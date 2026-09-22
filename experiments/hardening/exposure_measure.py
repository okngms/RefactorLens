"""DAM'ın varyans ayrıştırması ve fiili açıklık (EXP) adayı (v2.2, K7'nin sorusu).

Ön kayıt ve çürütme koşulları `exposure.md`'de, ölçümden **önce** yazıldı.
Aday fonksiyonlar burada durur; kabul edilirse araca taşınır.

    python experiments/hardening/exposure_measure.py measure   # ~3 dk
    python experiments/hardening/exposure_measure.py summary   # (d) kararları dolunca

`measure` şunları yazar: `results/exposure.json`, `results/exposure-tables.md`,
elle kesinlik örneklemi `exposure-sample.json` (yoksa) ve boş karar şablonu
`exposure-verdicts.json` (yoksa). Örneklem `--force` olmadan yeniden çekilmez.
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
from corpus import accuracy_set_mismatches, load_corpus, project_config
from coverage import class_nodes
from distribution import MIN_VALUES, median_of, percentile

from rlens.analysis.class_metrics import assigned_attributes, iter_module_classes

JSON_FILE = HERE / "results" / "exposure.json"
TABLES_FILE = HERE / "results" / "exposure-tables.md"
SAMPLE_FILE = HERE / "exposure-sample.json"
VERDICTS_FILE = HERE / "exposure-verdicts.json"

SEED = 20260922
ETA_CAP = 200
SAMPLE_SIZE = 30
PRECISION_FLOOR = 24
DAM_SILENT = ("fastapi", "pipx", "healthchecks", "netbox", "saleor", "mealie", "yolov5")
MIN_GROUP = 20
INTERNAL_RECEIVERS = frozenset({"self", "cls"})


# --------------------------------------------------------------------------- #
# Aday ölçü — test edilir
# --------------------------------------------------------------------------- #


def attribute_index(trees: list[tuple[str, ast.Module]]) -> dict[str, set[tuple[str, str]]]:
    """Attribute adı → o adı attribute kümesinde taşıyan (modül, sınıf) çiftleri."""
    index: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for module, tree in trees:
        for node in iter_module_classes(tree):
            for name in assigned_attributes(node):
                index[name].add((module, node.name))
    return index


def _is_external(node: ast.Attribute) -> bool:
    return not (isinstance(node.value, ast.Name) and node.value.id in INTERNAL_RECEIVERS)


def external_attribute_names(trees: list[tuple[str, ast.Module]]) -> set[str]:
    """Alıcısı `self`/`cls` olmayan bütün `X.a` erişimlerinin adları (okuma ve yazma)."""
    return {
        node.attr
        for _, tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and _is_external(node)
    }


def resolvable_attributes(node: ast.ClassDef, index: dict) -> list[str]:
    """Projede yalnızca bu sınıfın taşıdığı attribute adları."""
    return sorted(name for name in assigned_attributes(node) if len(index.get(name, ())) == 1)


def exposure(node: ast.ClassDef, index: dict, external: set[str]) -> float | None:
    """Dışarıdan erişilen çözülebilir attribute payı; çözülebilir yoksa `None`."""
    resolvable = resolvable_attributes(node, index)
    if not resolvable:
        return None
    return round(sum(1 for name in resolvable if name in external) / len(resolvable), 4)


# --------------------------------------------------------------------------- #
# İstatistik — test edilir
# --------------------------------------------------------------------------- #


def eta_squared(groups: dict[str, list[float]]) -> float | None:
    """Gruplar arası kareler toplamı / toplam kareler toplamı."""
    values = [v for group in groups.values() for v in group]
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    total = sum((v - mean) ** 2 for v in values)
    if total == 0:
        return None
    between = sum(
        len(group) * (sum(group) / len(group) - mean) ** 2 for group in groups.values() if group
    )
    return round(between / total, 4)


def naming_consistent(private: tuple[int, int], public: tuple[int, int]) -> bool | None:
    """(dışarıdan erişilen, toplam) çiftleri; `_` önekliler daha az mı erişiliyor.

    Gruplardan biri `MIN_GROUP`'tan küçükse `None` (proje uygun değil).
    """
    if private[1] < MIN_GROUP or public[1] < MIN_GROUP:
        return None
    return private[0] / private[1] < public[0] / public[1]


def verdict_problems(sample: list[dict], verdicts: dict) -> list[str]:
    problems = []
    for item in sample:
        entry = verdicts.get(item["id"])
        if entry is None or entry.get("verdict") not in ("correct", "wrong"):
            problems.append(f"{item['id']}: verdict must be correct or wrong")
        elif not entry.get("reason"):
            problems.append(f"{item['id']}: a verdict needs a reason")
    return problems


# --------------------------------------------------------------------------- #
# Toplama
# --------------------------------------------------------------------------- #


def external_accesses(trees, paths) -> dict[str, list[tuple[str, int]]]:
    """Ad → dış erişimlerin (dosya, satır) listesi; (d) örneklemi için."""
    found: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for module, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and _is_external(node):
                found[node.attr].append((paths[module], node.lineno))
    return found


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

    rng = random.Random(SEED)
    dam_groups: dict[str, list[float]] = {}
    projects: dict[str, dict] = {}
    exposed_pool: list[dict] = []
    with tempfile.TemporaryDirectory() as workdir:
        for project in corpus:
            result = scan_project_with_sources(
                project.scan_root, project_config(project, Path(workdir))
            )
            trees = [(m.module, m.tree) for m in result.modules]
            paths = {m.module: m.path for m in result.report.modules}
            index = attribute_index(trees)
            external = external_attribute_names(trees)
            accesses = external_accesses(trees, paths)
            nodes = class_nodes(result.modules)
            dam_values: list[float] = []
            exposures: list[float] = []
            attrs = resolvable = 0
            private = [0, 0]
            public = [0, 0]
            for module in result.report.modules:
                for cls in module.classes:
                    node = nodes[(cls.module, cls.name, cls.lineno)]
                    names = assigned_attributes(node)
                    if cls.dam is not None and len(names) >= 2:
                        dam_values.append(cls.dam)
                    attrs += len(names)
                    solved = resolvable_attributes(node, index)
                    resolvable += len(solved)
                    value = exposure(node, index, external)
                    if value is not None:
                        exposures.append(value)
                    for name in solved:
                        hit = name in external
                        group = private if name.startswith("_") else public
                        group[0] += hit
                        group[1] += 1
                        if hit:
                            file, line = sorted(accesses[name])[0]
                            exposed_pool.append(
                                {
                                    "id": f"{project.name}:{cls.module}:{cls.name}.{name}",
                                    "project": project.name,
                                    "class": cls.name,
                                    "owner_file": module.path,
                                    "owner_line": cls.lineno,
                                    "attribute": name,
                                    "access_file": file,
                                    "access_line": line,
                                }
                            )
            dam_groups[project.name] = dam_values
            eligible = len(exposures) >= MIN_VALUES
            projects[project.name] = {
                "type": project.type,
                "attributes": attrs,
                "resolvable_share": round(resolvable / attrs, 4) if attrs else None,
                "exposure_classes": len(exposures),
                "exposure_p10": percentile(exposures, 10),
                "exposure_p50": percentile(exposures, 50),
                "exposure_p90": percentile(exposures, 90),
                "exposure_spread": (
                    percentile(exposures, 10) != percentile(exposures, 90) if eligible else None
                ),
                "private": private,
                "public": public,
                "naming_consistent": naming_consistent(tuple(private), tuple(public)),
            }
            print(f"{project.name:<17} scanned", flush=True)

    capped = {
        name: (rng.sample(values, ETA_CAP) if len(values) > ETA_CAP else values)
        for name, values in sorted(dam_groups.items())
    }
    eta_all = eta_squared(dam_groups)
    eta_capped = eta_squared(capped)
    if eta_all is not None and eta_capped is not None and min(eta_all, eta_capped) >= 0.5:
        q1 = "desteklendi"
    elif eta_all is not None and eta_capped is not None and max(eta_all, eta_capped) < 0.3:
        q1 = "çürüdü"
    else:
        q1 = "kararsız"

    resolvable_median = median_of(
        p["resolvable_share"] for p in projects.values() if p["attributes"] >= MIN_VALUES
    )
    silent = [projects[name] for name in DAM_SILENT]
    silent_spread = sum(1 for p in silent if p["exposure_spread"])
    naming = [
        p["naming_consistent"] for p in projects.values() if p["naming_consistent"] is not None
    ]
    naming_bad = sum(1 for ok in naming if not ok)
    refutations = {
        "a": resolvable_median is None or resolvable_median < 0.5,
        "b": silent_spread < 4,
        "c": bool(naming) and naming_bad / len(naming) > 0.2,
    }

    if not SAMPLE_FILE.exists() or force:
        pool = sorted(exposed_pool, key=lambda item: item["id"])
        sample = rng.sample(pool, SAMPLE_SIZE) if len(pool) > SAMPLE_SIZE else pool
        SAMPLE_FILE.write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")
        if not VERDICTS_FILE.exists() or force:
            VERDICTS_FILE.write_text(
                json.dumps({i["id"]: {"verdict": None, "reason": ""} for i in sample}, indent=2)
                + "\n",
                encoding="utf-8",
            )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "q1": {
            "eta_squared_all": eta_all,
            "eta_squared_capped": eta_capped,
            "cap": ETA_CAP,
            "reading": q1,
        },
        "resolvable_median": resolvable_median,
        "silent_projects_with_spread": silent_spread,
        "naming_eligible": len(naming),
        "naming_inconsistent": naming_bad,
        "exposed_pool": len(exposed_pool),
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
    correct = sum(1 for item in sample if verdicts[item["id"]]["verdict"] == "correct")
    result = {
        "sample": len(sample),
        "correct": correct,
        "precision": round(correct / len(sample), 4),
        "d_refuted": correct < PRECISION_FLOOR,
    }
    print(json.dumps(result, indent=2))
    data = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    data["precision"] = result
    data["refutations"]["d"] = result["d_refuted"]
    JSON_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    TABLES_FILE.write_text(render_tables(data), encoding="utf-8")
    return 0


def _pct(value: float | None) -> str:
    return "-" if value is None else f"%{value * 100:.1f}"


def render_tables(summary: dict) -> str:
    q1 = summary["q1"]
    r = summary["refutations"]
    lines = [
        "<!-- Üretildi: experiments/hardening/exposure_measure.py. Elle düzenlemeyin. -->",
        "",
        f"Scan şeması {summary['schema_version']}.",
        "",
        "## Soru 1 — DAM'ın varyansı",
        "",
        f"- η² (bütün bilgi taşıyan sınıflar): {q1['eta_squared_all']}",
        f"- η² (proje başına en fazla {q1['cap']} sınıf): {q1['eta_squared_capped']}",
        f"- Ön kayıtlı okuma: **{q1['reading']}**",
        "",
        "## Soru 2 — EXP",
        "",
        "| Proje | tür | çözülebilir | EXP sınıf | p10 | p50 | p90 | yayılım "
        "| `_` erişilen/toplam | öneksiz erişilen/toplam |",
        "|---|---|---:|---:|---:|---:|---:|---|---:|---:|",
    ]
    for name, p in summary["per_project"].items():
        spread = {True: "evet", False: "hayır", None: "-"}[p["exposure_spread"]]
        lines.append(
            f"| {name} | {p['type']} | {_pct(p['resolvable_share'])} | {p['exposure_classes']} | "
            f"{p['exposure_p10']} | {p['exposure_p50']} | {p['exposure_p90']} | {spread} | "
            f"{p['private'][0]}/{p['private'][1]} | {p['public'][0]}/{p['public'][1]} |"
        )
    lines += [
        "",
        "## Ön kayıtlı çürütme koşulları",
        "",
        f"- (a) çözülebilir pay medyanı {_pct(summary['resolvable_median'])} < %50: "
        f"**{'evet' if r['a'] else 'hayır'}**",
        f"- (b) DAM'ın sessiz olduğu 7 projeden yayılım gösteren "
        f"{summary['silent_projects_with_spread']} < 4: **{'evet' if r['b'] else 'hayır'}**",
        f"- (c) adlandırmayla tutarsız proje {summary['naming_inconsistent']}/"
        f"{summary['naming_eligible']} > %20: **{'evet' if r['c'] else 'hayır'}**",
    ]
    if "d" in r:
        p = summary["precision"]
        lines.append(
            f"- (d) elle kesinlik {p['correct']}/{p['sample']} < {PRECISION_FLOOR}: "
            f"**{'evet' if r['d'] else 'hayır'}**"
        )
    else:
        lines.append("- (d) elle kesinlik: kararlar bekleniyor")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("measure", "summary"))
    parser.add_argument("--force", action="store_true", help="redraw the precision sample")
    args = parser.parse_args(argv)
    return measure(args.force) if args.command == "measure" else summary()


if __name__ == "__main__":
    raise SystemExit(main())
