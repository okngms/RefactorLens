"""Doğrulama raporunun sunumu: terminal ve markdown.

Üç şey öne çıkarılır:

* **Karşılaştırılamazlık sessiz kalmaz.** Şema uyumsuzluğu varsa tablo yine
  basılır ama üstünde büyük bir uyarı durur; sayılara güvenilmemesi gerektiğini
  kullanıcı görmeden geçemez.
* **`mixed` gizlenmez.** Bir metriği düzeltirken diğerini bozan değişiklik,
  temiz bir iyileşme kadar önemli bir bulgudur.
* **Davranış testi hatırlatması her raporda vardır.** Metrikler ancak kod hâlâ
  çalışıyorsa bir şey ifade eder; bu proje kuralı rapordan çıkarılamaz.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from rlens.verify.calibration import CalibrationReport
from rlens.verify.diff import (
    ADDED,
    IMPROVED,
    MIXED,
    REGRESSED,
    REMOVED,
    ProjectDelta,
)
from rlens.verify.goodhart import GoodhartReport
from rlens.verify.prediction import HIT, MISS, UNVERIFIABLE, PredictionReport

#: Sonuç etiketlerinin renkleri.
_VERDICT_STYLES = {
    IMPROVED: "green",
    REGRESSED: "red",
    MIXED: "yellow",
    ADDED: "cyan",
    REMOVED: "magenta",
}

#: Tahmin sonuçlarının işaretleri.
_OUTCOME_MARKS = {HIT: "✓", MISS: "✗", UNVERIFIABLE: "?"}
_OUTCOME_STYLES = {HIT: "green", MISS: "red", UNVERIFIABLE: "dim"}

BEHAVIOUR_REMINDER = (
    "Metrics only mean something if the behaviour tests still pass. "
    "A refactoring that improves every number while breaking the code is a "
    "regression, not an improvement."
)


def _changed_summary(entity) -> str:
    """`LCOM4 4→1, DCC 8→4` biçiminde tek satırlık özet."""
    parts = [
        f"{metric} {delta.before}→{delta.after}" for metric, delta in entity.changed_metrics.items()
    ]
    return ", ".join(parts)


def build_delta_table(delta: ProjectDelta) -> Table | None:
    """Değişen öğelerin tablosu. Hiçbir şey değişmediyse None."""
    rows = delta.changed
    if not rows:
        return None

    table = Table(title="Metric changes", title_justify="left", header_style="bold")
    table.add_column("Entity", overflow="fold")
    table.add_column("Verdict")
    table.add_column("Changed metrics", overflow="fold")

    for entity in sorted(rows, key=lambda e: e.qualified_name):
        verdict = entity.summarise()
        style = _VERDICT_STYLES.get(verdict)
        shown = f"[{style}]{verdict}[/{style}]" if style else verdict
        table.add_row(entity.qualified_name, shown, _changed_summary(entity))
    return table


def build_prediction_table(report: PredictionReport) -> Table | None:
    """Tahmin denetimi tablosu. Hiç tahmin yoksa None."""
    if not report.scores:
        return None

    table = Table(title="Prediction check", title_justify="left", header_style="bold")
    table.add_column("Suggestion", overflow="fold")
    table.add_column("Metric")
    table.add_column("Predicted")
    table.add_column("Actual")
    table.add_column("")

    for score in report.scores:
        label = f"{score.index}. {score.title}"
        for position, check in enumerate(score.checks):
            mark = _OUTCOME_MARKS.get(check.outcome, "?")
            style = _OUTCOME_STYLES.get(check.outcome, "")
            table.add_row(
                label if position == 0 else "",
                check.metric,
                check.predicted,
                check.actual or "—",
                f"[{style}]{mark}[/{style}]" if style else mark,
            )
    return table


def build_set_table(delta: ProjectDelta) -> Table | None:
    """Mimari ihlal ve koku farkı. İkisi de değişmediyse None."""
    rows: list[tuple[str, str, str]] = []
    for name, change in (("violations", delta.violations), ("smells", delta.smells)):
        for item in change.removed:
            rows.append((name, "gone", item))
        for item in change.added:
            rows.append((name, "new", item))
    if not rows:
        return None

    table = Table(title="Architecture and smells", title_justify="left", header_style="bold")
    table.add_column("Kind")
    table.add_column("Change")
    table.add_column("Item", overflow="fold")
    for kind, change, item in rows:
        style = "green" if change == "gone" else "red"
        table.add_row(kind, f"[{style}]{change}[/{style}]", item)
    return table


def build_calibration_table(report: CalibrationReport) -> Table | None:
    """Güven kovaları. Hiç güven verilmemişse None."""
    if not report.points:
        return None
    table = Table(title="Confidence calibration", title_justify="left", header_style="bold")
    table.add_column("Confidence")
    table.add_column("Predictions", justify="right")
    table.add_column("Stated", justify="right")
    table.add_column("Actual", justify="right")
    table.add_column("Gap", justify="right")
    for bucket in report.bins:
        if not bucket.count:
            continue
        style = "red" if bucket.gap and bucket.gap > 0.2 else ""
        gap = f"{bucket.gap:+.2f}"
        table.add_row(
            f"{bucket.low:.1f}–{bucket.high:.1f}",
            str(bucket.count),
            f"{bucket.mean_confidence:.2f}",
            f"{bucket.accuracy:.2f}",
            f"[{style}]{gap}[/{style}]" if style else gap,
        )
    return table


def render_verify(
    delta: ProjectDelta,
    console: Console,
    predictions: PredictionReport | None = None,
    goodhart: GoodhartReport | None = None,
    calibration: CalibrationReport | None = None,
) -> None:
    """Doğrulama sonucunu terminale basar."""
    console.print(
        f"[bold]before[/bold] {delta.before_generated_at or '?'}  →  "
        f"[bold]after[/bold] {delta.after_generated_at or '?'}"
    )

    if not delta.comparable:
        console.print()
        console.print(f"[bold red]Not comparable:[/] {delta.incompatibility}")
        console.print(
            "[yellow]The numbers below are shown for information only; "
            "do not draw conclusions from them.[/]"
        )

    table = build_delta_table(delta)
    if table is None:
        console.print("\n[green]No metric changed.[/]")
    else:
        console.print()
        console.print(table)

    added = delta.with_status(ADDED)
    removed = delta.with_status(REMOVED)
    if added:
        console.print(f"[cyan]new:[/] {', '.join(e.qualified_name for e in added)}")
    if removed:
        console.print(f"[magenta]gone:[/] {', '.join(e.qualified_name for e in removed)}")

    sets = build_set_table(delta)
    if sets is not None:
        console.print()
        console.print(sets)

    if goodhart is not None and goodhart.any_suspicious:
        console.print()
        console.print(
            f"[bold yellow]{len(goodhart.suspicious)} suspicious improvement(s)[/] — "
            f"metrics got better while the public interface shrank:"
        )
        for check in goodhart.suspicious:
            console.print(f"  [yellow]{check.qualified_name}[/] — {check.reason}")
        console.print(
            "[dim]This is a question, not a verdict: deleting dead code shrinks "
            "the interface too. The behaviour tests decide.[/dim]"
        )

    if predictions is not None and predictions.scores:
        console.print()
        console.print(build_prediction_table(predictions))
        console.print()

        accuracy = predictions.accuracy
        if accuracy is None:
            console.print(
                "[dim]No prediction could be verified — "
                "the metrics involved were not measurable.[/dim]"
            )
        else:
            console.print(
                f"[bold]prediction accuracy: {predictions.hits}/"
                f"{predictions.verifiable} ({accuracy:.0%})[/bold]"
            )
        if predictions.unverifiable:
            console.print(
                f"[dim]{predictions.unverifiable} prediction(s) could not be "
                f"verified; they are excluded from the ratio.[/dim]"
            )
        if not predictions.filtered:
            console.print(
                "[yellow]Note:[/] every suggestion was checked, including ones "
                "you may not have applied. Use --applied to score only what you "
                "actually did."
            )

    if calibration is not None and calibration.points:
        console.print()
        console.print(build_calibration_table(calibration))
        console.print(
            f"[bold]Brier {calibration.brier:.3f} · ECE {calibration.ece:.3f}[/bold] "
            f"(stated {calibration.mean_confidence:.2f}, actual "
            f"{calibration.accuracy:.2f}, gap {calibration.overconfidence:+.2f})"
        )
        if calibration.without_confidence:
            console.print(
                f"[dim]{calibration.without_confidence} prediction(s) came without a "
                f"confidence and are excluded.[/dim]"
            )

    console.print()
    console.print(f"[dim]{BEHAVIOUR_REMINDER}[/dim]")


def verify_markdown(
    delta: ProjectDelta,
    predictions: PredictionReport | None = None,
    goodhart: GoodhartReport | None = None,
    calibration: CalibrationReport | None = None,
) -> str:
    """Doğrulama sonucunun markdown hali."""
    lines = [
        "# RefactorLens verification",
        "",
        f"- **Before:** {delta.before_generated_at or 'unknown'}",
        f"- **After:** {delta.after_generated_at or 'unknown'}",
        "",
    ]

    if not delta.comparable:
        lines += [
            f"> **Not comparable.** {delta.incompatibility}",
            ">",
            "> The numbers below are shown for information only.",
            "",
        ]

    lines += ["## Metric changes", ""]
    changed = delta.changed
    if not changed:
        lines += ["No metric changed.", ""]
    else:
        lines += ["| Entity | Verdict | Changed metrics |", "|---|---|---|"]
        for entity in sorted(changed, key=lambda e: e.qualified_name):
            lines.append(
                f"| `{entity.qualified_name}` | {entity.summarise()} | "
                f"{_changed_summary(entity) or '—'} |"
            )
        lines.append("")

    if predictions is not None and predictions.scores:
        lines += ["## Prediction check", ""]
        if not predictions.filtered:
            lines += [
                "> Every suggestion was checked, including ones that may not have "
                "been applied. Predictions for unapplied suggestions are not "
                "meaningful.",
                "",
            ]
        for score in predictions.scores:
            lines += [f"### {score.index}. {score.title}", "", f"Target: `{score.target}`", ""]
            lines += ["| Metric | Predicted | Actual | Outcome |", "|---|---|---|---|"]
            for check in score.checks:
                actual = check.actual or "—"
                note = f" ({check.reason})" if check.outcome == UNVERIFIABLE else ""
                lines.append(
                    f"| {check.metric} | {check.predicted} | {actual} | {check.outcome}{note} |"
                )
            accuracy = "not measurable" if score.accuracy is None else f"{score.accuracy:.0%}"
            lines += ["", f"**Accuracy:** {score.hits}/{score.verifiable} ({accuracy})", ""]

        overall = (
            "not measurable" if predictions.accuracy is None else f"{predictions.accuracy:.0%}"
        )
        lines += [
            "### Overall",
            "",
            f"- Hits: {predictions.hits}",
            f"- Misses: {predictions.misses}",
            f"- Unverifiable: {predictions.unverifiable} (excluded from the ratio)",
            f"- **Accuracy: {overall}**",
            "",
        ]

    if (
        delta.violations.removed
        or delta.violations.added
        or delta.smells.removed
        or delta.smells.added
    ):
        lines += ["## Architecture and smells", ""]
        for name, change in (("Violations", delta.violations), ("Smells", delta.smells)):
            if change.removed:
                lines.append(f"- **{name} gone:** {', '.join(change.removed)}")
            if change.added:
                lines.append(f"- **{name} new:** {', '.join(change.added)}")
        lines.append("")

    if goodhart is not None and goodhart.any_suspicious:
        lines += [
            "## Suspicious improvements",
            "",
            "> Metrics improved while the public interface shrank. This is a "
            "question, not a verdict: deleting dead code shrinks the interface "
            "too. The behaviour tests decide.",
            "",
        ]
        for check in goodhart.suspicious:
            lines.append(f"- `{check.qualified_name}` — {check.reason}")
        lines.append("")

    if calibration is not None and calibration.points:
        lines += [
            "## Confidence calibration",
            "",
            f"- **Brier:** {calibration.brier:.3f} (0 perfect, 0.25 coin flip)",
            f"- **ECE:** {calibration.ece:.3f}",
            f"- Stated confidence {calibration.mean_confidence:.2f} vs actual "
            f"accuracy {calibration.accuracy:.2f} "
            f"(gap {calibration.overconfidence:+.2f})",
            f"- {calibration.without_confidence} prediction(s) came without a "
            f"confidence and are excluded",
            "",
            "| Confidence | Predictions | Stated | Actual | Gap |",
            "|---|---|---|---|---|",
        ]
        for bucket in calibration.bins:
            if not bucket.count:
                continue
            lines.append(
                f"| {bucket.low:.1f}–{bucket.high:.1f} | {bucket.count} | "
                f"{bucket.mean_confidence:.2f} | {bucket.accuracy:.2f} | "
                f"{bucket.gap:+.2f} |"
            )
        lines.append("")

    lines += ["---", "", f"_{BEHAVIOUR_REMINDER}_", ""]
    return "\n".join(lines).rstrip() + "\n"
