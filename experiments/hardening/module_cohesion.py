"""Modül düzeyi kohezyon adayı (v2.2 §3): modülün birimleri ne kadar bağlı.

Ön kayıt ve çürütme koşulları `module-cohesion.md`'de, ölçümden **önce**
yazıldı. Aday fonksiyonlar burada durur; kabul edilirse araca taşınır.

    python experiments/hardening/module_cohesion.py

Önce `corpus.py fetch`. Çıktı: `results/module-cohesion.json`,
`results/module-cohesion-tables.md`; tekrar üretildiğinde birebir aynı.
"""

from __future__ import annotations

import ast
import json
import statistics
import sys
import tempfile
from math import comb
from pathlib import Path

from compare_radon import HERE, PROJECTS_FILE, load_projects
from corpus import PROJECT_TYPES, accuracy_set_mismatches, load_corpus, project_config
from distribution import MIN_VALUES, median_of, percentile

from rlens.analysis.class_metrics import iter_module_classes
from rlens.analysis.func_metrics import iter_module_functions
from rlens.analysis.imports import _absolute_name, _Resolver, root_package_name

JSON_FILE = HERE / "results" / "module-cohesion.json"
TABLES_FILE = HERE / "results" / "module-cohesion-tables.md"

R_CEILING = 0.95
MIN_PAIRS = 100
DEGENERATE_SHARE = 0.5
VARIANTS = {"mcoh": True, "mcoh_s": False}
"""Değişken → kullanım kenarı dahil mi."""


# --------------------------------------------------------------------------- #
# Aday ölçü — test edilir
# --------------------------------------------------------------------------- #


def _units(tree: ast.Module) -> list[ast.AST]:
    return [*iter_module_functions(tree), *iter_module_classes(tree)]


def module_globals(tree: ast.Module) -> set[str]:
    """Modülün en üst düzeyinde atamayla bağlanan adlar; birim adları hariç."""
    names: set[str] = set()
    for statement in tree.body:
        targets: list[ast.AST] = []
        if isinstance(statement, ast.Assign):
            targets = statement.targets
        elif isinstance(statement, ast.AnnAssign | ast.AugAssign):
            targets = [statement.target]
        for target in targets:
            names |= {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}
    return names - {unit.name for unit in _units(tree)}


def _names_used(unit: ast.AST) -> set[str]:
    """Birimin gövdesinde (dekoratör ve varsayılanlar dahil) geçen bütün adlar.

    `global x` bildirimi de adı kullanır.
    """
    used = {n.id for n in ast.walk(unit) if isinstance(n, ast.Name)}
    for node in ast.walk(unit):
        if isinstance(node, ast.Global | ast.Nonlocal):
            used |= set(node.names)
    used.discard(unit.name)
    return used


def components(tree: ast.Module, *, with_usage: bool) -> list[set[str]] | None:
    """Bağlı bileşenler (birim adları kümeleri); ikiden az birimde `None`."""
    units = _units(tree)
    names = [unit.name for unit in units]
    if len(set(names)) < 2:
        return None
    parent = {name: name for name in names}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def union(a: str, b: str) -> None:
        parent[find(b)] = find(a)

    globals_ = module_globals(tree)
    owners: dict[str, list[str]] = {}
    unit_names = set(names)
    for unit in units:
        used = _names_used(unit)
        for name in used & globals_:
            owners.setdefault(name, []).append(unit.name)
        if with_usage:
            for other in used & unit_names:
                union(unit.name, other)
    for sharers in owners.values():
        for other in sharers[1:]:
            union(sharers[0], other)
    groups: dict[str, set[str]] = {}
    for name in parent:
        groups.setdefault(find(name), set()).add(name)
    return list(groups.values())


def expected_touched(sizes: list[int], chosen: int) -> float:
    """`chosen` birim rastgele seçilseydi dokunulacak bileşen sayısının beklentisi."""
    total = sum(sizes)
    ways = comb(total, chosen)
    return sum(1 - comb(total - size, chosen) / ways for size in sizes)


def touched(groups: list[set[str]], names: set[str]) -> int:
    return sum(1 for group in groups if group & names)


# --------------------------------------------------------------------------- #
# Toplama
# --------------------------------------------------------------------------- #


def importer_pairs(modules, root: Path) -> list[tuple[str, str, set[str]]]:
    """(kullanan modül, kullanılan modül, alınan adlar) — `from M import ...`."""
    resolver = _Resolver(tuple(m.module for m in modules), root_package_name(root))
    pairs: list[tuple[str, str, set[str]]] = []
    for module in modules:
        taken: dict[str, set[str]] = {}
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            absolute = _absolute_name(module, node)
            target, _ = resolver.resolve(absolute or "")
            if target is None or target == module.module:
                continue
            taken.setdefault(target, set()).update(alias.name for alias in node.names)
        pairs += [(module.module, target, names) for target, names in sorted(taken.items())]
    return pairs


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
    ratios: dict[str, list[float]] = {v: [] for v in VARIANTS}
    # Sonradan eklenen (ön kayıtta yok): kullanan M'nin bütün birimlerini
    # alıyorsa seçim yoktur, R tanım gereği 1'dir. Bilgi taşıyan çiftler ayrıca.
    informative: dict[str, list[float]] = {v: [] for v in VARIANTS}
    with tempfile.TemporaryDirectory() as workdir:
        for project in corpus:
            result = scan_project_with_sources(
                project.scan_root, project_config(project, Path(workdir))
            )
            groups_by: dict[str, dict[str, list[set[str]]]] = {v: {} for v in VARIANTS}
            entry: dict = {"type": project.type}
            for variant, with_usage in VARIANTS.items():
                values: list[int] = []
                fragmented = 0
                for module in result.modules:
                    groups = components(module.tree, with_usage=with_usage)
                    if groups is None:
                        continue
                    groups_by[variant][module.module] = groups
                    values.append(len(groups))
                    fragmented += len(groups) == sum(len(g) for g in groups)
                eligible = len(values) >= MIN_VALUES
                entry[variant] = {
                    "modules": len(values),
                    "p50": percentile(values, 50),
                    "p90": percentile(values, 90),
                    "spread": (percentile(values, 10) < percentile(values, 90))
                    if eligible
                    else None,
                    "fragmented_share": round(fragmented / len(values), 4) if values else None,
                }
            pair_count = {v: 0 for v in VARIANTS}
            for _, target, names in importer_pairs(result.modules, project.scan_root):
                for variant in VARIANTS:
                    groups = groups_by[variant].get(target)
                    if not groups or len(groups) < 2:
                        continue
                    units = set().union(*groups)
                    chosen = names & units
                    if len(chosen) < 2:
                        continue
                    expected = expected_touched([len(g) for g in groups], len(chosen))
                    ratio = touched(groups, chosen) / expected
                    ratios[variant].append(ratio)
                    if len(chosen) < len(units):
                        informative[variant].append(ratio)
                    pair_count[variant] += 1
            for variant in VARIANTS:
                entry[variant]["pairs"] = pair_count[variant]
            projects[project.name] = entry
            print(f"{project.name:<17} scanned", flush=True)

    summary: dict = {"schema_version": SCHEMA_VERSION, "variants": {}, "per_project": projects}
    for variant in VARIANTS:
        rows = [p[variant] for p in projects.values()]
        eligible = [r for r in rows if r["spread"] is not None]
        median_ratio = round(statistics.median(ratios[variant]), 4) if ratios[variant] else None
        fragmented = median_of(r["fragmented_share"] for r in rows)
        spread = sum(1 for r in eligible if r["spread"])
        summary["variants"][variant] = {
            "pairs": len(ratios[variant]),
            "median_ratio": median_ratio,
            "share_below_one": round(
                sum(1 for r in ratios[variant] if r < 1) / len(ratios[variant]), 4
            )
            if ratios[variant]
            else None,
            "median_fragmented_share": fragmented,
            "posthoc_informative_pairs": len(informative[variant]),
            "posthoc_informative_median_ratio": round(statistics.median(informative[variant]), 4)
            if informative[variant]
            else None,
            "posthoc_informative_below_one": round(
                sum(1 for r in informative[variant] if r < 1) / len(informative[variant]), 4
            )
            if informative[variant]
            else None,
            "spread_projects": spread,
            "eligible_projects": len(eligible),
            "by_type_p90": {
                kind: median_of(p[variant]["p90"] for p in projects.values() if p["type"] == kind)
                for kind in PROJECT_TYPES
            },
            "refutations": {
                "a": median_ratio is None
                or len(ratios[variant]) < MIN_PAIRS
                or median_ratio >= R_CEILING,
                "b": fragmented is not None and fragmented > DEGENERATE_SHARE,
                "c": spread < len(eligible) / 2,
            },
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
    lines = [
        "<!-- Üretildi: experiments/hardening/module_cohesion.py. Elle düzenlemeyin. -->",
        "",
        f"Scan şeması {summary['schema_version']}. MCOH: durum + kullanım kenarı; "
        "MCOH-S: yalnız durum kenarı.",
        "",
        "## Ön kayıtlı koşullar",
        "",
        "| Değişken | çift | R medyanı | R < 1 payı | tamamen dağınık (medyan) | yayılım "
        "| (a) | (b) | (c) |",
        "|---|---:|---:|---:|---:|---|---|---|---|",
    ]
    for variant, v in summary["variants"].items():
        r = v["refutations"]
        mark = {True: "ret", False: "geçti"}
        lines.append(
            f"| {variant} | {v['pairs']} | {v['median_ratio']} | {_pct(v['share_below_one'])} | "
            f"{_pct(v['median_fragmented_share'])} | {v['spread_projects']}/"
            f"{v['eligible_projects']} | {mark[r['a']]} | {mark[r['b']]} | {mark[r['c']]} |"
        )
    lines += [
        "",
        "## Sonradan eklenen analiz (ön kayıtta yok)",
        "",
        "Kullanan modül M'nin bütün birimlerini alıyorsa seçim yoktur ve R tanım gereği 1'dir. "
        "Yalnız seçim yapılan çiftler:",
        "",
        "| Değişken | bilgi taşıyan çift | R medyanı | R < 1 payı |",
        "|---|---:|---:|---:|",
    ]
    for variant, v in summary["variants"].items():
        lines.append(
            f"| {variant} | {v['posthoc_informative_pairs']} | "
            f"{v['posthoc_informative_median_ratio']} | "
            f"{_pct(v['posthoc_informative_below_one'])} |"
        )
    lines += [
        "",
        "## Proje başına",
        "",
        "| Proje | tür | modül | MCOH p50 | MCOH p90 | MCOH dağınık | MCOH-S p50 | MCOH-S p90 "
        "| MCOH-S dağınık | çift (MCOH) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, p in summary["per_project"].items():
        a, s = p["mcoh"], p["mcoh_s"]
        lines.append(
            f"| {name} | {p['type']} | {a['modules']} | {a['p50']} | {a['p90']} | "
            f"{_pct(a['fragmented_share'])} | {s['p50']} | {s['p90']} | "
            f"{_pct(s['fragmented_share'])} | {a['pairs']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
