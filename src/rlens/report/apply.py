"""`apply` çıktısı: terminal ve markdown.

Patch ve test çıktısı koddan ve modelden gelir; köşeli parantez içerir. rich
onları biçim etiketi sanar ve sessizce yutar, bu yüzden her biri `escape`
edilir (AGENTS.md, "rich eats square brackets").
"""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape

from rlens import __version__
from rlens.apply.runner import BROKEN, NO_GATE, REJECTED, ApplyResult

#: Terminalde gösterilen test çıktısı satırı; tamamı raporda.
TAIL_SHOWN = 12


def _changes(result: ApplyResult) -> list[str]:
    if not result.entity:
        return []
    return [
        f"{name} {delta['before']}→{delta['after']}"
        for name, delta in result.entity.get("metrics", {}).items()
        if delta.get("direction") not in (None, "same")
    ]


def _accuracy(result: ApplyResult) -> str | None:
    predictions = result.predictions or {}
    verifiable = predictions.get("hits", 0) + predictions.get("misses", 0)
    if not verifiable:
        return None
    return f"{predictions['hits']}/{verifiable}"


def chartests_line(chartests: dict) -> str:
    """Seviye 2'nin özeti: kaç test üretildi, kaçı mevcut kodda geçti."""
    generated, kept = chartests["generated"], chartests["kept"]
    if not generated:
        return f"characterization tests: none usable ({escape(chartests.get('reason') or '')})"
    line = (
        f"characterization tests: {kept} of {generated} tests pass on the current code "
        f"({chartests['pass_rate']:.0%})"
    )
    if not kept and chartests.get("reason"):
        line += f"; {escape(chartests['reason'])}"
    return line


def render_apply(result: ApplyResult, console: Console) -> None:
    console.print(
        f"[bold]apply[/bold] {escape(result.target)}  suggestion {result.suggestion_index}: "
        f"{escape(result.title)}"
    )
    if result.outcome == REJECTED:
        console.print(f"[red]patch rejected[/] after {result.attempts} attempt(s):")
        for reason in result.rejections:
            console.print(f"  - {escape(reason)}")
    else:
        console.print(f"patch accepted on attempt {result.attempts}")

    if result.chartests is not None:
        console.print(chartests_line(result.chartests))
    if result.gate is not None:
        state = "[green]passed[/]" if result.gate.passed else "[red]failed[/]"
        detail = "timed out" if result.gate.timed_out else f"exit {result.gate.exit_code}"
        console.print(f"tests: {state} ({detail}, {result.gate.duration:.1f}s)")
        if not result.gate.passed and result.gate.output_tail:
            tail = "\n".join(result.gate.output_tail.splitlines()[-TAIL_SHOWN:])
            console.print(tail, markup=False, highlight=False)

    console.print(f"[bold]outcome: {result.outcome}[/bold]")
    changes = _changes(result)
    if changes:
        console.print(f"  {escape(', '.join(changes))}")
    accuracy = _accuracy(result)
    if accuracy:
        console.print(f"  prediction accuracy: {accuracy}")

    if result.branch and result.outcome != BROKEN:
        console.print(
            f"branch: [cyan]{escape(result.branch)}[/] — review it with "
            f"`git diff HEAD...{escape(result.branch)}`; RefactorLens never merges."
        )
    elif result.branch:
        console.print(f"failed worktree kept for inspection on {escape(result.branch)}")
    else:
        console.print("[dim]no branch was kept; your working tree is untouched.[/dim]")
    if result.outcome == NO_GATE:
        console.print(
            "[yellow]No characterization test passed on the current code, so the change "
            "could not be gated and no patch was requested.[/]"
        )


def apply_markdown(result: ApplyResult, *, root: str, generated_at: str) -> str:
    lines = [
        "# RefactorLens apply",
        "",
        f"- Project: `{root}`",
        f"- Generated: {generated_at}",
        f"- rlens: {__version__}",
        f"- Target: `{result.target}`, suggestion {result.suggestion_index}: {result.title}",
        f"- Outcome: **{result.outcome}**",
        f"- Branch: `{result.branch}`" if result.branch else "- Branch: none kept",
        f"- Attempts: {result.attempts}",
        "",
        "> RefactorLens never merges. Review the branch and merge it yourself, or delete it.",
        "",
    ]
    if result.chartests is not None:
        chartests = result.chartests
        lines += [
            "## Characterization tests (gate level 2)",
            "",
            f"- Generated: {chartests['generated']}, kept: {chartests['kept']}, "
            f"pass rate on the current code: {chartests['pass_rate']}",
            f"- Dropped: {', '.join(chartests['dropped']) or 'none'}",
            "",
        ]
        if chartests.get("code"):
            lines += ["```python", chartests["code"].rstrip("\n"), "```", ""]
    if result.rejections:
        lines += ["## Rejected replies", "", *(f"- {reason}" for reason in result.rejections), ""]
    if result.patch:
        lines += ["## Patch", "", "```diff", result.patch.rstrip("\n"), "```", ""]
    if result.gate is not None:
        gate = result.gate
        state = "passed" if gate.passed else "failed"
        detail = "timed out" if gate.timed_out else f"exit {gate.exit_code}"
        lines += ["## Behaviour gate", "", f"Level {gate.level}: {state} ({detail}).", ""]
        if gate.output_tail:
            lines += ["```", gate.output_tail, "```", ""]
    changes = _changes(result)
    if changes:
        lines += ["## Metric changes", "", *(f"- {change}" for change in changes), ""]
    accuracy = _accuracy(result)
    if accuracy:
        lines += ["## Predictions", "", f"Accuracy: {accuracy}", ""]
    return "\n".join(lines)
