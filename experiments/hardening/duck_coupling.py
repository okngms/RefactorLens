"""Duck typing yapısal kuplajı (v2.2 §3, K14): korpus ölçümü ve kesinlik örneklemi.

Ön kayıt ve çürütme koşulları `duck-coupling.md`'de, ölçümden **önce** yazıldı.
Ölçü fonksiyonu K14'ten beri aracın kendisinden gelir (`func_metrics.duck_pairs`).

    python experiments/hardening/duck_coupling.py measure   # ~2 dk
    python experiments/hardening/duck_coupling.py summary   # (a) kararları dolunca
"""

from __future__ import annotations

import argparse
import ast
import json
import random
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from compare_radon import HERE, PROJECTS_FILE, load_projects
from corpus import PROJECT_TYPES, accuracy_set_mismatches, load_corpus, project_config
from distribution import MIN_VALUES, median_of, percentile

from rlens.analysis.class_metrics import (
    all_methods,
    assigned_attributes,
    class_methods,
    iter_module_classes,
)
from rlens.analysis.func_metrics import (
    _walk_body,
    duck_pairs,
    iter_module_functions,
    parameter_slots,
)

JSON_FILE = HERE / "results" / "duck-coupling.json"
TABLES_FILE = HERE / "results" / "duck-coupling-tables.md"
SAMPLE_FILE = HERE / "duck-sample.json"
VERDICTS_FILE = HERE / "duck-verdicts.json"

SEED = 20260922
SAMPLE_SIZE = 30
PRECISION_FLOOR = 24
MEMBER_SHARE_FLOOR = 0.6
MIN_TYPED_PAIRS = 30


# --------------------------------------------------------------------------- #
# Aday ölçü — test edilir
# --------------------------------------------------------------------------- #


def class_members(node: ast.ClassDef) -> set[str]:
    """Sınıfın kendi attribute'ları ve metot adları; kalıtım hariç."""
    return assigned_attributes(node) | {method.name for method in all_methods(node)}


def annotation_name(annotation: ast.expr | None) -> str | None:
    """`Order` ya da `"Order"` → "Order"; başka biçimler `None`."""
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        text = annotation.value.strip()
        return text if text.isidentifier() else None
    return None


def verdict_problems(sample: list[dict], verdicts: dict) -> list[str]:
    problems = []
    for item in sample:
        entry = verdicts.get(item["id"])
        if entry is None or entry.get("verdict") not in ("argument", "not_argument"):
            problems.append(f"{item['id']}: verdict must be argument or not_argument")
        elif not entry.get("reason"):
            problems.append(f"{item['id']}: a verdict needs a reason")
    return problems


# --------------------------------------------------------------------------- #
# Toplama
# --------------------------------------------------------------------------- #


def _first_access(node, param: str, attr: str) -> int:
    lines = [
        child.lineno
        for child in _walk_body(node)
        if isinstance(child, ast.Attribute)
        and isinstance(child.value, ast.Name)
        and child.value.id == param
        and child.attr == attr
    ]
    return min(lines)


def measure(force: bool) -> int:
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
    pool: list[dict] = []
    with tempfile.TemporaryDirectory() as workdir:
        for project in corpus:
            result = scan_project_with_sources(
                project.scan_root, project_config(project, Path(workdir))
            )
            owners: dict[str, list[ast.ClassDef]] = defaultdict(list)
            for module in result.modules:
                for cls in iter_module_classes(module.tree):
                    owners[cls.name].append(cls)
            members = {
                name: class_members(nodes[0]) for name, nodes in owners.items() if len(nodes) == 1
            }
            values: list[int] = []
            module_level = module_level_positive = 0
            typed_pairs = typed_members = 0
            for module in result.modules:
                units = [(f, False, None) for f in iter_module_functions(module.tree)]
                for cls in iter_module_classes(module.tree):
                    units += [(m, True, cls.name) for m in class_methods(cls)]
                for function, is_method, owner in units:
                    pairs = duck_pairs(function, is_method=is_method)
                    if pairs is None:
                        continue
                    values.append(len(pairs))
                    if not is_method:
                        module_level += 1
                        module_level_positive += bool(pairs)
                    annotations = {
                        slot.arg: annotation_name(slot.annotation)
                        for slot in parameter_slots(function, is_method=is_method)
                    }
                    qualified = f"{owner}.{function.name}" if owner else function.name
                    for param, attr in sorted(pairs):
                        typed = annotations.get(param)
                        if typed in members:
                            typed_pairs += 1
                            typed_members += attr in members[typed]
                        pool.append(
                            {
                                "id": f"{project.name}:{module.module}:{qualified}:{param}.{attr}",
                                "project": project.name,
                                "file": module.relative_path,
                                "line": _first_access(function, param, attr),
                                "function": qualified,
                                "pair": f"{param}.{attr}",
                            }
                        )
            eligible = len(values) >= MIN_VALUES
            projects[project.name] = {
                "type": project.type,
                "functions": len(values),
                "p50": percentile(values, 50),
                "p90": percentile(values, 90),
                "p10": percentile(values, 10),
                "spread": (percentile(values, 10) < percentile(values, 90)) if eligible else None,
                "positive_share": round(sum(1 for v in values if v) / len(values), 4)
                if values
                else None,
                "module_level_positive": round(module_level_positive / module_level, 4)
                if module_level
                else None,
                "typed_pairs": typed_pairs,
                "typed_member_share": round(typed_members / typed_pairs, 4)
                if typed_pairs
                else None,
            }
            print(f"{project.name:<17} scanned", flush=True)

    typed = [
        p["typed_member_share"] for p in projects.values() if p["typed_pairs"] >= MIN_TYPED_PAIRS
    ]
    member_median = median_of(typed)
    eligible = [p for p in projects.values() if p["spread"] is not None]
    spread = sum(1 for p in eligible if p["spread"])
    refutations = {
        "b": member_median is None or member_median < MEMBER_SHARE_FLOOR,
        "c": spread < len(eligible) / 2,
    }
    if not SAMPLE_FILE.exists() or force:
        rng = random.Random(SEED)
        ordered = sorted(pool, key=lambda item: item["id"])
        sample = rng.sample(ordered, SAMPLE_SIZE) if len(ordered) > SAMPLE_SIZE else ordered
        SAMPLE_FILE.write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")
        if not VERDICTS_FILE.exists() or force:
            VERDICTS_FILE.write_text(
                json.dumps({i["id"]: {"verdict": None, "reason": ""} for i in sample}, indent=2)
                + "\n",
                encoding="utf-8",
            )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "pairs": len(pool),
        "typed_projects": len(typed),
        "typed_member_median": member_median,
        "spread_projects": spread,
        "eligible_projects": len(eligible),
        "by_type_p90": {
            kind: median_of(
                p["p90"] for p in projects.values() if p["type"] == kind and p["spread"] is not None
            )
            for kind in PROJECT_TYPES
        },
        "refutations": refutations,
        "per_project": projects,
    }
    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    JSON_FILE.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    TABLES_FILE.write_text(render_tables(summary), encoding="utf-8")
    sys.stdout.reconfigure(errors="replace")
    print(render_tables(summary))
    return 0


def summary() -> int:
    sample = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
    verdicts = json.loads(VERDICTS_FILE.read_text(encoding="utf-8"))
    problems = verdict_problems(sample, verdicts)
    if problems:
        print("verdicts incomplete; no precision computed:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    correct = sum(1 for item in sample if verdicts[item["id"]]["verdict"] == "argument")
    data = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    data["precision"] = {
        "sample": len(sample),
        "argument": correct,
        "precision": round(correct / len(sample), 4),
        "refuted": correct < PRECISION_FLOOR,
    }
    data["refutations"]["a"] = data["precision"]["refuted"]
    JSON_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    TABLES_FILE.write_text(render_tables(data), encoding="utf-8")
    print(json.dumps(data["precision"], indent=2))
    return 0


def _pct(value: float | None) -> str:
    return "-" if value is None else f"%{value * 100:.1f}"


def render_tables(summary: dict) -> str:
    r = summary["refutations"]
    lines = [
        "<!-- Üretildi: experiments/hardening/duck_coupling.py. Elle düzenlemeyin. -->",
        "",
        f"Scan şeması {summary['schema_version']}. Parametreli fonksiyonlar; "
        f"toplam {summary['pairs']} (parametre, attribute) çifti.",
        "",
        "| Proje | tür | fonksiyon | p10 | p50 | p90 | yayılım | değer > 0 | "
        "modül fonk. değer > 0 | tipli çift | üye payı |",
        "|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|",
    ]
    for name, p in summary["per_project"].items():
        spread = {True: "evet", False: "hayır", None: "-"}[p["spread"]]
        lines.append(
            f"| {name} | {p['type']} | {p['functions']} | {p['p10']} | {p['p50']} | {p['p90']} | "
            f"{spread} | {_pct(p['positive_share'])} | {_pct(p['module_level_positive'])} | "
            f"{p['typed_pairs']} | {_pct(p['typed_member_share'])} |"
        )
    lines += [
        "",
        "## Ön kayıtlı koşullar",
        "",
        f"- (b) tipli çiftlerde üye payı medyanı ({summary['typed_projects']} proje) "
        f"{_pct(summary['typed_member_median'])} < %60: **{'evet' if r['b'] else 'hayır'}**",
        f"- (c) yayılım gösteren proje {summary['spread_projects']}/"
        f"{summary['eligible_projects']} < yarısı: **{'evet' if r['c'] else 'hayır'}**",
    ]
    if "precision" in summary:
        p = summary["precision"]
        lines.append(
            f"- (a) elle kesinlik {p['argument']}/{p['sample']} < {PRECISION_FLOOR}: "
            f"**{'evet' if p['refuted'] else 'hayır'}**"
        )
    else:
        lines.append("- (a) elle kesinlik: kararlar bekleniyor")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("measure", "summary"))
    parser.add_argument("--force", action="store_true", help="redraw the precision sample")
    args = parser.parse_args(argv)
    return measure(args.force) if args.command == "measure" else summary()


if __name__ == "__main__":
    raise SystemExit(main())
