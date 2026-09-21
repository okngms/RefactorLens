"""Framework giriş noktaları: korpusta ne kadar, `too_many_params`'a etkisi ne.

Sertleştirme Blok 1b, madde 4. Kural `rlens.analysis.entry_points`'ta; bu
betik onu korpusta ve RefactorLens'in kendi kodunda ölçer.

    python experiments/hardening/entry_points.py

Çıktı: `results/entry-points.json` (tekrar üretildiğinde birebir aynı).

Ölçülen:

* 5+ parametreli fonksiyonların dekoratör dağılımı: giriş noktası, başka
  dekoratör, dekoratörsüz. Planın "dekoratörlü fonksiyonlar ayrı ele alınır"
  varsayımını sınamak için — dekoratörlülerin çoğu giriş noktası değilse,
  "dekoratör varsa muaf" kuralı gerçek kokuları gizlerdi.
* Tanınan giriş noktaları türe göre, örnekleriyle (elle denetim için).
* `too_many_params` sayısı kuraldan önce ve sonra, proje türüne göre.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from compare_radon import HERE
from corpus import load_corpus

from rlens.analysis.class_metrics import class_methods, iter_module_classes
from rlens.analysis.entry_points import KINDS, entry_point_kind
from rlens.analysis.func_metrics import iter_module_functions, param_count
from rlens.analysis.parser import parse_project
from rlens.config import DEFAULTS

RESULTS_FILE = HERE / "results" / "entry-points.json"
REPO_SRC = HERE.parent.parent / "src" / "rlens"

#: Örnek listesi bu kadar uzar; elle denetim için yeter.
EXAMPLES_PER_KIND = 8


def units(tree):
    """(fonksiyon düğümü, metot mu) — raporun ölçtüğü birimler."""
    for node in iter_module_functions(tree):
        yield node, False
    for cls in iter_module_classes(tree):
        for method in class_methods(cls):
            yield method, True


def survey(modules, label: str) -> dict:
    threshold = DEFAULTS["thresholds"]["max_params"]["warn"]
    categories: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    examples: dict[str, list[str]] = {kind: [] for kind in KINDS}
    for module in modules:
        for node, is_method in units(module.tree):
            if param_count(node, is_method=is_method) < threshold:
                continue
            kind = entry_point_kind(node)
            if kind is not None:
                categories["entry_point"] += 1
                kinds[kind] += 1
                if len(examples[kind]) < EXAMPLES_PER_KIND:
                    examples[kind].append(f"{label}:{module.module}.{node.name}")
            elif node.decorator_list:
                categories["other_decorator"] += 1
            else:
                categories["no_decorator"] += 1
    return {
        "too_many_params_before": sum(categories.values()),
        "too_many_params_after": categories["other_decorator"] + categories["no_decorator"],
        "categories": dict(sorted(categories.items())),
        "kinds": dict(sorted(kinds.items())),
        "examples": {kind: items for kind, items in examples.items() if items},
    }


def main() -> int:
    excludes = tuple(DEFAULTS["scan"]["exclude"])
    report: dict = {"threshold": DEFAULTS["thresholds"]["max_params"]["warn"], "projects": {}}
    by_type: dict[str, Counter[str]] = {}
    for project in load_corpus():
        modules, _ = parse_project(
            project.scan_root, (".",), excludes + tuple(f"{e}/" for e in project.excludes)
        )
        entry = survey(modules, project.name)
        entry["type"] = project.type
        report["projects"][project.name] = entry
        bucket = by_type.setdefault(project.type, Counter())
        bucket["before"] += entry["too_many_params_before"]
        bucket["after"] += entry["too_many_params_after"]
        for kind, count in entry["kinds"].items():
            bucket[kind] += count
    report["by_type"] = {kind: dict(counts) for kind, counts in by_type.items()}
    totals: Counter[str] = Counter()
    for entry in report["projects"].values():
        for key, value in entry["categories"].items():
            totals[key] += value
    report["corpus_categories"] = dict(sorted(totals.items()))

    own, _ = parse_project(Path(REPO_SRC), (".",), excludes)
    report["refactorlens"] = survey(own, "rlens")

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "projects"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
