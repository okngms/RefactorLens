"""Faz 5a çözümlemesi: koşul başına öneri kalitesi.

**Ölçmediği şey:** tahminlerin doğru olup olmadığı. Onun için önerinin
uygulanması gerekir; 5b'nin işi odur. Buradaki her ölçüt önerinin **metninden**
okunur.

Ölçütler (`v2-kalan-kapsam.md` §10, Aşama 5a):

| Ölçüt | Ne sorar |
|---|---|
| `rejected` oranı | Öneri katman kuralını çiğniyor mu? |
| Kısıt uyuşmazlığı | Modelin "kurallara uydum" beyanı doğru mu? |
| Koku adresleme | `addresses_smells` hedefin gerçekten taşıdığı etiketleri mi anıyor? |
| Hedef katman | `target_layer_after` dağılımı |
| Tutarlılık | Aynı soruya üç kez aynı cevap mı? |
| Sözleşme uyumu | `unlinked`, onarım, ayrıştırılamayan |
| Güven varlığı | Kalibrasyon 5b'de ölçülebilir mi? |

Kullanım:

    python experiments/analyse_advice_v2.py --out experiments/v2/analysis-advice.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUNS = REPO_ROOT / "experiments" / "v2" / "runs"

CONDITION_ORDER = ["plain", "arch", "rules", "arch_rules"]
CONDITION_LABELS = {
    "plain": "neither",
    "arch": "arch-context",
    "rules": "metric-rules",
    "arch_rules": "both",
}


@dataclass
class Run:
    """Tek bir (koşul, model, hedef, tekrar) çıktısı."""

    condition: str
    model: str
    target: str
    repetition: int
    suggestions: list[dict] = field(default_factory=list)
    structured: bool = True
    repaired: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def metric_set(self) -> frozenset[str]:
        names: set[str] = set()
        for suggestion in self.suggestions:
            names.update(suggestion.get("rationale_metric_link", []))
        return frozenset(names)

    @property
    def prediction_set(self) -> frozenset[tuple[str, str]]:
        pairs: set[tuple[str, str]] = set()
        for suggestion in self.suggestions:
            for effect in suggestion.get("expected_effect", []):
                pairs.add((effect.get("metric", ""), effect.get("direction", "")))
        return frozenset(pairs)


def load_runs(runs_dir: Path) -> list[Run]:
    runs: list[Run] = []
    for path in sorted(runs_dir.rglob("rep*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        advices = payload.get("advices", [])
        if not advices:
            continue
        advice = advices[0]
        runs.append(
            Run(
                # Koşul dosyanın içinden okunur; dizin adına güvenilmez.
                condition=payload.get("condition", path.parts[-4]),
                model=payload.get("model", "?"),
                target=advice.get("target", "?"),
                repetition=int(path.stem.removeprefix("rep")),
                suggestions=advice.get("suggestions", []),
                structured="unstructured" not in advice.get("tags", []),
                repaired=bool(advice.get("repaired")),
                warnings=advice.get("warnings", []),
            )
        )
    return runs


def jaccard(left: frozenset, right: frozenset) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def ratio(part: int, whole: int) -> float | None:
    """Payda sıfırsa `None` — sıfır yanıltıcı olurdu."""
    return round(part / whole, 3) if whole else None


def by_condition(runs: list[Run]) -> dict[str, list[Run]]:
    grouped: dict[str, list[Run]] = defaultdict(list)
    for run in runs:
        grouped[run.condition].append(run)
    return grouped


def condition_summary(runs: list[Run]) -> dict:
    """Bir koşulun tüm ölçütleri."""
    suggestions = [s for run in runs for s in run.suggestions]
    statuses = Counter(s.get("status", "linked") for s in suggestions)

    disagreements = sum(1 for s in suggestions if s.get("constraint_agreement") is False)
    claimed = sum(1 for s in suggestions if s.get("claims_constraints_respected") is not None)
    with_layer = sum(1 for s in suggestions if s.get("target_layer_after"))
    with_smells = sum(1 for s in suggestions if s.get("addresses_smells"))

    effects = [e for s in suggestions for e in s.get("expected_effect", [])]
    with_confidence = sum(1 for e in effects if e.get("confidence") is not None)

    return {
        "runs": len(runs),
        "suggestions": len(suggestions),
        "per_run": ratio(len(suggestions), len(runs)),
        "rejected": statuses.get("rejected", 0),
        "rejected_rate": ratio(statuses.get("rejected", 0), len(suggestions)),
        "unlinked": statuses.get("unlinked", 0),
        "unlinked_rate": ratio(statuses.get("unlinked", 0), len(suggestions)),
        "claimed_constraints": claimed,
        "disagreements": disagreements,
        "disagreement_rate": ratio(disagreements, claimed),
        "named_destination_layer": with_layer,
        "named_smells": with_smells,
        "predictions": len(effects),
        "with_confidence": with_confidence,
        "confidence_rate": ratio(with_confidence, len(effects)),
        "repaired": sum(1 for r in runs if r.repaired),
        "unstructured": sum(1 for r in runs if not r.structured),
    }


def consistency(runs: list[Run]) -> list[dict]:
    """Aynı (koşul, model, hedef) için tekrarlar birbirine ne kadar benziyor?"""
    grouped: dict[tuple[str, str, str], list[Run]] = defaultdict(list)
    for run in runs:
        grouped[(run.condition, run.model, run.target)].append(run)

    rows = []
    for (condition, model, target), group in sorted(grouped.items()):
        if len(group) < 2:
            continue
        rows.append(
            {
                "condition": condition,
                "model": model,
                "target": target,
                "n": len(group),
                "evidence": round(
                    sum(jaccard(a.metric_set, b.metric_set) for a, b in combinations(group, 2))
                    / len(list(combinations(group, 2))),
                    3,
                ),
                "prediction": round(
                    sum(
                        jaccard(a.prediction_set, b.prediction_set)
                        for a, b in combinations(group, 2)
                    )
                    / len(list(combinations(group, 2))),
                    3,
                ),
            }
        )
    return rows


def smell_addressing(runs: list[Run], smells_by_target: dict[str, set[str]]) -> list[dict]:
    """`addresses_smells` hedefin gerçekten taşıdığı etiketleri mi anıyor?

    Modelin var olmayan bir kokuyu adreslediğini iddia etmesi, kısıt beyanının
    yanlış olmasıyla aynı türden bir hatadır: kendinden emin ama yanlış.
    """
    rows = []
    for condition, group in sorted(by_condition(runs).items()):
        claimed = wrong = 0
        for run in group:
            known = smells_by_target.get(run.target, set())
            for suggestion in run.suggestions:
                for label in suggestion.get("addresses_smells", []):
                    claimed += 1
                    if label not in known:
                        wrong += 1
        rows.append(
            {
                "condition": condition,
                "claims": claimed,
                "wrong": wrong,
                "wrong_rate": ratio(wrong, claimed),
            }
        )
    return rows


def render(runs: list[Run], smells_by_target: dict[str, set[str]]) -> str:
    if not runs:
        return (
            "# Advice analysis (phase 5a)\n\n"
            "No runs found. Run `experiments/run_advice_v2.py` first.\n"
        )

    models = sorted({r.model for r in runs})
    targets = sorted({r.target for r in runs})
    conditions = [c for c in CONDITION_ORDER if c in by_condition(runs)]

    lines = [
        "# Advice analysis (phase 5a)",
        "",
        f"- **Runs:** {len(runs)}",
        f"- **Models:** {', '.join(models)}",
        f"- **Targets:** {', '.join(targets)}",
        f"- **Conditions:** {', '.join(CONDITION_LABELS[c] for c in conditions)}",
        "",
        "> This part measures **suggestion quality**, read from the text of the "
        "advice. Whether the predictions were correct requires applying them, "
        "which is part B.",
        "",
        "## Constraint compliance",
        "",
        "`rejected` counts suggestions that break the layer rules. "
        "`disagreements` counts suggestions claiming to respect them while the "
        "tool finds otherwise — the model's own claim is an output too.",
        "",
        "| Condition | Runs | Suggestions | Per run | Rejected | Rate | "
        "Claims | Disagreements | Rate |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    summaries = {c: condition_summary(by_condition(runs)[c]) for c in conditions}
    for condition in conditions:
        s = summaries[condition]
        lines.append(
            f"| {CONDITION_LABELS[condition]} | {s['runs']} | {s['suggestions']} | "
            f"{s['per_run']} | {s['rejected']} | {s['rejected_rate']} | "
            f"{s['claimed_constraints']} | {s['disagreements']} | "
            f"{s['disagreement_rate']} |"
        )

    lines += [
        "",
        "## Contract compliance",
        "",
        "| Condition | Unlinked | Rate | Repaired | Unparseable | "
        "Predictions | With confidence | Rate |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for condition in conditions:
        s = summaries[condition]
        lines.append(
            f"| {CONDITION_LABELS[condition]} | {s['unlinked']} | "
            f"{s['unlinked_rate']} | {s['repaired']} | {s['unstructured']} | "
            f"{s['predictions']} | {s['with_confidence']} | {s['confidence_rate']} |"
        )

    lines += [
        "",
        "## Architectural fields",
        "",
        "Only the conditions with architectural context can produce these.",
        "",
        "| Condition | Named a destination layer | Named smells |",
        "|---|---|---|",
    ]
    for condition in conditions:
        s = summaries[condition]
        lines.append(
            f"| {CONDITION_LABELS[condition]} | {s['named_destination_layer']} | "
            f"{s['named_smells']} |"
        )

    if smells_by_target:
        lines += [
            "",
            "### Are the named smells real?",
            "",
            "| Condition | Claims | Wrong | Rate |",
            "|---|---|---|---|",
        ]
        for row in smell_addressing(runs, smells_by_target):
            if row["claims"]:
                lines.append(
                    f"| {CONDITION_LABELS.get(row['condition'], row['condition'])} | "
                    f"{row['claims']} | {row['wrong']} | {row['wrong_rate']} |"
                )

    lines += [
        "",
        "## Consistency across repetitions",
        "",
        "Mean Jaccard similarity between the repetitions of the same "
        "(condition, model, target). A model whose own runs disagree cannot be "
        "compared with another until that variance is accounted for.",
        "",
        "| Condition | Model | Target | n | Evidence | Prediction |",
        "|---|---|---|---|---|---|",
    ]
    for row in consistency(runs):
        lines.append(
            f"| {CONDITION_LABELS.get(row['condition'], row['condition'])} | "
            f"`{row['model']}` | `{row['target']}` | {row['n']} | "
            f"{row['evidence']} | {row['prediction']} |"
        )

    warnings = Counter(w for r in runs for w in r.warnings)
    if warnings:
        lines += ["", "## Schema warnings", ""]
        for warning, count in warnings.most_common(10):
            lines.append(f"- ({count}×) {warning}")

    lines.append("")
    return "\n".join(lines)


def smells_from_project(project: Path) -> dict[str, set[str]]:
    """Hedeflerin gerçekten taşıdığı koku etiketleri.

    `addresses_smells` iddialarını doğrulamak için gerekir.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "src"))
    from rlens.analysis.scanner import scan_project
    from rlens.config import load_config

    report = scan_project(project, load_config(search_from=project))
    found: dict[str, set[str]] = defaultdict(set)
    for cls in report.iter_classes():
        for smell in cls.smells:
            found[cls.qualified_name].add(smell["label"])
    return dict(found)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--project", type=Path, default=REPO_ROOT / "examples" / "layered_project")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    runs = load_runs(args.runs)
    smells = smells_from_project(args.project) if args.project.is_dir() else {}
    report = render(runs, smells)
    print(report)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
