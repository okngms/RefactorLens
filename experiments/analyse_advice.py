"""Faz 5 / A parçası: toplanan önerilerin çözümlenmesi.

`run_advice.py`'nin yazdığı ham çıktıları okur ve dört soruya cevap üretir:

1. **Sözleşmeye uyum.** Öneriler gerçekten bir metriğe bağlanıyor mu, yoksa
   `rationale_metric_link` formalite mi dolduruluyor? Yanıtlar JSON şemasına
   uyuyor mu, kaçı onarım gerektirdi?
2. **Tekrarlar arası tutarlılık.** Aynı modele aynı soru üç kez sorulduğunda
   aynı metriklere mi bakıyor, aynı yönleri mi tahmin ediyor?
3. **Tahmin profili.** Hangi metrikler hakkında tahmin veriliyor, hangi yönde?
   Ödünleşim kabul ediliyor mu, yoksa her metrik birden iyileşecek mi deniyor?
4. **Modeller arası fark.** Varsa, tekrar varyansını aşıyor mu?

**Bu aşama tahminlerin doğruluğunu ölçmez.** Onun için önerinin uygulanması
gerekir; B parçasının işi odur. Buradaki sorular kod değişikliği gerektirmez.

Kullanım:

    python experiments/analyse_advice.py
    python experiments/analyse_advice.py --out experiments/analysis-advice.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUNS = REPO_ROOT / "experiments" / "runs"

UNLINKED = "unlinked"
UNSTRUCTURED = "unstructured"


@dataclass
class Run:
    """Tek bir (model, hedef, tekrar) çıktısı."""

    model: str
    target: str
    repetition: int
    suggestions: list[dict] = field(default_factory=list)
    structured: bool = True
    repaired: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def metric_set(self) -> frozenset[str]:
        """Bu çalıştırmada adı geçen tüm kanıt metrikleri."""
        names: set[str] = set()
        for suggestion in self.suggestions:
            names.update(suggestion.get("rationale_metric_link", []))
        return frozenset(names)

    @property
    def prediction_set(self) -> frozenset[tuple[str, str]]:
        """`(metrik, yön)` çiftlerinin kümesi."""
        pairs: set[tuple[str, str]] = set()
        for suggestion in self.suggestions:
            for effect in suggestion.get("expected_effect", []):
                pairs.add((effect.get("metric", ""), effect.get("direction", "")))
        return frozenset(pairs)

    @property
    def unlinked_count(self) -> int:
        return sum(1 for s in self.suggestions if not s.get("rationale_metric_link"))


def load_runs(runs_dir: Path) -> list[Run]:
    """Diskteki tüm çalıştırmaları okur."""
    runs: list[Run] = []
    for path in sorted(runs_dir.rglob("rep*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        advices = payload.get("advices", [])
        if not advices:
            continue
        advice = advices[0]
        runs.append(
            Run(
                model=payload.get("model", "?"),
                target=advice.get("target", "?"),
                repetition=int(path.stem.removeprefix("rep")),
                suggestions=advice.get("suggestions", []),
                structured=UNSTRUCTURED not in advice.get("tags", []),
                repaired=bool(advice.get("repaired")),
                warnings=advice.get("warnings", []),
            )
        )
    return runs


def jaccard(left: frozenset, right: frozenset) -> float:
    """İki küme ne kadar örtüşüyor? Boş kümeler tam örtüşme sayılır."""
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def compliance_table(runs: list[Run]) -> list[dict]:
    """Model başına sözleşme uyumu."""
    by_model: dict[str, list[Run]] = defaultdict(list)
    for run in runs:
        by_model[run.model].append(run)

    rows = []
    for model, model_runs in sorted(by_model.items()):
        suggestions = sum(len(r.suggestions) for r in model_runs)
        unlinked = sum(r.unlinked_count for r in model_runs)
        with_prediction = sum(
            1 for r in model_runs for s in r.suggestions if s.get("expected_effect")
        )
        rows.append(
            {
                "model": model,
                "runs": len(model_runs),
                "unstructured": sum(1 for r in model_runs if not r.structured),
                "repaired": sum(1 for r in model_runs if r.repaired),
                "suggestions": suggestions,
                "unlinked": unlinked,
                "unlinked_rate": round(unlinked / suggestions, 3) if suggestions else None,
                "with_prediction": with_prediction,
                "prediction_rate": (
                    round(with_prediction / suggestions, 3) if suggestions else None
                ),
                "suggestions_per_run": (
                    round(suggestions / len(model_runs), 2) if model_runs else None
                ),
            }
        )
    return rows


def consistency_table(runs: list[Run]) -> list[dict]:
    """Aynı (model, hedef) için tekrarlar birbirine ne kadar benziyor?

    Ölçüt, tekrar çiftleri arasındaki Jaccard benzerliğinin ortalamasıdır.
    1.0 = her seferinde aynı metriklere bakılmış; 0.0 = hiç ortak yok.
    """
    grouped: dict[tuple[str, str], list[Run]] = defaultdict(list)
    for run in runs:
        grouped[(run.model, run.target)].append(run)

    rows = []
    for (model, target), group in sorted(grouped.items()):
        if len(group) < 2:
            continue
        metric_scores = [jaccard(a.metric_set, b.metric_set) for a, b in combinations(group, 2)]
        prediction_scores = [
            jaccard(a.prediction_set, b.prediction_set) for a, b in combinations(group, 2)
        ]
        counts = [len(r.suggestions) for r in group]
        rows.append(
            {
                "model": model,
                "target": target,
                "repetitions": len(group),
                "evidence_agreement": mean(metric_scores),
                "prediction_agreement": mean(prediction_scores),
                "suggestion_counts": counts,
            }
        )
    return rows


def prediction_profile(runs: list[Run]) -> dict[str, Counter]:
    """Model başına, hangi metrik hakkında hangi yönde tahmin verildiği."""
    profile: dict[str, Counter] = defaultdict(Counter)
    for run in runs:
        for metric, direction in run.prediction_set:
            profile[run.model][f"{metric} {direction}"] += 1
    return profile


def tradeoff_rate(runs: list[Run]) -> list[dict]:
    """Öneriler ödünleşim kabul ediyor mu?

    Bir öneri hem `down` hem `up` tahmini içeriyorsa, model bir metriği
    iyileştirirken diğerini bozacağını kabul etmiş demektir. Hepsi aynı yönde
    ise ya gerçekten öyledir ya da model iyimserlik yapıyordur — B parçası
    hangisi olduğunu söyleyecek.
    """
    by_model: dict[str, list[bool]] = defaultdict(list)
    for run in runs:
        for suggestion in run.suggestions:
            directions = {
                effect.get("direction") for effect in suggestion.get("expected_effect", [])
            }
            directions.discard("same")
            if directions:
                by_model[run.model].append(len(directions) > 1)

    return [
        {
            "model": model,
            "suggestions_with_direction": len(flags),
            "acknowledging_tradeoff": sum(flags),
            "rate": round(sum(flags) / len(flags), 3) if flags else None,
        }
        for model, flags in sorted(by_model.items())
    ]


def render(runs: list[Run]) -> str:
    """Çözümlemeyi markdown olarak biçimlendirir."""
    if not runs:
        return "# Advice analysis\n\nNo runs found. Run `experiments/run_advice.py` first.\n"

    models = sorted({r.model for r in runs})
    targets = sorted({r.target for r in runs})

    lines = [
        "# Advice analysis (phase 5, part A)",
        "",
        f"- **Runs:** {len(runs)}",
        f"- **Models:** {', '.join(models)}",
        f"- **Targets:** {', '.join(targets)}",
        "",
        "> This part measures **contract compliance and consistency**, not whether "
        "the predictions were correct. Checking correctness requires applying the "
        "suggestions, which is part B.",
        "",
        "## Contract compliance",
        "",
        "`unlinked` counts suggestions naming no metric — the rule the prompt makes "
        "mandatory. `repaired` counts replies that were not valid JSON on the first "
        "attempt.",
        "",
        "| Model | Runs | Suggestions | Per run | Unlinked | Unlinked rate "
        "| With prediction | Repaired | Unstructured |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in compliance_table(runs):
        lines.append(
            f"| `{row['model']}` | {row['runs']} | {row['suggestions']} | "
            f"{row['suggestions_per_run']} | {row['unlinked']} | "
            f"{row['unlinked_rate']} | {row['with_prediction']} | "
            f"{row['repaired']} | {row['unstructured']} |"
        )

    lines += [
        "",
        "## Consistency across repetitions",
        "",
        "Mean Jaccard similarity between the repetitions of the same "
        "(model, target) pair. 1.0 means every run cited the same metrics; 0.0 "
        "means no overlap at all.",
        "",
        "A model whose own runs disagree cannot be meaningfully compared with "
        "another model until that variance is accounted for.",
        "",
        "| Model | Target | n | Evidence agreement | Prediction agreement | Suggestions per run |",
        "|---|---|---|---|---|---|",
    ]
    for row in consistency_table(runs):
        lines.append(
            f"| `{row['model']}` | `{row['target']}` | {row['repetitions']} | "
            f"{row['evidence_agreement']} | {row['prediction_agreement']} | "
            f"{row['suggestion_counts']} |"
        )

    lines += [
        "",
        "## Prediction profile",
        "",
        "Which metrics models predict, and in which direction.",
        "",
    ]
    for model, counter in sorted(prediction_profile(runs).items()):
        lines.append(f"**`{model}`**")
        lines.append("")
        for label, count in counter.most_common():
            lines.append(f"- {label}: {count}")
        lines.append("")

    lines += [
        "## Trade-off acknowledgement",
        "",
        "A suggestion predicting both `up` and `down` admits it will make some "
        "metric worse. One predicting only improvements is either right or "
        "optimistic — part B decides which.",
        "",
        "| Model | Suggestions with a direction | Acknowledging a trade-off | Rate |",
        "|---|---|---|---|",
    ]
    for row in tradeoff_rate(runs):
        lines.append(
            f"| `{row['model']}` | {row['suggestions_with_direction']} | "
            f"{row['acknowledging_tradeoff']} | {row['rate']} |"
        )

    warnings = Counter(w for r in runs for w in r.warnings)
    if warnings:
        lines += ["", "## Schema warnings", ""]
        for warning, count in warnings.most_common(10):
            lines.append(f"- ({count}×) {warning}")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--out", type=Path, default=None, help="Write markdown here too.")
    args = parser.parse_args()

    runs = load_runs(args.runs)
    report = render(runs)
    print(report)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
