"""PySmell'in elle verilmiş etiketleri kendi metrikleriyle yeniden üretilebiliyor mu.

v2.2 §2. Ön kayıt ve okuma kuralı `pysmell-labels.md`'de, ölçümden **önce**
yazıldı.

    python experiments/hardening/pysmell_labels.py

Depo `.cache/pysmell`'e çalışma ağacı açılmadan klonlanır (bazı dosya adları
Windows'un yol sınırını aşıyor); dosyalar `git show` ile okunur. Çıktı:
`results/pysmell-labels.json`, `results/pysmell-labels-tables.md`; tekrar
üretildiğinde birebir aynı.
"""

from __future__ import annotations

import csv
import io
import json
import math
import subprocess
import sys
from itertools import combinations

from compare_radon import HERE

REPO = "https://github.com/chenzhifei731/Pysmell"
COMMIT = "233afebac24c910be89d065ffa661ec72458a62c"
CACHE = HERE / ".cache" / "pysmell"
MANUAL_DIR = "pysmell/detection/example repository/manual inspection"
SMELLS = (
    "ComplexContainerComprehension",
    "LargeClass",
    "LongBaseClassList",
    "LongLambdaFunction",
    "LongMessageChain",
    "LongMethod",
    "LongParameterList",
    "LongScopeChaining",
    "LongTernaryConditionalExpression",
    "MultiplyNestedContainer",
)
JSON_FILE = HERE / "results" / "pysmell-labels.json"
TABLES_FILE = HERE / "results" / "pysmell-labels-tables.md"

FIXED = ("subject", "tag", "file", "lineno")
LABELS = {"experience-based": "experience", "statistics-based": "statistics"}
MIN_POSITIVES = 10


# --------------------------------------------------------------------------- #
# Saf kurallar — test edilir
# --------------------------------------------------------------------------- #


def _number(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    value = float(text)
    return int(value) if value.is_integer() else value


def parse_rows(text: str) -> tuple[list[str], list[dict]]:
    """CSV → (metrik sütunları, satırlar). Boş hücre `None`."""
    reader = csv.DictReader(io.StringIO(text))
    fields = reader.fieldnames or []
    metrics = [f for f in fields if f not in FIXED and f not in LABELS and f != "manual analysis"]
    rows = []
    for raw in reader:
        row = {metric: _number(raw[metric]) for metric in metrics}
        row["manual"] = int(raw["manual analysis"])
        for column, key in LABELS.items():
            row[key] = int(raw[column])
        rows.append(row)
    return metrics, rows


def _masks(rows: list[dict], metric: str) -> list[tuple[str, float, int]]:
    """(yön, eşik, tahmin maskesi); maskenin i. biti i. satırın tahmini.

    Eksik değer hiçbir kuralı karşılamaz.
    """
    values = sorted({r[metric] for r in rows if r[metric] is not None})
    found = []
    for direction in (">=", "<="):
        for threshold in values:
            mask = 0
            for i, row in enumerate(rows):
                value = row[metric]
                if value is None:
                    continue
                if (value >= threshold) if direction == ">=" else (value <= threshold):
                    mask |= 1 << i
            found.append((direction, threshold, mask))
    return found


def _label_mask(rows: list[dict]) -> int:
    return sum(1 << i for i, row in enumerate(rows) if row["manual"])


def best_single(rows: list[dict], metrics: list[str]) -> tuple[int, str, str, float]:
    """En az hatalı tek eşik: (hata, metrik, yön, eşik). Eşitlikte ilk bulunan."""
    labels = _label_mask(rows)
    best = None
    for metric in metrics:
        for direction, threshold, mask in _masks(rows, metric):
            errors = (mask ^ labels).bit_count()
            if best is None or errors < best[0]:
                best = (errors, metric, direction, threshold)
    return best


def best_two(rows: list[dict], metrics: list[str]) -> tuple[int, dict] | tuple[None, None]:
    """İki metrikte `ve`/`veya` birleşiminin en az hatalısı; tek metrikte (None, None)."""
    if len(metrics) < 2:
        return None, None
    labels = _label_mask(rows)
    masks = {metric: _masks(rows, metric) for metric in metrics}
    best: tuple[int, dict] | None = None
    for left, right in combinations(metrics, 2):
        for d1, t1, m1 in masks[left]:
            for d2, t2, m2 in masks[right]:
                for combine, mask in (("and", m1 & m2), ("or", m1 | m2)):
                    errors = (mask ^ labels).bit_count()
                    if best is None or errors < best[0]:
                        best = (
                            errors,
                            {
                                "combine": combine,
                                "rule": f"{left} {d1} {t1:g} {combine} {right} {d2} {t2:g}",
                            },
                        )
    return best


def reading(n: int, positives: int, single: int, two: int | None) -> str:
    """Ön kayıttaki okuma kuralı."""
    if positives < MIN_POSITIVES:
        return "yetersiz pozitif"
    limit = max(1, math.ceil(0.02 * n))
    if single <= limit:
        return "tek eşiği kodluyor"
    if two is not None and two <= limit:
        return "kuralı kodluyor"
    return "bağımsız yargı"


def agreement(rows: list[dict], detector: str) -> float:
    return round(sum(1 for r in rows if r[detector] == r["manual"]) / len(rows), 4)


# --------------------------------------------------------------------------- #
# Sonradan eklenen analiz (ön kayıtta yok): dedektör kuralları
# --------------------------------------------------------------------------- #

#: `pysmell/detection/detector.py`'deki eşikler: [experience, statistics, tuning].
#: Genel eşiklerdir, proje başına değil.
DETECTOR = {
    "PAR": [5, 4, 5],
    "MLOC": [38, 28, 52],
    "DOC": [3, 4, 4],
    "CLOC": [29, 59, 37],
    "LMC": [5, 4, 4],
    "NBC": [3, 2, 3],
}
SINGLE_METRIC = {
    "LongParameterList": "PAR",
    "LongMethod": "MLOC",
    "LongScopeChaining": "DOC",
    "LongBaseClassList": "NBC",
    "LargeClass": "CLOC",
    "LongMessageChain": "LMC",
}


def detector_rule(smell: str, row: dict, k: int) -> bool:
    """`detector.py`'nin k. eşik takımıyla verdiği karar (0 experience, 1 statistics)."""

    def at_least(metric: str, values: list[int]) -> bool:
        return row.get(metric) is not None and row[metric] >= values[k]

    if smell == "LongLambdaFunction":
        return at_least("NOC", [48, 82, 73]) and (
            at_least("PAR", [3, 3, 4]) or at_least("NOO", [7, 13, 15])
        )
    if smell == "ComplexContainerComprehension":
        return (at_least("NOC", [62, 131, 92]) and at_least("NOO", [8, 24, 22])) or at_least(
            "NOFF", [3, 3, 3]
        )
    if smell == "LongTernaryConditionalExpression":
        return at_least("NOC", [54, 102, 101]) or at_least("NOL", [3, 3, 3])
    if smell == "MultiplyNestedContainer":
        return at_least("LEC", [3, 3, 3]) or (
            at_least("DNC", [3, 4, 3]) and at_least("NCT", [3, 2, 2])
        )
    metric = SINGLE_METRIC[smell]
    return at_least(metric, DETECTOR[metric])


def detector_check(smell: str, rows: list[dict]) -> dict:
    """Sütun kuralla aynı mı; kural elle verilen etiketten kaç satırda ayrılıyor."""
    found = {}
    for k, column in ((0, "experience"), (1, "statistics")):
        found[column] = {
            "column_differs_from_rule": sum(
                1 for r in rows if int(detector_rule(smell, r, k)) != r[column]
            ),
            "rule_differs_from_manual": sum(
                1 for r in rows if int(detector_rule(smell, r, k)) != r["manual"]
            ),
        }
    return found


# --------------------------------------------------------------------------- #
# Toplama
# --------------------------------------------------------------------------- #


def fetch() -> None:
    if (CACHE / ".git").exists():
        head = subprocess.run(
            ["git", "-C", str(CACHE), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
        if head == COMMIT:
            return
    CACHE.mkdir(parents=True, exist_ok=True)
    for command in (
        ["git", "init", "-q"],
        ["git", "fetch", "-q", "--depth", "1", REPO, COMMIT],
        ["git", "update-ref", "HEAD", "FETCH_HEAD"],
    ):
        subprocess.run(["git", "-C", str(CACHE), *command[1:]], check=True)


def read(smell: str) -> str:
    return subprocess.run(
        ["git", "-C", str(CACHE), "show", f"{COMMIT}:{MANUAL_DIR}/{smell}.csv"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8", errors="replace")


def main() -> int:
    fetch()
    results = {}
    for smell in SMELLS:
        metrics, rows = parse_rows(read(smell))
        positives = sum(r["manual"] for r in rows)
        single = best_single(rows, metrics)
        two_errors, two_rule = best_two(rows, metrics)
        results[smell] = {
            "rows": len(rows),
            "positives": positives,
            "metrics": metrics,
            "single": {
                "errors": single[0],
                "rule": f"{single[1]} {single[2]} {single[3]:g}",
            },
            "two": None if two_errors is None else {"errors": two_errors, **two_rule},
            "error_limit": max(1, math.ceil(0.02 * len(rows))),
            "reading": reading(len(rows), positives, single[0], two_errors),
            "agreement": {key: agreement(rows, key) for key in LABELS.values()},
            "posthoc_detector": detector_check(smell, rows),
            "subjects": sorted(set(_subjects(read(smell)))),
        }
        print(f"{smell:<34} done", flush=True)
    summary = {"repo": REPO, "commit": COMMIT, "smells": results}
    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    JSON_FILE.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    TABLES_FILE.write_text(render_tables(summary), encoding="utf-8")
    sys.stdout.reconfigure(errors="replace")
    print(render_tables(summary))
    return 0


def _subjects(text: str) -> list[str]:
    return [f"{row['subject']} {row['tag']}" for row in csv.DictReader(io.StringIO(text))]


def render_tables(summary: dict) -> str:
    lines = [
        "<!-- Üretildi: experiments/hardening/pysmell_labels.py. Elle düzenlemeyin. -->",
        "",
        f"PySmell `{summary['commit'][:7]}`, `manual inspection/`. Hata sınırı: max(1, ⌈0.02·N⌉).",
        "",
        "| Koku | N | pozitif | metrikler | en iyi tek eşik (hata) | en iyi iki eşik (hata) "
        "| sınır | okuma |",
        "|---|---:|---:|---|---|---|---:|---|",
    ]
    for smell, r in summary["smells"].items():
        two = "-" if r["two"] is None else f"`{r['two']['rule']}` ({r['two']['errors']})"
        lines.append(
            f"| {smell} | {r['rows']} | {r['positives']} | {', '.join(r['metrics'])} | "
            f"`{r['single']['rule']}` ({r['single']['errors']}) | {two} | {r['error_limit']} | "
            f"{r['reading']} |"
        )
    lines += [
        "",
        "## Sonradan eklenen analiz — PySmell'in kendi dedektör kuralları",
        "",
        "Ön kayıtta yok. `detector.py`'deki genel eşikler satırlara uygulandı. "
        "Sütun ≠ kural: CSV'deki dedektör sütununun kuraldan ayrıldığı satır. "
        "Kural ≠ elle: kuralın elle verilen etiketten ayrıldığı satır.",
        "",
        "| Koku | experience: sütun ≠ kural | experience: kural ≠ elle "
        "| statistics: sütun ≠ kural | statistics: kural ≠ elle |",
        "|---|---:|---:|---:|---:|",
    ]
    for smell, r in summary["smells"].items():
        d = r["posthoc_detector"]
        lines.append(
            f"| {smell} | {d['experience']['column_differs_from_rule']} | "
            f"{d['experience']['rule_differs_from_manual']} | "
            f"{d['statistics']['column_differs_from_rule']} | "
            f"{d['statistics']['rule_differs_from_manual']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
