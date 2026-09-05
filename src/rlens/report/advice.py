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
    """`LCOM4 ↓ 0.8   DCC ↑` biçiminde tahmin özeti.

    Güven varsa gösterilir; yoksa gösterilmez. Eksik güven bir kusur değildir.
    """
    if not advice_suggestion.expected_effect:
        return "(no prediction)"
    parts = []
    for effect in advice_suggestion.expected_effect:
        mark = _DIRECTION_MARKS.get(effect.direction, effect.direction)
        text = f"{effect.metric} {mark}"
        if effect.confidence is not None:
            text += f" {effect.confidence:.2f}"
        parts.append(text)
    return "   ".join(parts)


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
            if suggestion.is_rejected:
                marker = " [red](rejected)[/red]"
            elif not suggestion.is_linked:
                marker = " [yellow](unlinked)[/yellow]"
            else:
                marker = ""
            console.print(f"  [bold]{index}. {_safe(suggestion.title)}[/bold]{marker}")
            if suggestion.rationale_metric_link:
                console.print(f"     evidence: {', '.join(suggestion.rationale_metric_link)}")
            console.print(f"     predicts: {_effects_line(suggestion)}")
            if suggestion.target_layer_after:
                console.print(f"     destination layer: {suggestion.target_layer_after}")
            if suggestion.addresses_smells:
                console.print(f"     addresses: {', '.join(suggestion.addresses_smells)}")
            for note in suggestion.notes:
                console.print(f"     [yellow]![/] {_safe(note)}")
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
    suggestions = document.suggestion_count
    targets = len(document.advices)
    summary = (
        f"{suggestions} {'suggestion' if suggestions == 1 else 'suggestions'} "
        f"across {targets} {'target' if targets == 1 else 'targets'}"
    )
    if document.unlinked_count:
        summary += f", {document.unlinked_count} not linked to any metric"
    if document.rejected_count:
        summary += f", {document.rejected_count} rejected"
    console.print(summary)
    if document.constraint_disagreements:
        console.print(
            f"[yellow]{document.constraint_disagreements} suggestion(s) claim to "
            f"respect the layer rules but do not.[/]"
        )


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
        if suggestion.is_rejected:
            flag = "  _(rejected: breaks the layer rules)_"
        elif not suggestion.is_linked:
            flag = "  _(not linked to any metric)_"
        else:
            flag = ""
        lines.append(f"### {index}. {suggestion.title}{flag}")
        lines.append("")
        if suggestion.rationale_metric_link:
            # Liste öğesi olarak yazılır: markdown ardışık satırları tek paragrafta
            # birleştirir, düz satır olsalardı render edildiğinde "Evidence: ...
            # Predicted effect: ..." tek satır halinde yapışırdı.
            lines.append(f"- **Evidence:** {', '.join(suggestion.rationale_metric_link)}")
        predictions = ", ".join(
            f"{effect.metric} {effect.direction}"
            + (f" ({effect.confidence:.2f})" if effect.confidence is not None else "")
            for effect in suggestion.expected_effect
        )
        lines.append(f"- **Predicted effect:** {predictions or 'none stated'}")
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
        # Başlık ile liste arasında boş satır: katı ayrıştırıcılar boş satır
        # olmadan listeyi paragrafın devamı sayar.
        lines.append("_Notes:_")
        lines.append("")
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
