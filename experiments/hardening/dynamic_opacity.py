"""Dinamik opaklık adayı (v2.2 §3): statik analizin kör kaldığı noktalar.

Ön kayıt ve çürütme koşulları `dynamic-opacity.md`'de, ölçümden **önce**
yazıldı. Ölçü fonksiyonları K13'ten beri aracın kendisinden gelir
(`func_metrics.dynamic_sites`, `class_metrics.has_attribute_hooks`).

    python experiments/hardening/dynamic_opacity.py measure   # ~2 dk
    python experiments/hardening/dynamic_opacity.py summary   # (a) kararları dolunca

`measure` şunları yazar: `results/dynamic-opacity.json`,
`results/dynamic-opacity-tables.md`, elle kesinlik örneklemi
`dynamic-sample.json` (yoksa) ve boş karar şablonu `dynamic-verdicts.json`
(yoksa). Örneklem `--force` olmadan yeniden çekilmez.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

from compare_radon import HERE, PROJECTS_FILE, load_projects
from corpus import PROJECT_TYPES, accuracy_set_mismatches, load_corpus, project_config
from distribution import median_of

from rlens.analysis.class_metrics import (
    class_methods,
    has_attribute_hooks,
    iter_module_classes,
)
from rlens.analysis.func_metrics import dynamic_sites, iter_module_functions

JSON_FILE = HERE / "results" / "dynamic-opacity.json"
TABLES_FILE = HERE / "results" / "dynamic-opacity-tables.md"
SAMPLE_FILE = HERE / "dynamic-sample.json"
VERDICTS_FILE = HERE / "dynamic-verdicts.json"

SEED = 20260922
SAMPLE_SIZE = 30
PRECISION_FLOOR = 24
METAPROGRAMMING = ("attrs", "pydantic", "sqlalchemy")
TOKENS = {
    "getattr": "getattr",
    "setattr": "setattr",
    "delattr": "delattr",
    "hasattr": "hasattr",
    "eval": "eval",
    "exec": "exec",
    "import": "import",
    "kwargs": "**",
}


# --------------------------------------------------------------------------- #
# Aday ölçü — test edilir
# --------------------------------------------------------------------------- #


def verdict_problems(sample: list[dict], verdicts: dict) -> list[str]:
    problems = []
    for item in sample:
        entry = verdicts.get(item["id"])
        if entry is None or entry.get("verdict") not in ("opaque", "resolvable"):
            problems.append(f"{item['id']}: verdict must be opaque or resolvable")
        elif not entry.get("reason"):
            problems.append(f"{item['id']}: a verdict needs a reason")
    return problems


def concentration(rates: dict[str, float], median: float) -> dict:
    """(b): metaprogramlama kütüphanelerinden kaçı korpus medyanının üstünde."""
    above = [name for name in METAPROGRAMMING if rates.get(name, 0) > median]
    return {"above": above, "refuted": len(above) < 2}


# --------------------------------------------------------------------------- #
# Toplama
# --------------------------------------------------------------------------- #


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
    token_misses = 0
    with tempfile.TemporaryDirectory() as workdir:
        for project in corpus:
            result = scan_project_with_sources(
                project.scan_root, project_config(project, Path(workdir))
            )
            kinds = dict.fromkeys(TOKENS, 0)
            functions = with_sites = classes = hooked = 0
            for module in result.modules:
                lines = module.source.splitlines()
                units = [(f, None) for f in iter_module_functions(module.tree)]
                for cls in iter_module_classes(module.tree):
                    classes += 1
                    hooked += has_attribute_hooks(cls)
                    units += [(m, cls.name) for m in class_methods(cls)]
                for function, owner in units:
                    functions += 1
                    sites = dynamic_sites(function)
                    with_sites += bool(sites)
                    for line, kind in sites:
                        kinds[kind] += 1
                        text = lines[line - 1] if line <= len(lines) else ""
                        if TOKENS[kind] not in text:
                            token_misses += 1
                        qualified = f"{owner}.{function.name}" if owner else function.name
                        pool.append(
                            {
                                "id": f"{project.name}:{module.module}:{qualified}:{line}:{kind}",
                                "project": project.name,
                                "file": module.relative_path,
                                "line": line,
                                "function": qualified,
                                "kind": kind,
                            }
                        )
            total = sum(kinds.values())
            projects[project.name] = {
                "type": project.type,
                "functions": functions,
                "sites": total,
                "rate_per_1000": round(1000 * total / functions, 2) if functions else None,
                "functions_with_sites": round(with_sites / functions, 4) if functions else None,
                "kinds": kinds,
                "classes": classes,
                "hooked_classes": hooked,
            }
            print(f"{project.name:<17} scanned", flush=True)

    rates = {n: p["rate_per_1000"] for n, p in projects.items() if p["rate_per_1000"] is not None}
    median = median_of(rates.values())
    by_type = {
        kind: median_of(p["rate_per_1000"] for p in projects.values() if p["type"] == kind)
        for kind in PROJECT_TYPES
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
        "median_rate": median,
        "by_type": by_type,
        "token_misses": token_misses,
        "sites": len(pool),
        "concentration": concentration(rates, median),
        "per_project": projects,
    }
    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    JSON_FILE.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    TABLES_FILE.write_text(render_tables(summary), encoding="utf-8")
    sys.stdout.reconfigure(errors="replace")
    print(render_tables(summary))
    return 1 if token_misses else 0


def summary() -> int:
    sample = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
    verdicts = json.loads(VERDICTS_FILE.read_text(encoding="utf-8"))
    problems = verdict_problems(sample, verdicts)
    if problems:
        print("verdicts incomplete; no precision computed:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    opaque = sum(1 for item in sample if verdicts[item["id"]]["verdict"] == "opaque")
    data = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    data["precision"] = {
        "sample": len(sample),
        "opaque": opaque,
        "precision": round(opaque / len(sample), 4),
        "refuted": opaque < PRECISION_FLOOR,
    }
    JSON_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    TABLES_FILE.write_text(render_tables(data), encoding="utf-8")
    print(json.dumps(data["precision"], indent=2))
    return 0


def render_tables(summary: dict) -> str:
    lines = [
        "<!-- Üretildi: experiments/hardening/dynamic_opacity.py. Elle düzenlemeyin. -->",
        "",
        f"Scan şeması {summary['schema_version']}. Oran: 1000 fonksiyon başına opak nokta. "
        f"Toplam {summary['sites']} nokta; korpus medyanı {summary['median_rate']}.",
        "",
        "| Proje | tür | fonksiyon | nokta | 1000 başına | noktası olan fonksiyon | "
        + " | ".join(TOKENS)
        + " | kancalı sınıf |",
        "|---|---|---:|---:|---:|---:|" + "---:|" * len(TOKENS) + "---:|",
    ]
    for name, p in sorted(
        summary["per_project"].items(), key=lambda i: -(i[1]["rate_per_1000"] or 0)
    ):
        share = (
            "-" if p["functions_with_sites"] is None else f"%{p['functions_with_sites'] * 100:.1f}"
        )
        lines.append(
            f"| {name} | {p['type']} | {p['functions']} | {p['sites']} | {p['rate_per_1000']} | "
            f"{share} | "
            + " | ".join(str(p["kinds"][k]) for k in TOKENS)
            + f" | {p['hooked_classes']}/{p['classes']} |"
        )
    c = summary["concentration"]
    lines += [
        "",
        "## Tür medyanları (betimsel)",
        "",
        "| " + " | ".join(summary["by_type"]) + " |",
        "|" + "---:|" * len(summary["by_type"]),
        "| " + " | ".join(str(v) for v in summary["by_type"].values()) + " |",
        "",
        "## Ön kayıtlı koşullar",
        "",
        f"- (b) medyanın üstündeki metaprogramlama kütüphaneleri: "
        f"{', '.join(c['above']) or 'yok'} → ret: **{'evet' if c['refuted'] else 'hayır'}**",
        f"- (c) belirteci satırında bulunmayan nokta: **{summary['token_misses']}**",
    ]
    if "precision" in summary:
        p = summary["precision"]
        lines.append(
            f"- (a) elle kesinlik {p['opaque']}/{p['sample']} < {PRECISION_FLOOR}: "
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
