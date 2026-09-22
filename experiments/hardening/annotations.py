"""Anotasyon kapsamı: korpusta dağılım ve `py.typed` ile bağımsız sınama.

v2.2 §3. Ön kayıt ve çürütme koşulları `annotation-coverage.md`'de, ölçümden
**önce** yazıldı; bu betik onları mekanik olarak uygular. Ölçü fonksiyonları
aracın kendisinden gelir (`func_metrics.annotation_coverage`,
`class_metrics.class_annotation_coverage`).

    python experiments/hardening/annotations.py

Önce `corpus.py fetch`. Çıktı: `results/annotation-coverage.json` ve
`results/annotation-coverage-tables.md`; tekrar üretildiğinde birebir aynı.
"""

from __future__ import annotations

import json
import statistics
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from compare_radon import HERE, PROJECTS_FILE, load_projects
from corpus import PROJECT_TYPES, accuracy_set_mismatches, load_corpus, project_config
from distribution import median_of

from rlens.analysis.class_metrics import (
    cam,
    class_annotation_coverage,
    class_methods,
    iter_module_classes,
)
from rlens.analysis.func_metrics import iter_module_functions, parameter_slots

JSON_FILE = HERE / "results" / "annotation-coverage.json"
TABLES_FILE = HERE / "results" / "annotation-coverage-tables.md"

MIN_FUNCTIONS = 30
PY_TYPED_ABOVE_MEDIAN = 0.8


# --------------------------------------------------------------------------- #
# Saf kurallar — test edilir
# --------------------------------------------------------------------------- #


@dataclass
class ProjectCounts:
    slots: int = 0
    annotated: int = 0
    functions: int = 0
    with_slots: int = 0
    fully: int = 0
    none: int = 0
    returns: int = 0
    cam_mismatches: int = 0
    classes_with_slots: int = 0
    per_function: list[float] = field(default_factory=list)

    def add_function(self, node, *, is_method: bool) -> None:
        self.functions += 1
        if node.returns is not None:
            self.returns += 1
        slots = parameter_slots(node, is_method=is_method)
        if not slots:
            return
        annotated = sum(1 for slot in slots if slot.annotation is not None)
        self.with_slots += 1
        self.slots += len(slots)
        self.annotated += annotated
        self.per_function.append(annotated / len(slots))
        if annotated == len(slots):
            self.fully += 1
        elif annotated == 0:
            self.none += 1


def summarise(counts: ProjectCounts) -> dict:
    def share(part: int, whole: int) -> float | None:
        return round(part / whole, 4) if whole else None

    return {
        "functions": counts.functions,
        "with_slots": counts.with_slots,
        "eligible": counts.with_slots >= MIN_FUNCTIONS,
        "coverage": share(counts.annotated, counts.slots),
        "fully_annotated": share(counts.fully, counts.with_slots),
        "unannotated": share(counts.none, counts.with_slots),
        "returns": share(counts.returns, counts.functions),
        "classes_with_slots": counts.classes_with_slots,
        "cam_mismatches": counts.cam_mismatches,
    }


def refutations(projects: dict[str, dict]) -> dict:
    """Ön kayıttaki (a), (b), (c) koşulları; `rejected` herhangi biri tutarsa."""
    eligible = {name: p for name, p in projects.items() if p["eligible"]}
    typed = [p["coverage"] for p in eligible.values() if p["py_typed"]]
    untyped = [p["coverage"] for p in eligible.values() if not p["py_typed"]]
    overall = statistics.median(p["coverage"] for p in eligible.values()) if eligible else None
    typed_median = statistics.median(typed) if typed else None
    untyped_median = statistics.median(untyped) if untyped else None
    above = sum(1 for value in typed if overall is not None and value > overall)
    a = typed_median is None or untyped_median is None or not typed_median > untyped_median
    b = not typed or above / len(typed) < PY_TYPED_ABOVE_MEDIAN
    c = any(p["cam_mismatches"] for p in projects.values())
    return {
        "overall_median": overall,
        "py_typed_median": typed_median,
        "untyped_median": untyped_median,
        "py_typed_projects": len(typed),
        "untyped_projects": len(untyped),
        "py_typed_above_overall": above,
        "a": a,
        "b": b,
        "c": c,
        "rejected": a or b or c,
    }


def has_py_typed(root: Path, excludes: list[str]) -> bool:
    """Dışlanan dizinlerin dışında en az bir `py.typed`."""
    excluded = {entry.strip("/").split("/")[-1] for entry in excludes}
    for marker in root.rglob("py.typed"):
        parts = marker.relative_to(root).parts[:-1]
        if not excluded.intersection(parts):
            return True
    return False


# --------------------------------------------------------------------------- #
# Toplama
# --------------------------------------------------------------------------- #


def collect(result) -> ProjectCounts:
    counts = ProjectCounts()
    for module in result.modules:
        for node in iter_module_functions(module.tree):
            counts.add_function(node, is_method=False)
        for cls in iter_module_classes(module.tree):
            for method in class_methods(cls):
                counts.add_function(method, is_method=True)
            value = class_annotation_coverage(cls)
            if value is not None:
                counts.classes_with_slots += 1
                if value != cam(cls).annotation_coverage:
                    counts.cam_mismatches += 1
    return counts


def main() -> int:
    from rlens.analysis.model import SCHEMA_VERSION
    from rlens.analysis.scanner import scan_project_with_sources

    corpus = load_corpus()
    problems = accuracy_set_mismatches(corpus, load_projects(PROJECTS_FILE))
    if problems:
        print("corpus.txt disagrees with projects.txt: " + "; ".join(problems))
        return 1
    missing = [project.name for project in corpus if not project.scan_root.is_dir()]
    if missing:
        print(f"not fetched: {', '.join(missing)} — run `corpus.py fetch` first")
        return 1

    projects: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as workdir:
        for project in corpus:
            config = project_config(project, Path(workdir))
            result = scan_project_with_sources(project.scan_root, config)
            counts = collect(result)
            projects[project.name] = {
                "type": project.type,
                "py_typed": has_py_typed(project.scan_root, list(config.scan.exclude)),
            } | summarise(counts)
            print(f"{project.name:<17} scanned", flush=True)

    eligible = [p for p in projects.values() if p["eligible"]]
    by_type = {
        kind: {
            key: median_of(p[key] for p in eligible if p["type"] == kind)
            for key in ("coverage", "fully_annotated", "unannotated", "returns")
        }
        | {"projects": sum(1 for p in eligible if p["type"] == kind)}
        for kind in PROJECT_TYPES
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "min_functions": MIN_FUNCTIONS,
        "overall": {
            key: median_of(p[key] for p in eligible)
            for key in ("coverage", "fully_annotated", "unannotated", "returns")
        }
        | {"projects": len(eligible)},
        "by_type": by_type,
        "refutations": refutations(projects),
        "per_project": projects,
    }
    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    JSON_FILE.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    TABLES_FILE.write_text(render_tables(summary), encoding="utf-8")
    sys.stdout.reconfigure(errors="replace")
    print(render_tables(summary))
    return 0


def _pct(value: float | None) -> str:
    return "-" if value is None else f"%{value * 100:.1f}"


def render_tables(summary: dict) -> str:
    o = summary["overall"]
    r = summary["refutations"]
    lines = [
        "<!-- Üretildi: experiments/hardening/annotations.py. Elle düzenlemeyin. -->",
        "",
        f"Scan şeması {summary['schema_version']}. Proje değeri: yuvaların havuz oranı; "
        f"genel ve tür değeri projelerin medyanı (yuvalı en az {summary['min_functions']} "
        "fonksiyonu olan projeler).",
        "",
        "## Dağılım",
        "",
        "| Grup | proje | kapsam | tam annotation'lı fonksiyon | hiç annotation'sız "
        "| dönüş annotation'ı |",
        "|---|---:|---:|---:|---:|---:|",
        f"| tüm korpus | {o['projects']} | {_pct(o['coverage'])} | "
        f"{_pct(o['fully_annotated'])} | {_pct(o['unannotated'])} | {_pct(o['returns'])} |",
    ]
    for kind, t in summary["by_type"].items():
        lines.append(
            f"| {kind} | {t['projects']} | {_pct(t['coverage'])} | {_pct(t['fully_annotated'])} "
            f"| {_pct(t['unannotated'])} | {_pct(t['returns'])} |"
        )
    lines += [
        "",
        "## Proje başına",
        "",
        "| Proje | tür | py.typed | kapsam | tam | hiç | dönüş |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for name, p in sorted(
        summary["per_project"].items(), key=lambda item: -(item[1]["coverage"] or 0)
    ):
        lines.append(
            f"| {name} | {p['type']} | {'evet' if p['py_typed'] else 'hayır'} | "
            f"{_pct(p['coverage'])} | {_pct(p['fully_annotated'])} | "
            f"{_pct(p['unannotated'])} | {_pct(p['returns'])} |"
        )
    lines += [
        "",
        "## Ön kayıtlı çürütme koşulları",
        "",
        f"- Genel medyan {_pct(r['overall_median'])}; `py.typed` taşıyan "
        f"{r['py_typed_projects']} projenin medyanı {_pct(r['py_typed_median'])}, taşımayan "
        f"{r['untyped_projects']} projenin {_pct(r['untyped_median'])}.",
        f"- (a) py.typed medyanı büyük değil: **{'evet' if r['a'] else 'hayır'}**",
        f"- (b) py.typed projelerinin %80'inden azı genel medyanın üstünde "
        f"({r['py_typed_above_overall']}/{r['py_typed_projects']}): "
        f"**{'evet' if r['b'] else 'hayır'}**",
        f"- (c) sınıf değeri CAM'in iç kapsamından farklı: **{'evet' if r['c'] else 'hayır'}**",
        f"- Sonuç: **{'reddedildi' if r['rejected'] else 'çürütülmedi'}**",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
