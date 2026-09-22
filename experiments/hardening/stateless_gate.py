"""`god_class` ve durumsuz metotlar: dört aday kural (v2.2 §5b, K9'un sorusu).

Ön kayıt ve çürütme koşulları `stateless-gate.md`'de, **ölçümden önce** yazıldı.
Bu betik o koşulları mekanik olarak uygular; aracı değiştirmez.

    R1  bugünkü kapı, ama metot adlarının en az yarısı taslaksa koku yok
    R2  bugünkü kapı, ama metot adlarının en az yarısı alıcısızsa koku yok
    R3  LCOM4 yalnızca durumlu metot adlarının grafiğinde (çağrılar dahil) >= t
    R4  LCOM3-HM yalnızca durumlu metot adları üzerinde >= t

R3/R4'ün t'si: ölçünün sınıf dağılımında ≈ p90 (en az iki durumlu metot adı
olan sınıflar, proje başına, projelerin medyanı), en yakın tamsayı.

    python experiments/hardening/stateless_gate.py

Önce `corpus.py fetch`. Çıktı: `results/stateless-gate.json` ve
`results/stateless-gate-tables.md`; tekrar üretildiğinde birebir aynı.
"""

from __future__ import annotations

import ast
import json
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from compare_radon import HERE, PROJECTS_FILE, load_projects
from corpus import accuracy_set_mismatches, load_corpus, project_config
from coverage import class_nodes
from density_gate import attribute_sets, lcom3_hm, stateless_kinds, stateless_share
from distribution import MIN_VALUES, median_of, percentile

from rlens.analysis.class_metrics import called_methods, class_methods, stub_method_share

JSON_FILE = HERE / "results" / "stateless-gate.json"
TABLES_FILE = HERE / "results" / "stateless-gate-tables.md"

CURRENT_LCOM4 = 3
"""Bugünkü `god_class` kapısı (`smells.god_class.lcom4`); boyut koşulu ayrıca."""
EXCLUSION_SHARE = 0.5
STATELESS_SHARE = 0.5
FIRES_EVERYWHERE = 0.9
NARROW_LIMIT = 0.1
CANDIDATES = ("R1", "R2", "R3", "R4")


# --------------------------------------------------------------------------- #
# Ölçüler — test edilir
# --------------------------------------------------------------------------- #


def _stateful_sets(node: ast.ClassDef) -> dict[str, set[str]]:
    return {name: attrs for name, attrs in attribute_sets(node).items() if attrs}


def lcom4_stateful(node: ast.ClassDef) -> int | None:
    """LCOM4, yalnızca durumlu metot adlarının grafiğinde. Durumlu ad yoksa `None`.

    Çağrı kenarı yalnızca iki durumlu ad arasında sayılır; durumsuz bir ara
    metot üzerinden geçen yol, o metot düğüm olmadığı için kopar.
    """
    sets = _stateful_sets(node)
    if not sets:
        return None
    parent = {name: name for name in sets}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def union(left: str, right: str) -> None:
        parent[find(right)] = find(left)

    owners: dict[str, list[str]] = {}
    for name, attributes in sets.items():
        for attribute in attributes:
            owners.setdefault(attribute, []).append(name)
    for names in owners.values():
        for other in names[1:]:
            union(names[0], other)
    methods = class_methods(node)
    known = {method.name for method in methods}
    for method in methods:
        if method.name not in sets:
            continue
        for target in called_methods(method, known):
            if target in sets:
                union(method.name, target)
    return len({find(name) for name in sets})


def lcom3_stateful(node: ast.ClassDef) -> int | None:
    """LCOM3-HM, yalnızca durumlu metot adları üzerinde."""
    return lcom3_hm(_stateful_sets(node))


def exclusion_share(node: ast.ClassDef, kind: str) -> float | None:
    """Belirli türdeki durumsuz metot adlarının bütün metot adlarına payı."""
    names = attribute_sets(node)
    if not names:
        return None
    return round(stateless_kinds(node)[kind] / len(names), 4)


@dataclass(frozen=True)
class ClassFacts:
    name: str
    nom: int
    lcom4: int
    stateful: int
    lcom4_stateful: int | None
    lcom3_stateful: int | None
    stub_share: float
    receiverless_share: float
    stateless_share: float


def class_facts(node: ast.ClassDef, *, name: str, nom: int, lcom4_value: int) -> ClassFacts:
    return ClassFacts(
        name=name,
        nom=nom,
        lcom4=lcom4_value,
        stateful=len(_stateful_sets(node)),
        lcom4_stateful=lcom4_stateful(node),
        lcom3_stateful=lcom3_stateful(node),
        # R1 aracın K10 kuralıyla birebir aynı payı kullanır.
        stub_share=stub_method_share(node) or 0.0,
        receiverless_share=exclusion_share(node, "no_receiver") or 0.0,
        stateless_share=stateless_share(attribute_sets(node)) or 0.0,
    )


def candidate_fires(facts: ClassFacts, candidate: str, threshold: int | None) -> bool:
    """Boyut koşulunu geçmiş bir sınıfta adayın kapısı."""
    if candidate == "R1":
        return facts.lcom4 >= CURRENT_LCOM4 and facts.stub_share < EXCLUSION_SHARE
    if candidate == "R2":
        return facts.lcom4 >= CURRENT_LCOM4 and facts.receiverless_share < EXCLUSION_SHARE
    value = facts.lcom4_stateful if candidate == "R3" else facts.lcom3_stateful
    return value is not None and value >= threshold


def rejections(
    classes: list[ClassFacts],
    fires: Callable[[ClassFacts], bool],
    candidate: str,
    p75: float | None,
    p90: float | None,
    p95: float | None,
) -> list[str]:
    """Ön kayıttaki çürütme koşullarından gerçekleşenler (`stateless-gate.md` §9)."""
    reasons: list[str] = []
    fired = [c for c in classes if fires(c)]
    if classes and len(fired) / len(classes) > FIRES_EVERYWHERE:
        reasons.append("a")
    if any(c.stub_share >= EXCLUSION_SHARE for c in fired):
        reasons.append("b")
    if p75 is not None and p75 == p90 == p95:
        reasons.append("c")
    base = [c for c in classes if c.lcom4 >= CURRENT_LCOM4 and c.stateless_share < STATELESS_SHARE]
    lost = [c for c in base if not fires(c)]
    if base and len(lost) > len(base) / 2:
        reasons.append("d")
    if candidate in ("R1", "R2"):
        current = [c for c in classes if c.lcom4 >= CURRENT_LCOM4]
        removed = [c for c in current if not fires(c)]
        if current and len(removed) > NARROW_LIMIT * len(current):
            reasons.append("narrow")
    return reasons


# --------------------------------------------------------------------------- #
# Toplama
# --------------------------------------------------------------------------- #


def main() -> int:
    from rlens.analysis.model import SCHEMA_VERSION
    from rlens.analysis.scanner import scan_project_with_sources
    from rlens.config import DEFAULTS

    corpus = load_corpus()
    problems = accuracy_set_mismatches(corpus, load_projects(PROJECTS_FILE))
    if problems:
        print("corpus.txt disagrees with projects.txt: " + "; ".join(problems))
        return 1
    missing = [project.name for project in corpus if not project.scan_root.is_dir()]
    if missing:
        print(f"not fetched: {', '.join(missing)} — run `corpus.py fetch` first")
        return 1

    rules = DEFAULTS["smells"]["god_class"]
    if rules["lcom4"] != CURRENT_LCOM4:
        print(f"smells.god_class.lcom4 is {rules['lcom4']}, expected {CURRENT_LCOM4}")
        return 1
    large: list[ClassFacts] = []
    distributions: dict[str, list[dict]] = {"lcom4_stateful": [], "lcom3_stateful": []}
    with tempfile.TemporaryDirectory() as workdir:
        for project in corpus:
            config = project_config(project, Path(workdir))
            result = scan_project_with_sources(project.scan_root, config)
            nodes = class_nodes(result.modules)
            values: dict[str, list[int]] = {"lcom4_stateful": [], "lcom3_stateful": []}
            for module in result.report.modules:
                for cls in module.classes:
                    node = nodes[(cls.module, cls.name, cls.lineno)]
                    if len(_stateful_sets(node)) >= 2:
                        values["lcom4_stateful"].append(lcom4_stateful(node))
                        values["lcom3_stateful"].append(lcom3_stateful(node))
                    if cls.nom >= rules["nom"] and cls.wmc >= rules["wmc"]:
                        large.append(
                            class_facts(
                                node,
                                name=f"{project.name}:{cls.module}.{cls.name}",
                                nom=cls.nom,
                                lcom4_value=cls.lcom4,
                            )
                        )
            for key, collected in values.items():
                if len(collected) >= MIN_VALUES:
                    distributions[key].append(
                        {f"p{q}": percentile(collected, q) for q in (50, 75, 90, 95)}
                    )
            print(f"{project.name:<17} scanned", flush=True)

    percentiles = {
        key: {
            stat: median_of(entry[stat] for entry in entries)
            for stat in ("p50", "p75", "p90", "p95")
        }
        | {"projects": len(entries)}
        for key, entries in distributions.items()
    }
    thresholds = {
        "R3": round(percentiles["lcom4_stateful"]["p90"]),
        "R4": round(percentiles["lcom3_stateful"]["p90"]),
    }
    current = {c.name for c in large if c.lcom4 >= CURRENT_LCOM4}
    results = {}
    for candidate in CANDIDATES:
        threshold = thresholds.get(candidate)

        def fires(c, candidate=candidate, threshold=threshold):
            return candidate_fires(c, candidate, threshold)

        key = {"R3": "lcom4_stateful", "R4": "lcom3_stateful"}.get(candidate)
        p = percentiles[key] if key else {"p75": None, "p90": None, "p95": None}
        fired = [c for c in large if fires(c)]
        new = [c for c in fired if c.name not in current]
        lost = [c for c in large if c.name in current and not fires(c)]
        results[candidate] = {
            "threshold": threshold,
            "fired": len(fired),
            "new": len(new),
            "lost": len(lost),
            "fired_stateless": sum(1 for c in fired if c.stateless_share >= STATELESS_SHARE),
            "fired_interfaces": sum(1 for c in fired if c.stub_share >= EXCLUSION_SHARE),
            "rejections": rejections(large, fires, candidate, p["p75"], p["p90"], p["p95"]),
            "new_examples": [c.name for c in sorted(new, key=lambda c: -c.nom)[:10]],
            "lost_examples": [c.name for c in sorted(lost, key=lambda c: -c.nom)[:10]],
        }

    summary = {
        "schema_version": SCHEMA_VERSION,
        "min_values": MIN_VALUES,
        "large_classes": len(large),
        "current_fired": len(current),
        "current_interfaces": sum(
            1 for c in large if c.name in current and c.stub_share >= EXCLUSION_SHARE
        ),
        "percentiles": percentiles,
        "candidates": results,
        "large": [asdict(c) for c in large],
    }
    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    JSON_FILE.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    TABLES_FILE.write_text(render_tables(summary), encoding="utf-8")
    print(render_tables(summary))
    return 0


def render_tables(summary: dict) -> str:
    lines = [
        "<!-- Üretildi: experiments/hardening/stateless_gate.py. Elle düzenlemeyin. -->",
        "",
        f"Scan şeması {summary['schema_version']}. Boyut koşulunu geçen "
        f"{summary['large_classes']} sınıf; bugünkü kapı {summary['current_fired']} "
        f"sınıfta ateşliyor, {summary['current_interfaces']}'ü taslak arayüz.",
        "",
        "## Dağılım (en az iki durumlu metot adı olan sınıflar)",
        "",
        "| Ölçü | proje | p50 | p75 | p90 | p95 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, p in summary["percentiles"].items():
        lines.append(
            f"| {key} | {p['projects']} | {p['p50']:g} | {p['p75']:g} | {p['p90']:g} | "
            f"{p['p95']:g} |"
        )
    lines += [
        "",
        "## Adaylar",
        "",
        "| Aday | eşik | ateşler | yeni | kayıp | ateşleyen içinde durumsuz "
        "| ateşleyen taslak arayüz | çürütme |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, r in summary["candidates"].items():
        threshold = "-" if r["threshold"] is None else r["threshold"]
        reasons = ", ".join(r["rejections"]) or "yok"
        lines.append(
            f"| {name} | {threshold} | {r['fired']} | {r['new']} | {r['lost']} | "
            f"{r['fired_stateless']} | {r['fired_interfaces']} | {reasons} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
