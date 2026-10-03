"""LensBench raporu: tablolar ve ön kayıtlı karar kuralları.

Karar eşikleri `docs/lensbench-v1-onkayit.md` ile birebir aynıdır ve
sonuçlar görülmeden yazıldı; burada değiştirilmeleri ön kaydı bozar.
Raporlama sırası AGENTS kuralına uyar: önce metrik bazında, sonra gruplar.

Yalnızca **doğrulanabilir** tahminler doğruluğa girer; doğrulanamayanlar
sayılır ve gösterilir (invariant). Güven verilmemiş tahmin kalibrasyona
girmez, sayılır (kilitli karar).
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from rlens.bench.suite import BenchError

#: Ön kayıtlı eşikler.
#: Birincil set üç ücretsiz model (ön kayıt §5); "dörtte üç" üçte üç demektir.
MIN_MODELS = 3
MIN_PREDICTIONS = 10
MIN_PER_KIND = 20
H1_GAIN = 0.10
H3_OVERCONFIDENCE = 0.10
H4_SPREAD_SUPPORTED = 0.20
H4_SPREAD_REFUTED = 0.10
H5_GAP_SUPPORTED = 0.30
H5_GAP_REFUTED = 0.10

#: Ölçüm boşluğu sayılan durma nedenleri (ön kayıt N1, N3).
LIMITS = ("provider_limit", "output_limit")

SUPPORTED, REFUTED, INCONCLUSIVE, INSUFFICIENT = (
    "supported",
    "refuted",
    "inconclusive",
    "insufficient data",
)


@dataclass(frozen=True)
class Prediction:
    model: str
    target: str
    condition: str
    iteration: int
    last: bool
    metric: str
    predicted: str
    outcome: str
    confidence: float | None
    kind: str
    wrappers: bool


def load_results(paths: list[Path]) -> list[dict]:
    results = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
    if not results:
        raise BenchError("No result files given.")
    for key in ("suite_hash", "prompt_hash", "project_hashes"):
        values = {json.dumps(r[key], sort_keys=True) for r in results}
        if len(values) > 1:
            raise BenchError(
                f"The result files differ in `{key}`; they measured different suites, "
                "prompts or code and cannot share a table."
            )
    return results


def _primary_kind(kinds: list[str]) -> str:
    named = [k for k in kinds if k != "unknown"]
    pool = named or kinds
    return max(sorted(set(pool)), key=pool.count) if pool else "none"


def predictions(results: list[dict]) -> list[Prediction]:
    found = []
    for result in results:
        model = f"{result['provider']}/{result['model']}"
        for unit in result["units"]:
            iterations = unit["loop"]["iterations"]
            for item in iterations:
                apply = item.get("apply") or {}
                refactorings = apply.get("refactorings") or []
                wrappers = any(
                    r.get("details", {}).get("delegating_wrappers") for r in refactorings
                )
                kind = _primary_kind([r["kind"] for r in refactorings])
                for suggestion in (apply.get("predictions") or {}).get("suggestions", []):
                    for check in suggestion.get("checks", []):
                        found.append(
                            Prediction(
                                model=model,
                                target=unit["target"],
                                condition=unit["condition"],
                                iteration=item["iteration"],
                                last=item is iterations[-1],
                                metric=check["metric"],
                                predicted=check["predicted"],
                                outcome=check["outcome"],
                                confidence=check.get("confidence"),
                                kind=kind,
                                wrappers=wrappers,
                            )
                        )
    return found


def verdict_items(items: list[Prediction], primary: set[str] | None) -> list[Prediction]:
    """Hükme giren tahminler: yalnızca birincil set (verilmişse)."""
    if primary is None:
        return items
    return [p for p in items if p.model in primary]


def _accuracy(items: list[Prediction]) -> tuple[float | None, int]:
    verifiable = [p for p in items if p.outcome in ("hit", "miss")]
    if not verifiable:
        return None, 0
    return sum(p.outcome == "hit" for p in verifiable) / len(verifiable), len(verifiable)


def _share(total: int) -> int:
    """Modellerin dörtte üçü (yukarı yuvarlanmış)."""
    return math.ceil(0.75 * total) if total else 0


def h1(items: list[Prediction]) -> tuple[str, dict]:
    """Geri besleme: `loop3`'te son iterasyonun doğruluğu − ilk iterasyonun."""
    gains = {}
    for model in sorted({p.model for p in items}):
        mine = [p for p in items if p.model == model and p.condition == "loop3"]
        first, n_first = _accuracy([p for p in mine if p.iteration == 1])
        last, n_last = _accuracy([p for p in mine if p.last])
        if n_first >= MIN_PREDICTIONS and n_last >= MIN_PREDICTIONS:
            gains[model] = round(last - first, 4)
    if len(gains) < MIN_MODELS:
        return INSUFFICIENT, gains
    mean = sum(gains.values()) / len(gains)
    positive = sum(g > 0 for g in gains.values())
    non_positive = len(gains) - positive
    if mean >= H1_GAIN and positive >= _share(len(gains)):
        return SUPPORTED, gains
    if mean <= 0 and non_positive >= _share(len(gains)):
        return REFUTED, gains
    return INCONCLUSIVE, gains


def h3(items: list[Prediction]) -> tuple[str, dict]:
    """Aşırı güven: ortalama beyan edilen güven − gerçek doğruluk."""
    gaps = {}
    for model in sorted({p.model for p in items}):
        rated = [
            p
            for p in items
            if p.model == model and p.confidence is not None and p.outcome in ("hit", "miss")
        ]
        if len(rated) >= MIN_PREDICTIONS:
            accuracy = sum(p.outcome == "hit" for p in rated) / len(rated)
            gaps[model] = round(sum(p.confidence for p in rated) / len(rated) - accuracy, 4)
    if len(gaps) < MIN_MODELS:
        return INSUFFICIENT, gaps
    over = sum(g > H3_OVERCONFIDENCE for g in gaps.values())
    under = sum(g <= 0 for g in gaps.values())
    if over >= _share(len(gaps)):
        return SUPPORTED, gaps
    if under >= _share(len(gaps)):
        return REFUTED, gaps
    return INCONCLUSIVE, gaps


def h4(items: list[Prediction]) -> tuple[str, dict]:
    """Tür bazında doğruluk farkı (bütün modeller birlikte)."""
    by_kind = {}
    for kind in sorted({p.kind for p in items}):
        accuracy, n = _accuracy([p for p in items if p.kind == kind])
        if n >= MIN_PER_KIND:
            by_kind[kind] = round(accuracy, 4)
    if len(by_kind) < 2:
        return INSUFFICIENT, by_kind
    spread = max(by_kind.values()) - min(by_kind.values())
    if spread >= H4_SPREAD_SUPPORTED:
        return SUPPORTED, by_kind
    if spread <= H4_SPREAD_REFUTED:
        return REFUTED, by_kind
    return INCONCLUSIVE, by_kind


def h5(items: list[Prediction]) -> tuple[str, dict]:
    """Kalıntı: NOM/LCOM4 "down" tahminleri sarmalayıcı kalınca daha çok tutmaz."""
    pool = [p for p in items if p.metric in ("NOM", "LCOM4") and p.predicted == "down"]
    rates = {}
    for label, flag in (("with_wrappers", True), ("without_wrappers", False)):
        accuracy, n = _accuracy([p for p in pool if p.wrappers is flag])
        rates[label] = None if n < MIN_PREDICTIONS else round(1 - accuracy, 4)
        rates[f"{label}_n"] = n
    if rates["with_wrappers"] is None or rates["without_wrappers"] is None:
        return INSUFFICIENT, rates
    gap = rates["with_wrappers"] - rates["without_wrappers"]
    if gap >= H5_GAP_SUPPORTED:
        return SUPPORTED, rates
    if gap <= H5_GAP_REFUTED:
        return REFUTED, rates
    return INCONCLUSIVE, rates


def _fmt(value) -> str:
    if value is None:
        return "—"
    return f"{value:.0%}" if isinstance(value, float) else str(value)


def report_markdown(results: list[dict], primary: set[str] | None = None) -> str:
    """`primary`: ön kayıtlı modeller; hükümler yalnızca onlarla verilir."""
    items = predictions(results)
    judged = verdict_items(items, primary)
    first = results[0]
    lines = [
        f"# LensBench report — {first['suite']}",
        "",
        f"- Suite hash `{first['suite_hash']}`, prompt hash `{first['prompt_hash']}`",
        f"- Result files: {len(results)}; models: {len({p.model for p in items}) or len(results)}",
        "- Only verifiable predictions count toward accuracy; unverifiable ones are listed.",
        "- Provider limit: runs stopped by a request over the provider's per-request limit;"
        " a measurement gap, not a model error, never retried.",
        "",
        "## Per model",
        "",
        "| Model | Units | Verifiable | Accuracy | Unverifiable | Tests passed "
        "| Suspicious | Rejected advice | Provider limit |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        model = f"{result['provider']}/{result['model']}"
        mine = [p for p in items if p.model == model]
        accuracy, n = _accuracy(mine)
        iterations = [it for u in result["units"] for it in u["loop"]["iterations"]]
        gated = [it for it in iterations if it.get("gate_passed") is not None]
        passed = sum(1 for it in gated if it["gate_passed"]) / len(gated) if gated else None
        suspicious = (
            sum(1 for it in iterations if it.get("outcome") == "suspicious") / len(iterations)
            if iterations
            else None
        )
        statuses = [it.get("advice_status") for it in iterations if it.get("advice_status")]
        rejected = statuses.count("rejected") / len(statuses) if statuses else None
        lines.append(
            f"| {model} | {len(result['units'])} | {n} | {_fmt(accuracy)} | "
            f"{sum(p.outcome not in ('hit', 'miss') for p in mine)} | {_fmt(passed)} | "
            f"{_fmt(suspicious)} | {_fmt(rejected)} | "
            f"{sum(u['loop']['stop_reason'] in LIMITS for u in result['units'])} |"
        )

    metrics = sorted({p.metric for p in items})
    models = sorted({p.model for p in items})
    lines += ["", "## Per metric (all conditions)", "", "| Metric | " + " | ".join(models) + " |"]
    lines.append("|---|" + "---:|" * len(models))
    for metric in metrics:
        cells = []
        for model in models:
            accuracy, n = _accuracy([p for p in items if p.metric == metric and p.model == model])
            cells.append(f"{_fmt(accuracy)} (n={n})")
        lines.append(f"| {metric} | " + " | ".join(cells) + " |")

    conditions = sorted({p.condition for p in items})
    lines += ["", "## Per condition", "", "| Condition | " + " | ".join(models) + " |"]
    lines.append("|---|" + "---:|" * len(models))
    for condition in conditions:
        cells = []
        for model in models:
            subset = [p for p in items if p.condition == condition and p.model == model]
            accuracy, n = _accuracy(subset)
            cells.append(f"{_fmt(accuracy)} (n={n})")
        lines.append(f"| {condition} | " + " | ".join(cells) + " |")

    lines += ["", "## Pre-registered hypotheses", ""]
    if primary is not None:
        later = sorted({p.model for p in items} - primary)
        lines += [
            f"Verdicts use the pre-registered models only: {', '.join(sorted(primary))}."
            + (f" Added later (tables only): {', '.join(later)}." if later else ""),
            "",
        ]
    else:
        lines += ["No models file given: verdicts use every result.", ""]
    for name, (verdict, data) in (
        ("H1 feedback raises accuracy (loop3, last − first iteration)", h1(judged)),
        ("H3 models are overconfident (stated confidence − accuracy)", h3(judged)),
        ("H4 accuracy differs by refactoring kind", h4(judged)),
        ("H5 NOM/LCOM4 'down' misses more when delegating wrappers stay", h5(judged)),
    ):
        lines.append(f"- **{name}: {verdict}.** {json.dumps(data, sort_keys=True)}")
    lines += [
        "- **H2** (characterization tests catch more than the user's tests) is deferred: "
        "it needs both gates on the same patch, which v1 does not run.",
        "",
    ]
    return "\n".join(lines)


def grouped(items: list[Prediction]) -> dict:
    """Ham sayımlar (JSON için): model × metrik × sonuç."""
    counts: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for p in items:
        counts[p.model][p.metric][p.outcome] += 1
    return {m: {k: dict(v) for k, v in metrics.items()} for m, metrics in counts.items()}
