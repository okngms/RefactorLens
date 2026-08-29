"""Öneri raporunun sunumu: terminal ve markdown.

İki kural sunumu belirler:

* **Modelin tahmini öne çıkarılır.** `expected_effect` sıradan bir alan değil,
  projenin ana ölçümüdür; terminalde ve raporda her önerinin altında ayrı
  satır olarak gösterilir. Faz 4 bu satırı gerçekleşen deltayla karşılaştırır.
* **Kural ihlalleri görünür kalır.** Metriğe bağlanmamış öneri, kırpılmış
  bağlam, onarım gerektirmiş cevap — hepsi raporda yazar. Gizlenseydi, çıktının
  ne kadarının sözleşmeye uyduğu ölçülemezdi.
"""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape

from rlens.advise.advisor import UNSTRUCTURED, Advice, AdviceDocument


def _safe(text: str) -> str:
    """Modelden gelen metni rich biçimlendirmesinden korur.

    Bir öneride `list[str]` geçtiğinde rich `[str]` kısmını biçim etiketi sanıp
    yutar ve kullanıcı yanlış kod görür. Modelin ürettiği hiçbir metin doğrudan
    basılmaz.
    """
    return escape(text)


#: Tahmin yönlerinin terminal gösterimi.
_DIRECTION_MARKS = {"down": "↓", "up": "↑", "same": "="}


def _effects_line(advice_suggestion) -> str:
    """`LCOM4 ↓  DCC ↑` biçiminde tek satırlık tahmin özeti."""
    if not advice_suggestion.expected_effect:
        return "(no prediction)"
    return "  ".join(
        f"{effect.metric} {_DIRECTION_MARKS.get(effect.direction, effect.direction)}"
        for effect in advice_suggestion.expected_effect
    )


def render_advice(document: AdviceDocument, console: Console) -> None:
    """Öneri belgesini terminale basar."""
    console.print(
        f"[bold]{document.root}[/bold] — "
        f"{document.provider}"
        + (f" / {document.model}" if document.model else "")
        + f", temperature {document.temperature}"
    )

    for advice in document.advices:
        console.print()
        console.print(f"[bold cyan]{_safe(advice.target)}[/bold cyan]")

        if UNSTRUCTURED in advice.tags:
            console.print(
                "  [red]The reply could not be parsed as JSON.[/] "
                "The raw text is kept in the report."
            )
            continue

        if advice.diagnosis:
            console.print(f"  [dim]{_safe(advice.diagnosis)}[/dim]")

        for index, suggestion in enumerate(advice.suggestions, start=1):
            console.print()
            marker = "" if suggestion.is_linked else " [yellow](unlinked)[/yellow]"
            console.print(f"  [bold]{index}. {_safe(suggestion.title)}[/bold]{marker}")
            if suggestion.rationale_metric_link:
                console.print(f"     evidence: {', '.join(suggestion.rationale_metric_link)}")
            console.print(f"     predicts: {_effects_line(suggestion)}")
            if suggestion.sketch:
                console.print(f"     [dim]{_safe(suggestion.sketch)}[/dim]")

        if advice.risk_notes:
            console.print(f"\n  [yellow]risks:[/] {_safe(advice.risk_notes)}")

        if advice.truncation_notes:
            console.print(
                f"  [yellow]context was truncated:[/] {'; '.join(advice.truncation_notes)}"
            )
        if advice.repaired:
            console.print("  [dim]the reply needed a repair round[/dim]")
        for warning in advice.warnings:
            console.print(f"  [yellow]![/] {_safe(warning)}")

    console.print()
    summary = f"{document.suggestion_count} suggestions across {len(document.advices)} targets"
    if document.unlinked_count:
        summary += f", {document.unlinked_count} not linked to any metric"
    console.print(summary)


def _advice_markdown(advice: Advice) -> list[str]:
    lines = [f"## {advice.target}", ""]

    if UNSTRUCTURED in advice.tags:
        lines += [
            "> The model's reply could not be parsed as JSON, even after one repair "
            "attempt. The raw text is preserved below.",
            "",
            "```",
            advice.raw_reply.strip() or "(empty reply)",
            "```",
            "",
        ]
        return lines

    if advice.diagnosis:
        lines += [advice.diagnosis, ""]

    for index, suggestion in enumerate(advice.suggestions, start=1):
        flag = "" if suggestion.is_linked else "  _(not linked to any metric)_"
        lines.append(f"### {index}. {suggestion.title}{flag}")
        lines.append("")
        if suggestion.rationale_metric_link:
            lines.append(f"**Evidence:** {', '.join(suggestion.rationale_metric_link)}")
        predictions = ", ".join(
            f"{effect.metric} {effect.direction}" for effect in suggestion.expected_effect
        )
        lines.append(f"**Predicted effect:** {predictions or 'none stated'}")
        lines.append("")
        if suggestion.sketch:
            lines += [suggestion.sketch, ""]

    if advice.risk_notes:
        lines += ["**Risks:** " + advice.risk_notes, ""]

    notes = []
    if advice.truncation_notes:
        notes.append("Context was truncated: " + "; ".join(advice.truncation_notes))
    if advice.repaired:
        notes.append("The reply needed a repair round.")
    notes.extend(advice.warnings)
    if notes:
        lines.append("_Notes:_")
        lines += [f"- {note}" for note in notes]
        lines.append("")

    return lines


def advice_markdown(document: AdviceDocument) -> str:
    """Öneri belgesinin markdown hali.

    Bu dosya insanın okuyup uygulayacağı çıktıdır; JSON ise Faz 4'ün
    `verify --advice` ile okuyacağı makine formatıdır.
    """
    lines = [
        "# RefactorLens suggestions",
        "",
        f"- **Project:** `{document.root}`",
        f"- **Generated:** {document.generated_at}",
        f"- **Provider:** {document.provider}"
        + (f" (`{document.model}`)" if document.model else ""),
        f"- **Temperature:** {document.temperature}",
        f"- **rlens:** {document.rlens_version}",
        "",
        "> Each suggestion states a **predicted effect** on the metrics. After "
        "applying a change, `rlens verify --advice` checks whether the prediction "
        "held.",
        "",
    ]

    if document.unlinked_count:
        lines += [
            f"> {document.unlinked_count} suggestion(s) were not linked to any "
            "metric. They are kept and marked rather than dropped, so that "
            "adherence to the rule can be measured.",
            "",
        ]

    for advice in document.advices:
        lines += _advice_markdown(advice)

    return "\n".join(lines).rstrip() + "\n"
