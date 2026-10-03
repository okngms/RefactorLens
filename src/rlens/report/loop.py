"""`loop` çıktısı: terminal ve markdown."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from rlens import __version__
from rlens.loop.runner import STOP_TEXT, LoopResult


def _fmt(value, pattern="{:.0%}") -> str:
    return "—" if value is None else pattern.format(value)


def _gate(value) -> str:
    return "—" if value is None else ("passed" if value else "failed")


def render_loop(result: LoopResult, console: Console) -> None:
    payload = result.to_dict()
    table = Table(title=f"loop {escape(result.target)}", title_justify="left", header_style="bold")
    for column in ("#", "Suggestion", "Outcome", "Tests", "Predictions", "Brier", "Calls"):
        table.add_column(column, justify="right" if column in ("#", "Brier", "Calls") else "left")
    for item in result.iterations:
        verifiable = item.hits + item.misses
        predictions = f"{item.hits}/{verifiable}" if verifiable else "—"
        if item.unverifiable:
            predictions += f" (+{item.unverifiable} unverifiable)"
        table.add_row(
            str(item.number),
            escape(item.title or "—"),
            item.outcome or "—",
            _gate(item.gate_passed),
            predictions,
            _fmt(item.brier, "{:.3f}"),
            str(item.calls),
        )
    console.print(table)
    overall = payload["overall"]
    console.print(
        f"stopped: {STOP_TEXT[result.stop_reason]}. Overall prediction accuracy "
        f"{_fmt(overall['accuracy'])}, tests passed {_fmt(overall['gate_pass_rate'])}, "
        f"suspicious {_fmt(overall['suspicious_rate'])}, Brier {_fmt(overall['brier'], '{:.3f}')}."
    )
    branches = [item.branch for item in result.iterations if item.branch]
    if branches:
        console.print("branches to review (RefactorLens never merges):")
        for branch in branches:
            console.print(f"  [cyan]{escape(branch)}[/]")


def loop_markdown(result: LoopResult, *, root: str, generated_at: str) -> str:
    payload = result.to_dict()
    overall = payload["overall"]
    lines = [
        "# RefactorLens loop",
        "",
        f"- Project: `{root}`",
        f"- Generated: {generated_at}",
        f"- rlens: {__version__}",
        f"- Target: `{result.target}`, at most {result.max_iter} iterations",
        f"- Stopped: {STOP_TEXT[result.stop_reason]}",
        "",
        "Each iteration starts from HEAD; changes do not build on each other.",
        "",
        "| # | Suggestion | Outcome | Tests | Hits | Misses | Unverifiable | Brier | Calls |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for item in result.iterations:
        lines.append(
            f"| {item.number} | {item.title or '—'} | {item.outcome or '—'} | "
            f"{_gate(item.gate_passed)} | {item.hits} | {item.misses} | {item.unverifiable} | "
            f"{_fmt(item.brier, '{:.3f}')} | {item.calls} |"
        )
    lines += [
        "",
        f"Overall: accuracy {_fmt(overall['accuracy'])}, tests passed "
        f"{_fmt(overall['gate_pass_rate'])}, suspicious {_fmt(overall['suspicious_rate'])}, "
        f"Brier {_fmt(overall['brier'], '{:.3f}')}, ECE {_fmt(overall['ece'], '{:.3f}')}.",
        "",
    ]
    for item in result.iterations:
        if item.feedback:
            lines += [
                f"## Feedback given before iteration {item.number}",
                "",
                "```",
                item.feedback.rstrip("\n"),
                "```",
                "",
            ]
        if item.branch:
            lines += [f"Iteration {item.number} branch: `{item.branch}`", ""]
    return "\n".join(lines)
