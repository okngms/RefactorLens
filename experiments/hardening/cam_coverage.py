"""CAM annotation kapsamı: referans setinde CAM ne sıklıkla hesaplanabiliyor.

Sertleştirme Blok 1, madde 2 (CAM). CAM parametre **tipleri** üzerinden
tanımlıdır ve annotation kapsamı `cam_min_annotation_coverage` (0.7) altındaysa
`null` döner. Soru: bu kural gerçek kodda CAM'i ne kadar kullanılabilir bırakıyor?

Rapordaki `cam_skipped_reason` iki değer alır, ama bunlardan
`no_annotated_parameters` iki farklı durumu kapsar: sınıfın hiç parametresi
yoktur, **ya da** parametreleri vardır ama hiçbiri annotation'lı değildir.
İkincisi "annotation yazılmamış kod"dur; birincisi "CAM'in anlamı yok" demektir.
Bu betik ikisini ayırır:

    computed           CAM bir sayı
    below_threshold    0 < kapsam < eşik
    zero_annotations   parametre var, annotation hiç yok
    no_parameters      alıcı dışında parametre yok

**Hesaplanması anlamlı mı?** Parametreli tek bir metodu olan sınıfın CAM'i
tanım gereği 1.0'dır: tek metodun tipleri birleşimin tamamıdır. Bu sayı hiçbir
şey ayırt etmez. `computed_informative`, parametreli en az iki metodu olan
hesaplanmış sınıfları sayar — Blok 1b'nin "ayrım yapıyor mu" sorusuna ilk veri.

Eşik duyarlılığı da raporlanır (0.5 / 0.7 / 0.9): eşiği değiştirmenin kapsamı
ne kadar değiştirdiği, 1b'de eşiğin kalibrasyonu için girdidir.

Kullanım (önce `compare_radon.py fetch`):

    python experiments/hardening/cam_coverage.py
"""

from __future__ import annotations

import ast
import json
from collections import Counter
from dataclasses import dataclass

from compare_radon import ALWAYS_EXCLUDED, HERE, load_projects

from rlens.analysis.class_metrics import cam, class_methods, iter_module_classes, self_parameter
from rlens.analysis.parser import parse_project

RESULTS_FILE = HERE / "results" / "cam-coverage.json"

DEFAULT_THRESHOLD = 0.7
THRESHOLDS = (0.5, 0.7, 0.9)

COMPUTED = "computed"
BELOW_THRESHOLD = "below_threshold"
ZERO_ANNOTATIONS = "zero_annotations"
NO_PARAMETERS = "no_parameters"
STATUSES = (COMPUTED, BELOW_THRESHOLD, ZERO_ANNOTATIONS, NO_PARAMETERS)


@dataclass(frozen=True)
class ClassCoverage:
    status: str
    coverage: float | None
    """Annotation kapsamı; parametresiz sınıfta `None`."""
    parameterised_methods: int
    value: float | None

    @property
    def informative(self) -> bool:
        return self.status == COMPUTED and self.parameterised_methods >= 2


def parameter_counts(node: ast.ClassDef) -> tuple[int, int]:
    """(parametreli metot sayısı, toplam parametre) — `cam` ile aynı kural.

    Aynı kuralı burada tekrar etmek bilinçli: `cam` iki durumu tek sebep altında
    döndürür ve ayrımı dışarıdan yapmanın başka yolu yok. Tutarlılığı
    `tests/test_hardening_cam.py` sınar.
    """
    methods = 0
    total = 0
    for method in class_methods(node):
        receiver = self_parameter(method)
        arguments = method.args.posonlyargs + method.args.args + method.args.kwonlyargs
        if receiver in ("self", "cls") and arguments:
            arguments = arguments[1:]
        count = len(arguments) + (method.args.vararg is not None) + (method.args.kwarg is not None)
        if count:
            methods += 1
            total += count
    return methods, total


def classify(node: ast.ClassDef, threshold: float = DEFAULT_THRESHOLD) -> ClassCoverage:
    result = cam(node, min_annotation_coverage=threshold)
    methods, total = parameter_counts(node)
    if total == 0:
        return ClassCoverage(NO_PARAMETERS, None, 0, None)
    if result.value is not None:
        status = COMPUTED
    elif result.annotation_coverage == 0.0:
        status = ZERO_ANNOTATIONS
    else:
        status = BELOW_THRESHOLD
    return ClassCoverage(status, result.annotation_coverage, methods, result.value)


def quantile(values: list[float], q: float) -> float | None:
    """Doğrusal interpolasyonlu yüzdelik; boş listede `None`."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 4)


def summarise(classes: list[ClassCoverage], nodes: list[ast.ClassDef]) -> dict:
    statuses = Counter(item.status for item in classes)
    with_parameters = [item for item in classes if item.status != NO_PARAMETERS]
    coverages = [item.coverage for item in with_parameters if item.coverage is not None]
    sensitivity = {}
    for threshold in THRESHOLDS:
        computed = sum(
            1 for node in nodes if cam(node, min_annotation_coverage=threshold).value is not None
        )
        sensitivity[str(threshold)] = computed
    total = len(classes)
    return {
        "classes": total,
        "statuses": {status: statuses.get(status, 0) for status in STATUSES},
        "computed_share": round(statuses.get(COMPUTED, 0) / total, 4) if total else None,
        "computed_informative": sum(1 for item in classes if item.informative),
        "classes_with_parameters": len(with_parameters),
        "coverage_quantiles": {
            "p25": quantile(coverages, 0.25),
            "median": quantile(coverages, 0.5),
            "p75": quantile(coverages, 0.75),
        },
        "computed_by_threshold": sensitivity,
    }


def main() -> int:
    report: dict = {"threshold": DEFAULT_THRESHOLD, "projects": {}}
    all_classes: list[ClassCoverage] = []
    all_nodes: list[ast.ClassDef] = []
    for project in load_projects():
        modules, _ = parse_project(project.scan_root, (".",), ALWAYS_EXCLUDED + project.excludes)
        nodes = [node for module in modules for node in iter_module_classes(module.tree)]
        classes = [classify(node) for node in nodes]
        report["projects"][project.name] = summarise(classes, nodes)
        all_classes.extend(classes)
        all_nodes.extend(nodes)
    report["total"] = summarise(all_classes, all_nodes)

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    header = (
        f"{'project':<11} {'classes':>7} {'computed':>9} {'informative':>11} "
        f"{'below':>6} {'zero':>5} {'no_par':>6}  median  @0.5/0.7/0.9"
    )
    print(header)
    print("-" * len(header))
    for name, entry in [*report["projects"].items(), ("total", report["total"])]:
        s = entry["statuses"]
        share = f"{entry['computed_share']:.0%}" if entry["computed_share"] is not None else "-"
        median = entry["coverage_quantiles"]["median"]
        by = entry["computed_by_threshold"]
        print(
            f"{name:<11} {entry['classes']:>7} {s[COMPUTED]:>4} {share:>4} "
            f"{entry['computed_informative']:>11} "
            f"{s[BELOW_THRESHOLD]:>6} {s[ZERO_ANNOTATIONS]:>5} {s[NO_PARAMETERS]:>6}  "
            f"{median if median is not None else '-':>6}  {by['0.5']}/{by['0.7']}/{by['0.9']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
