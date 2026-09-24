"""`explain` çıktısı: terminal ve markdown.

Modelden gelen her metin `escape` edilir. Bu teorik bir önlem değil: rich
`console.print()` içinde `[...]` gördüğünde onu biçim etiketi sanar ve
`self._orders[key]` ifadesi `self._orders` olarak basılır. Hata sessizdir —
kullanıcı yanlış metni doğru sanarak okur.
"""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape

from rlens import __version__
from rlens.explain.explainer import UNLINKED, Explanation
from rlens.explain.template import TemplateReading


def _safe(text: str) -> str:
    return escape(text)


#: Terminalde gösterilecek en fazla özne. İlk koşularda model tek bir tespite
#: on özne bağladı ve satır okunamaz hale geldi; öznelerin tamamı yine JSON ve
#: markdown raporunda durur.
MAX_SUBJECTS_SHOWN = 3


def _subject_line(subjects: list[str]) -> str:
    if not subjects:
        return "(no subject)"
    shown = subjects[:MAX_SUBJECTS_SHOWN]
    line = ", ".join(shown)
    if len(subjects) > len(shown):
        line += f" (+{len(subjects) - len(shown)} more)"
    return line


def render_explanation(explanation: Explanation, console: Console) -> None:
    """Yorum raporunu terminale basar."""
    if not explanation.is_structured:
        console.print(
            "[yellow]The model's reply could not be parsed as JSON.[/] "
            "It is kept verbatim below and in the report."
        )
        console.print(_safe(explanation.raw_reply or ""))
        return

    if explanation.summary:
        console.print(_safe(explanation.summary))
        console.print()

    for finding in explanation.findings:
        subjects = _safe(_subject_line(finding.subjects))
        if finding.status == UNLINKED:
            # Silinmez, işaretlenir: modelin sözleşmeyi ne sıklıkla göz ardı
            # ettiği ancak bu tespitler durursa ölçülebilir.
            tag = "[yellow]unlinked[/yellow]"
        else:
            tag = f"[dim]{', '.join(finding.metric_link)}[/dim]"
        console.print(f"[bold cyan]{subjects}[/bold cyan]  {tag}")
        console.print(f"  {_safe(finding.statement)}")
        if finding.graded:
            console.print(f"  [yellow]graded language:[/yellow] {', '.join(finding.graded)}")
        console.print()

    if explanation.not_shown:
        console.print("[dim]Not shown by these measurements:[/dim]")
        console.print(f"  {_safe(explanation.not_shown)}")
        console.print()

    total = len(explanation.findings)
    # Tekil/çoğul ayrımı: "1 observations" iki kez yakalandı, testi var.
    noun = "finding" if total == 1 else "findings"
    line = f"[dim]{total} {noun}"
    if explanation.unlinked_count:
        line += f", {explanation.unlinked_count} not linked to a metric"
    if explanation.single_metric_count:
        line += f", {explanation.single_metric_count} resting on a single measurement"
    if explanation.from_cache:
        line += ", from cache"
    console.print(line + "[/dim]")
    if explanation.graded_count:
        console.print(
            f"[yellow]{explanation.graded_count} finding(s) graded a value[/] — "
            "a threshold is a cut-off in the measured distribution, not a verdict "
            "on the code, and it is not shown to the model."
        )

    console.print(
        "[dim]This is a reading of the measurements, not a verdict on the code, "
        "and it is not scored anywhere.[/dim]"
    )


def explanation_markdown(explanation: Explanation, *, root: str, generated_at: str) -> str:
    """Yorum raporunun markdown hali."""
    lines = [
        "# Explanation",
        "",
        f"- Project: `{root}`",
        f"- Generated: {generated_at}",
        f"- rlens: {__version__}",
        f"- Model: {explanation.model or 'unknown'}",
        f"- Prompt hash: `{explanation.prompt_hash}`",
        "",
        "> A reading of the measurements, not a verdict on the code. This output "
        "is not scored and does not enter any accuracy figure.",
        "",
    ]

    if not explanation.is_structured:
        lines += [
            "## Unparsed reply",
            "",
            "The model did not return a JSON object. Kept verbatim:",
            "",
            "```",
            explanation.raw_reply or "",
            "```",
            "",
        ]
        return "\n".join(lines)

    if explanation.summary:
        lines += ["## Summary", "", explanation.summary, ""]

    lines += ["## Findings", ""]
    for index, finding in enumerate(explanation.findings, start=1):
        links = ", ".join(finding.metric_link) if finding.metric_link else "unlinked"
        lines += [
            f"### {index}. {', '.join(finding.subjects) or '(no subject)'}",
            "",
            f"- Rests on: {links}",
        ]
        if finding.graded:
            lines.append(
                f"- Graded language (against the instruction): {', '.join(finding.graded)}"
            )
        lines += ["", finding.statement, ""]

    if explanation.not_shown:
        lines += ["## Not shown by these measurements", "", explanation.not_shown, ""]

    total = len(explanation.findings)
    noun = "finding" if total == 1 else "findings"
    lines += [
        "## Contract",
        "",
        f"- {total} {noun}",
        f"- {explanation.unlinked_count} not linked to a metric",
        f"- {explanation.single_metric_count} resting on a single measurement and subject",
        f"- {explanation.graded_count} using grading language the instruction forbids",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# `--no-llm`: şablon okuması
# --------------------------------------------------------------------------- #

_TEMPLATE_NOTE = (
    "Template reading: each sentence restates a measured value, its definition and "
    "the threshold it meets. No model was called. A threshold is a cut-off in the "
    "measured distribution, not a verdict on the code."
)


def _without_subject(sentence) -> str:
    """Başlık zaten özneyi söylüyor; cümle başındaki "özne: " tekrarlanmaz.

    JSON'daki metin tam kalır: tek başına okunabilmeli.
    """
    prefix = f"{sentence.subject}: "
    return sentence.text.removeprefix(prefix)


def render_template(reading: TemplateReading, console: Console) -> None:
    """Şablon okumasını terminale basar. Metin koddan türer; `escape` şart."""
    for line in reading.summary:
        console.print(_safe(line))
    console.print()
    subject = None
    for sentence in reading.sentences:
        if sentence.subject != subject:
            subject = sentence.subject
            console.print(f"[bold cyan]{_safe(subject)}[/bold cyan]")
        console.print(f"  {_safe(_without_subject(sentence))}")
    if reading.sentences:
        console.print()
    if reading.not_computed:
        console.print("[dim]Not computed:[/dim]")
        for note in reading.not_computed:
            console.print(f"  {_safe(note)}")
        console.print()
    console.print(f"[dim]{_safe(_TEMPLATE_NOTE)}[/dim]")


def template_markdown(reading: TemplateReading, *, root: str, generated_at: str) -> str:
    """Şablon okumasının markdown hali."""
    lines = [
        "# Explanation (template)",
        "",
        f"- Project: `{root}`",
        f"- Generated: {generated_at}",
        f"- rlens: {__version__}",
        "- Mode: template, no model called",
        "",
        f"> {_TEMPLATE_NOTE}",
        "",
        "## Summary",
        "",
        *(f"- {line}" for line in reading.summary),
        "",
        "## Findings",
        "",
    ]
    subject = None
    for sentence in reading.sentences:
        if sentence.subject != subject:
            subject = sentence.subject
            lines += ["", f"### `{subject}`", ""]
        lines.append(f"- {_without_subject(sentence)}")
    if not reading.sentences:
        lines.append("No threshold is met and no smell is flagged.")
    lines.append("")
    if reading.not_computed:
        lines += ["## Not computed", "", *(f"- {note}" for note in reading.not_computed), ""]
    return "\n".join(lines)
