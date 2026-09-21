"""Kapsama tablosu: her metrik kaç birimde hesaplanabiliyor, kaçında ayırt ediyor.

Sertleştirme Blok 1b, madde 3. Plan: "ayrım yapmayan metrik düşürülür ya da
gerekçesiyle tutulur". Bu betik o kararın **girdisini** üretir; metrik ya da
eşik değiştirmez.

    python experiments/hardening/coverage.py

Önce `corpus.py fetch`. Çıktı: `results/coverage.json` (tekrar üretildiğinde
birebir aynı) ve `results/coverage-tables.md` (belge bunları alıntılar).

Her metrik ve her proje için üç soru:

1. **Hesaplanabiliyor mu?** Birimlerin (fonksiyon/sınıf/modül) kaçında değer
   `null` değil.
2. **Değer tanım gereği mi belli?** Hesaplanmış ama ölçmeden bilinen değerler:

   * LCOM4 — tek adlı metodu olan sınıfta tanım gereği 1 (tek düğümlü grafik).
   * CAM — parametreli tek metodu olan sınıfta tanım gereği 1.0
     (`cam_coverage.py`, `ClassCoverage.informative`).
   * DAM — tek attribute'lu sınıfta yalnızca 0 ya da 1 olabilir; oran değil
     ikili bir bayraktır.

   Bu değerler hesaplanmış sayılır ama "bilgi taşıyan" sayılmaz.
3. **Ayırt ediyor mu?** Bilgi taşıyan değerlerin proje içindeki yayılımı:
   p10 ≠ p90 ise metrik o projede birimlerin orta %80'ini birbirinden ayırıyor.
   Yanında en sık değerin payı (mod payı) verilir.

Genel değer, dağılım tablosuyla aynı kuralla projelerin medyanıdır
(`distribution.py`). Yayılım sorusuna yalnızca bilgi taşıyan en az
`MIN_VALUES` değeri olan proje katılır.

**Ölçülen mantık payı** (betik tarzı kod) yeniden hesaplanmaz;
`corpus-inventory.json`'dan okunur (`corpus.py inventory`).
"""

from __future__ import annotations

import ast
import json
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from cam_coverage import classify
from compare_radon import HERE, PROJECTS_FILE, load_projects
from corpus import (
    INVENTORY_FILE,
    PROJECT_TYPES,
    accuracy_set_mismatches,
    load_corpus,
    project_config,
)
from distribution import ALL_METRICS, CLASS_METRICS, MIN_VALUES, median_of, percentile

JSON_FILE = HERE / "results" / "coverage.json"
TABLES_FILE = HERE / "results" / "coverage-tables.md"


# --------------------------------------------------------------------------- #
# Tanım gereği belli değerler — test edilir
# --------------------------------------------------------------------------- #


def lcom4_is_trivial(node: ast.ClassDef) -> bool:
    """Tek adlı metot: LCOM4 grafiği tek düğüm, değer tanım gereği 1.

    `lcom4` metotları **adla** düğüm yapar; property getter/setter çifti tek
    düğümdür. Bu yüzden sayılan şey `nom` değil, farklı metot adıdır.
    """
    from rlens.analysis.class_metrics import class_methods

    return len({method.name for method in class_methods(node)}) == 1


def cam_is_trivial(node: ast.ClassDef) -> bool:
    """Hesaplanmış ama parametreli tek metodu olan sınıf: CAM tanım gereği 1.0."""
    coverage = classify(node)
    return coverage.status == "computed" and not coverage.informative


def dam_is_trivial(node: ast.ClassDef) -> bool:
    """Tek attribute: DAM yalnızca 0 ya da 1 olabilir."""
    from rlens.analysis.class_metrics import assigned_attributes

    return len(assigned_attributes(node)) == 1


TRIVIAL_RULES = {"lcom4": lcom4_is_trivial, "cam": cam_is_trivial, "dam": dam_is_trivial}
"""Metrik → "değer ölçmeden belli mi" kuralı. Listede olmayan metrikte hiçbir değer
tanım gereği belli sayılmaz."""


# --------------------------------------------------------------------------- #
# Saf istatistik — test edilir
# --------------------------------------------------------------------------- #


@dataclass
class Coverage:
    """Bir projenin tek metriği için ham sayımlar."""

    units: int = 0
    nulls: int = 0
    trivial: int = 0
    informative: list[float] = field(default_factory=list)

    def add(self, value: float | None, trivial: bool = False) -> None:
        self.units += 1
        if value is None:
            self.nulls += 1
        elif trivial:
            self.trivial += 1
        else:
            self.informative.append(value)

    @property
    def computed(self) -> int:
        return self.units - self.nulls


def _share(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def summarise_coverage(coverage: Coverage) -> dict:
    """Bir projenin tek metriği için özet."""
    values = coverage.informative
    counts = Counter(values)
    mode, mode_count = (
        min(counts.items(), key=lambda item: (-item[1], item[0])) if counts else (None, 0)
    )
    p10 = percentile(values, 10)
    p90 = percentile(values, 90)
    return {
        "units": coverage.units,
        "computed_share": _share(coverage.computed, coverage.units),
        "trivial_share": _share(coverage.trivial, coverage.units),
        "informative_share": _share(len(values), coverage.units),
        "informative": len(values),
        "eligible": len(values) >= MIN_VALUES,
        "p10": p10,
        "p90": p90,
        "spread": (p10 != p90) if len(values) >= MIN_VALUES else None,
        "mode": mode,
        "mode_share": _share(mode_count, len(values)),
    }


def aggregate_coverage(summaries: list[dict]) -> dict:
    """Projelerin özetlerinden medyan.

    Pay sütunlarına birimi olan her proje katılır; yayılım ve mod sütunlarına
    yalnızca `eligible` projeler. Mod, uygun projelerin modlarının en sık olanıdır
    (eşitlikte küçüğü).
    """
    with_units = [entry for entry in summaries if entry["units"]]
    eligible = [entry for entry in summaries if entry["eligible"]]
    modes = Counter(entry["mode"] for entry in eligible)
    return {
        "projects": len(with_units),
        "computed_share": median_of(entry["computed_share"] for entry in with_units),
        "trivial_share": median_of(entry["trivial_share"] for entry in with_units),
        "informative_share": median_of(entry["informative_share"] for entry in with_units),
        "eligible_projects": len(eligible),
        "spread_projects": sum(1 for entry in eligible if entry["spread"]),
        "mode": min(modes.items(), key=lambda item: (-item[1], item[0]))[0] if modes else None,
        "mode_share": median_of(entry["mode_share"] for entry in eligible),
    }


# --------------------------------------------------------------------------- #
# Toplama
# --------------------------------------------------------------------------- #

CLASS_METRIC_NAMES = tuple(name for name, _, _ in CLASS_METRICS)


def class_nodes(parsed_modules) -> dict[tuple[str, str, int], ast.ClassDef]:
    """(modül, sınıf adı, satır) → düğüm. Tarayıcının ölçtüğü sınıflarla aynı küme."""
    from rlens.analysis.class_metrics import iter_module_classes

    return {
        (module.module, node.name, node.lineno): node
        for module in parsed_modules
        for node in iter_module_classes(module.tree)
    }


def collect(result) -> dict[str, Coverage]:
    """Bir taramadan metrik başına kapsama sayımları."""
    nodes = class_nodes(result.modules)
    collected = {name: Coverage() for name, _, _ in ALL_METRICS}
    for module in result.report.modules:
        collected["ca"].add(module.ca)
        collected["ce"].add(module.ce)
        collected["instability"].add(module.instability)
        functions = list(module.functions)
        for cls in module.classes:
            functions.extend(cls.methods)
            node = nodes[(cls.module, cls.name, cls.lineno)]
            for name in CLASS_METRIC_NAMES:
                value = getattr(cls, name)
                rule = TRIVIAL_RULES.get(name)
                trivial = value is not None and rule is not None and rule(node)
                collected[name].add(value, trivial)
        for function in functions:
            for name in ("cyclomatic_complexity", "loc", "param_count", "max_nesting"):
                collected[name].add(getattr(function, name))
    return collected


def trivial_value_violations(result) -> dict[str, int]:
    """Tanım gereği belli sayılan değerin gerçekten o değer olmadığı sınıflar.

    LCOM4 1, CAM 1.0, DAM {0, 1} olmalı. Sıfırdan farklı bir sayı, kuralın
    tanımla uyuşmadığını gösterir ve tablo yayınlanmaz.
    """
    nodes = class_nodes(result.modules)
    expected = {
        "lcom4": lambda value: value == 1,
        "cam": lambda value: value == 1.0,
        "dam": lambda value: value in (0.0, 1.0),
    }
    violations = dict.fromkeys(expected, 0)
    for module in result.report.modules:
        for cls in module.classes:
            node = nodes[(cls.module, cls.name, cls.lineno)]
            for name, check in expected.items():
                value = getattr(cls, name)
                if value is not None and TRIVIAL_RULES[name](node) and not check(value):
                    violations[name] += 1
    return violations


def logic_coverage(inventory: dict) -> dict:
    """`corpus-inventory.json`'dan ölçülen mantık payı: proje ve tür bazında."""
    projects = {
        name: {"type": entry["type"], "measured_logic_share": entry["measured_logic_share"]}
        for name, entry in inventory["projects"].items()
    }
    by_type = {
        kind: median_of(
            entry["measured_logic_share"] for entry in projects.values() if entry["type"] == kind
        )
        for kind in PROJECT_TYPES
    }
    lowest = sorted(projects.items(), key=lambda item: item[1]["measured_logic_share"])[:3]
    return {
        "median": median_of(entry["measured_logic_share"] for entry in projects.values()),
        "by_type": by_type,
        "lowest": {name: entry["measured_logic_share"] for name, entry in lowest},
    }


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

    per_project: dict[str, dict] = {}
    violations = {name: 0 for name in TRIVIAL_RULES}
    with tempfile.TemporaryDirectory() as workdir:
        for project in corpus:
            config = project_config(project, Path(workdir))
            result = scan_project_with_sources(project.scan_root, config)
            collected = collect(result)
            for name, count in trivial_value_violations(result).items():
                violations[name] += count
            per_project[project.name] = {
                "type": project.type,
                "metrics": {
                    name: summarise_coverage(collected[name]) for name, _, _ in ALL_METRICS
                },
            }
            print(f"{project.name:<17} scanned", flush=True)

    if any(violations.values()):
        print(f"trivial-value rule disagrees with the metric: {violations}")
        return 1

    names_by_type = {kind: [p.name for p in corpus if p.type == kind] for kind in PROJECT_TYPES}
    summary: dict = {
        "schema_version": SCHEMA_VERSION,
        "min_values": MIN_VALUES,
        "metrics": {},
    }
    for name, label, unit in ALL_METRICS:
        summaries = {p: per_project[p]["metrics"][name] for p in per_project}
        summary["metrics"][name] = {
            "label": label,
            "unit": unit,
            "all": aggregate_coverage(list(summaries.values())),
            "by_type": {
                kind: aggregate_coverage([summaries[p] for p in names])
                for kind, names in names_by_type.items()
            },
        }
    summary["logic"] = logic_coverage(json.loads(INVENTORY_FILE.read_text(encoding="utf-8")))
    summary["per_project"] = per_project

    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    JSON_FILE.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    TABLES_FILE.write_text(render_tables(summary), encoding="utf-8")
    print(render_tables(summary))
    return 0


# --------------------------------------------------------------------------- #
# Tablolar
# --------------------------------------------------------------------------- #


def _pct(value: float | None) -> str:
    return "—" if value is None else f"%{value * 100:.1f}"


def _num(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:g}" if float(value).is_integer() else f"{value:.2f}"


def render_tables(summary: dict) -> str:
    lines = [
        "<!-- Üretildi: experiments/hardening/coverage.py. Elle düzenlemeyin. -->",
        "",
        f"Scan şeması {summary['schema_version']}. Paylar birim başına, projelerin medyanı. "
        f"Yayılım ve mod: bilgi taşıyan en az {summary['min_values']} değeri olan projeler.",
        "",
        "## Kapsama — tüm korpus",
        "",
        "| Metrik | Birim | Proje | hesaplanan | tanım gereği belli | bilgi taşıyan "
        "| yayılım (p10 < p90) | mod | mod payı |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["metrics"].values():
        a = row["all"]
        lines.append(
            f"| {row['label']} | {row['unit']} | {a['projects']} | {_pct(a['computed_share'])} | "
            f"{_pct(a['trivial_share'])} | {_pct(a['informative_share'])} | "
            f"{a['spread_projects']}/{a['eligible_projects']} | {_num(a['mode'])} | "
            f"{_pct(a['mode_share'])} |"
        )
    lines += [
        "",
        "## Bilgi taşıyan pay — tür bazında",
        "",
        "Hücre: bilgi taşıyan pay (yayılım gösteren proje / uygun proje).",
        "",
        "| Metrik | " + " | ".join(PROJECT_TYPES) + " |",
        "|---|" + "---:|" * len(PROJECT_TYPES),
    ]
    for row in summary["metrics"].values():
        cells = []
        for kind in PROJECT_TYPES:
            entry = row["by_type"][kind]
            cells.append(
                f"{_pct(entry['informative_share'])} "
                f"({entry['spread_projects']}/{entry['eligible_projects']})"
            )
        lines.append(f"| {row['label']} | " + " | ".join(cells) + " |")
    logic = summary["logic"]
    lines += [
        "",
        "## Ölçülen mantık payı",
        "",
        "Raporun birimlerinin (fonksiyon, metot, sınıf gövdesi) kapsadığı mantık satırı payı; "
        "kaynak `corpus-inventory.json`.",
        "",
        "| Genel | " + " | ".join(PROJECT_TYPES) + " | en düşük üç |",
        "|---:|" + "---:|" * len(PROJECT_TYPES) + "---|",
        f"| {_pct(logic['median'])} | "
        + " | ".join(_pct(logic["by_type"][kind]) for kind in PROJECT_TYPES)
        + " | "
        + ", ".join(f"{name} {_pct(share)}" for name, share in logic["lowest"].items())
        + " |",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
