"""Metrik dağılımı: kalibrasyon korpusunda her metriğin olağan değerleri.

Sertleştirme Blok 1b, madde 2. Eşikler bu dağılımdan türetilecek; bu betik
eşikleri **değiştirmez**, mevcut varsayılanların gerçek kodda nereye düştüğünü
gösterir. Eşiği değiştirmek tablodan sonraki ayrı bir karardır.

    python experiments/hardening/distribution.py

Önce `corpus.py fetch`. Çıktı: `results/metric-distribution.json` (tekrar
üretildiğinde birebir aynı) ve `results/metric-distribution-tables.md`
(aynı veriden üretilmiş tablolar; belge bunları alıntılar).

**Ağırlıklandırma.** Sınıfların %47'si iki projeden geliyor (netbox, yt-dlp),
ikisi de tek bir deyimin binlerce tekrarı (`corpus.md` Bulgu 1). Tüm değerleri
tek havuzda toplayıp persentil almak eşiği o deyime kalibre eder. Bu yüzden:

1. Persentiller **proje başına** hesaplanır.
2. Tür ve genel değer, projelerin o istatistiğinin **medyanıdır**.
3. Havuzlanmış persentil yalnızca karşılaştırma için yanında verilir.

**Küçük örneklem.** Bir proje bir metriğin özetine ancak o metrikte en az
`MIN_VALUES` (30) hesaplanmış değeri varsa katılır. nanoGPT'nin 6 sınıfından 99.
persentil çıkmaz. Katılan proje sayısı her satırda yazılır.

**`null`.** Hesaplanamayan değer (metotsuz sınıfta LCOM4, attribute'suz sınıfta
DAM, annotation'sız sınıfta CAM) dağılıma girmez; payı ayrı sütundadır.
"""

from __future__ import annotations

import json
import statistics
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from compare_cohesion import god_class_gate
from compare_radon import HERE, PROJECTS_FILE, load_projects
from corpus import PROJECT_TYPES, accuracy_set_mismatches, load_corpus, project_config

JSON_FILE = HERE / "results" / "metric-distribution.json"
TABLES_FILE = HERE / "results" / "metric-distribution-tables.md"

MIN_VALUES = 30
PERCENTILES = (50, 75, 90, 95, 99)

#: (rapor alanı, gösterim adı, birim)
FUNCTION_METRICS = (
    ("cyclomatic_complexity", "CC", "function"),
    ("loc", "LOC", "function"),
    ("param_count", "PARAMS", "function"),
    ("max_nesting", "NESTING", "function"),
)
CLASS_METRICS = (
    ("nom", "NOM", "class"),
    ("wmc", "WMC", "class"),
    ("lcom4", "LCOM4", "class"),
    ("dcc", "DCC", "class"),
    ("dam", "DAM", "class"),
    ("cam", "CAM", "class"),
)
MODULE_METRICS = (
    ("ca", "Ca", "module"),
    ("ce", "Ce", "module"),
    ("instability", "I", "module"),
)
ALL_METRICS = FUNCTION_METRICS + CLASS_METRICS + MODULE_METRICS


# --------------------------------------------------------------------------- #
# Saf istatistik — test edilir
# --------------------------------------------------------------------------- #


def percentile(values: Sequence[float], q: float) -> float | None:
    """Doğrusal interpolasyonlu yüzdelik (NumPy `linear` ile aynı). Boşsa `None`."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q / 100
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 4)


def exceedance(values: Sequence[float], threshold: float) -> float | None:
    """Eşiği karşılayan pay. Kural `Threshold.level` ile aynı: `değer >= eşik`."""
    if not values:
        return None
    return round(sum(1 for value in values if value >= threshold) / len(values), 4)


@dataclass
class MetricValues:
    values: list[float] = field(default_factory=list)
    nulls: int = 0

    def add(self, value: float | None) -> None:
        if value is None:
            self.nulls += 1
        else:
            self.values.append(value)

    @property
    def total(self) -> int:
        return len(self.values) + self.nulls


def summarise_values(collected: MetricValues) -> dict:
    """Bir projenin tek metriği için özet."""
    values = collected.values
    summary: dict = {
        "n": len(values),
        "null_share": round(collected.nulls / collected.total, 4) if collected.total else None,
        "eligible": len(values) >= MIN_VALUES,
    }
    for q in PERCENTILES:
        summary[f"p{q}"] = percentile(values, q)
    summary["max"] = max(values) if values else None
    return summary


def median_of(entries: Iterable[float | None]) -> float | None:
    present = [entry for entry in entries if entry is not None]
    return round(statistics.median(present), 4) if present else None


def aggregate(project_summaries: dict[str, dict], names: Iterable[str], key: str) -> dict:
    """Projelerin özetlerinden medyan; yalnız `eligible` projeler katılır."""
    eligible = [project_summaries[name] for name in names if project_summaries[name]["eligible"]]
    result: dict = {"projects": len(eligible)}
    for stat in [f"p{q}" for q in PERCENTILES] + ["null_share"]:
        result[stat] = median_of(entry[stat] for entry in eligible)
    return result


# --------------------------------------------------------------------------- #
# Toplama
# --------------------------------------------------------------------------- #


def collect_report(report) -> dict[str, MetricValues]:
    """Bir tarama raporundan metrik değerleri, birim türüne göre."""
    collected = {name: MetricValues() for name, _, _ in ALL_METRICS}
    for module in report.modules:
        for name, _, _ in MODULE_METRICS:
            collected[name].add(getattr(module, name))
        functions = list(module.functions)
        for cls in module.classes:
            functions.extend(cls.methods)
            for name, _, _ in CLASS_METRICS:
                collected[name].add(getattr(cls, name))
        for function in functions:
            for name, _, _ in FUNCTION_METRICS:
                collected[name].add(getattr(function, name))
    return collected


def default_thresholds() -> list[dict]:
    """Varsayılan config'teki eşikler; config'le senkron kalsın diye oradan okunur."""
    from rlens.config import DEFAULTS

    thresholds = DEFAULTS["thresholds"]
    rows = []
    for field_name, label, _ in FUNCTION_METRICS + CLASS_METRICS:
        key = {"param_count": "max_params", "max_nesting": "max_nesting"}.get(
            field_name, field_name
        )
        spec = thresholds.get(key)
        if not spec:
            continue
        for level in ("warn", "critical"):
            if level in spec:
                rows.append(
                    {"metric": field_name, "label": label, "level": level, "value": spec[level]}
                )
    rows.append(
        {
            "metric": "loc",
            "label": "LOC",
            "level": "long_method",
            "value": DEFAULTS["smells"]["long_method"]["loc"],
        }
    )
    return rows


def main() -> int:
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

    thresholds = default_thresholds()
    per_project: dict[str, dict] = {}
    pooled = {name: MetricValues() for name, _, _ in ALL_METRICS}
    gates: dict[str, dict] = {}
    smells: dict[str, dict] = {}

    with tempfile.TemporaryDirectory() as workdir:
        for project in corpus:
            config = project_config(project, Path(workdir))
            result = scan_project_with_sources(project.scan_root, config)
            collected = collect_report(result.report)
            entry = {"type": project.type, "metrics": {}, "exceedance": {}}
            for name, _, _ in ALL_METRICS:
                entry["metrics"][name] = summarise_values(collected[name])
                pooled[name].values.extend(collected[name].values)
                pooled[name].nulls += collected[name].nulls
            for row in thresholds:
                key = f"{row['label']}>={row['value']:g} ({row['level']})"
                entry["exceedance"][key] = exceedance(collected[row["metric"]].values, row["value"])
            gate = god_class_gate(result.modules, DEFAULTS["smells"]["god_class"])
            gates[project.name] = {k: v for k, v in gate.items() if k != "examples"}
            counts: dict[str, int] = {}
            for smell in result.report.iter_smells():
                counts[smell["label"]] = counts.get(smell["label"], 0) + 1
            smells[project.name] = {
                "counts": dict(sorted(counts.items())),
                "functions": collected["loc"].total,
                "classes": collected["nom"].total,
            }
            per_project[project.name] = entry
            print(f"{project.name:<17} scanned", flush=True)

    names_by_type = {kind: [p.name for p in corpus if p.type == kind] for kind in PROJECT_TYPES}
    all_names = [p.name for p in corpus]
    summary: dict = {
        "schema_version": _schema_version(),
        "min_values": MIN_VALUES,
        "metrics": {},
        "thresholds": [],
        "god_class_gate": {},
        "smell_rates": {},
    }
    for name, label, unit in ALL_METRICS:
        project_summaries = {p: per_project[p]["metrics"][name] for p in all_names}
        row = {
            "label": label,
            "unit": unit,
            "all": aggregate(project_summaries, all_names, name),
            "by_type": {
                kind: aggregate(project_summaries, names, name)
                for kind, names in names_by_type.items()
            },
            "pooled": {f"p{q}": percentile(pooled[name].values, q) for q in PERCENTILES}
            | {"n": len(pooled[name].values)},
        }
        summary["metrics"][name] = row

    for row in thresholds:
        key = f"{row['label']}>={row['value']:g} ({row['level']})"
        eligible = [p for p in all_names if per_project[p]["metrics"][row["metric"]]["eligible"]]
        shares = [per_project[p]["exceedance"][key] for p in eligible]
        by_type = {}
        for kind, names in names_by_type.items():
            kind_shares = [per_project[p]["exceedance"][key] for p in names if p in eligible]
            by_type[kind] = median_of(kind_shares)
        pooled_share = exceedance(pooled[row["metric"]].values, row["value"])
        summary["thresholds"].append(
            {
                **row,
                "key": key,
                "projects": len(eligible),
                "median_exceedance": median_of(shares),
                "min_exceedance": min(shares) if shares else None,
                "max_exceedance": max(shares) if shares else None,
                "by_type": by_type,
                "pooled_exceedance": pooled_share,
            }
        )

    gate_keys = ("size_qualified", "fired", "gated_by_lcom4", "gated_only_because_of_call_edges")
    for kind, names in names_by_type.items():
        summary["god_class_gate"][kind] = {
            k: sum(gates[name][k] for name in names) for k in gate_keys
        }
    summary["god_class_gate"]["all"] = {
        k: sum(summary["god_class_gate"][kind][k] for kind in PROJECT_TYPES) for k in gate_keys
    }

    labels = sorted({label for entry in smells.values() for label in entry["counts"]})
    for kind, names in names_by_type.items():
        rates = {}
        for label in labels:
            per_project_rates = []
            for name in names:
                denominator = (
                    smells[name]["classes"]
                    if label in ("god_class", "data_class")
                    else smells[name]["functions"]
                )
                if denominator:
                    per_project_rates.append(
                        1000 * smells[name]["counts"].get(label, 0) / denominator
                    )
            rates[label] = median_of(per_project_rates)
        summary["smell_rates"][kind] = rates

    summary["per_project"] = per_project
    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    JSON_FILE.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    TABLES_FILE.write_text(render_tables(summary), encoding="utf-8")
    print(render_tables(summary))
    return 0


def _schema_version() -> int:
    from rlens.analysis.model import SCHEMA_VERSION

    return SCHEMA_VERSION


# --------------------------------------------------------------------------- #
# Tablolar
# --------------------------------------------------------------------------- #


def _fmt(value: float | None, share: bool = False) -> str:
    if value is None:
        return "—"
    if share:
        return f"%{value * 100:.1f}"
    return f"{value:g}" if float(value).is_integer() else f"{value:.2f}"


def render_tables(summary: dict) -> str:
    lines = [
        "<!-- Üretildi: experiments/hardening/distribution.py. Elle düzenlemeyin. -->",
        "",
        f"Scan şeması {summary['schema_version']}. Proje başına persentil, projelerin medyanı; "
        f"projenin katılması için metrikte en az {summary['min_values']} değer.",
        "",
        "## Dağılım — tüm korpus",
        "",
        "| Metrik | Birim | Proje | p50 | p75 | p90 | p95 | p99 | null | havuz p90 | havuz p99 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["metrics"].values():
        a = row["all"]
        lines.append(
            f"| {row['label']} | {row['unit']} | {a['projects']} | "
            f"{_fmt(a['p50'])} | {_fmt(a['p75'])} | {_fmt(a['p90'])} | "
            f"{_fmt(a['p95'])} | {_fmt(a['p99'])} | {_fmt(a['null_share'], True)} | "
            f"{_fmt(row['pooled']['p90'])} | {_fmt(row['pooled']['p99'])} |"
        )
    lines += [
        "",
        "## p90 tür bazında",
        "",
        "| Metrik | " + " | ".join(PROJECT_TYPES) + " |",
        "|---|" + "---:|" * len(PROJECT_TYPES),
    ]
    for row in summary["metrics"].values():
        cells = []
        for kind in PROJECT_TYPES:
            entry = row["by_type"][kind]
            cells.append(f"{_fmt(entry['p90'])} ({entry['projects']})")
        lines.append(f"| {row['label']} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Mevcut eşikler — eşiği karşılayan pay",
        "",
        "Proje başına pay; medyan ve aralık. Eşiğin denk geldiği persentil ≈ 100 − medyan pay.",
        "",
        "| Eşik | Proje | medyan | min | max | " + " | ".join(PROJECT_TYPES) + " | havuz |",
        "|---|---:|---:|---:|---:|" + "---:|" * len(PROJECT_TYPES) + "---:|",
    ]
    for row in summary["thresholds"]:
        cells = " | ".join(_fmt(row["by_type"][kind], True) for kind in PROJECT_TYPES)
        lines.append(
            f"| {row['key']} | {row['projects']} | {_fmt(row['median_exceedance'], True)} | "
            f"{_fmt(row['min_exceedance'], True)} | "
            f"{_fmt(row['max_exceedance'], True)} | {cells} | "
            f"{_fmt(row['pooled_exceedance'], True)} |"
        )
    lines += [
        "",
        "## `god_class` kapısı (K4)",
        "",
        "| Tür | Boyut koşulunu geçen | Ateşlendi | LCOM4'te elendi "
        "| Yalnız çağrı kenarı yüzünden |",
        "|---|---:|---:|---:|---:|",
    ]
    for kind, gate in summary["god_class_gate"].items():
        lines.append(
            f"| {kind} | {gate['size_qualified']} | {gate['fired']} | {gate['gated_by_lcom4']} | "
            f"{gate['gated_only_because_of_call_edges']} |"
        )
    labels = sorted({label for rates in summary["smell_rates"].values() for label in rates})
    lines += [
        "",
        "## Koku oranları — 1000 birim başına, projelerin medyanı",
        "",
        "`god_class`, `data_class`: 1000 sınıf başına; diğerleri 1000 fonksiyon başına.",
        "",
        "| Koku | " + " | ".join(PROJECT_TYPES) + " |",
        "|---|" + "---:|" * len(PROJECT_TYPES),
    ]
    for label in labels:
        cells = " | ".join(_fmt(summary["smell_rates"][kind].get(label)) for kind in PROJECT_TYPES)
        lines.append(f"| {label} | {cells} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
