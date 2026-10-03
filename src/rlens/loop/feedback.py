"""Önceki denemenin sonucunu modele anlatan blok (`docs/02` §4).

`advise/prompts.py` deney protokolü gereği donmuş kalır; blok `request_advice`
istemin sonuna eklenir. Yalnızca yönler ve kapı/arayüz durumu söylenir:

* **Ham eşik sayısı yok** (invariant). Ölçülen değer de yok; tahmin yön
  üzerinden yapıldı, geri bildirim de yön üzerinden verilir.
* Doğrulanamayan tahmin "yanlış" diye söylenmez; ölçülemediği söylenir
  (invariant: doğrulanamayan oranın dışındadır).
* Kapıyı geçmeyen değişikliğin metrikleri sayılmaz ve söylenmez.
"""

from __future__ import annotations

from rlens.apply.runner import BROKEN, REJECTED, SUSPICIOUS, ApplyResult

HEADER = "## Feedback from previous attempt"


def _prediction_lines(predictions: dict | None) -> list[str]:
    lines = []
    for suggestion in (predictions or {}).get("suggestions", []):
        for check in suggestion.get("checks", []):
            metric, predicted = check.get("metric"), check.get("predicted")
            if check.get("outcome") == "hit":
                lines.append(f"Prediction {metric}: {predicted} — actual: {check['actual']} (✓).")
            elif check.get("outcome") == "miss":
                lines.append(f"Prediction {metric}: {predicted} — actual: {check['actual']} (✗).")
            else:
                lines.append(f"Prediction {metric}: {predicted} — could not be measured.")
    return lines


def build_feedback(result: ApplyResult) -> str:
    lines = [HEADER, f'Your previous suggestion: "{result.title}".']
    if result.outcome == REJECTED:
        reason = result.rejections[-1] if result.rejections else "no usable patch"
        lines += [
            f"Your patch could not be applied: {reason}",
            "Propose a revised change, and send a patch that applies to the code as shown.",
        ]
        return "\n".join(lines) + "\n"
    if result.outcome == BROKEN:
        lines += [
            "Behavior gate: failed. The change broke the tests, so its metrics do not count.",
            "Propose a revised change that keeps the program's behaviour.",
        ]
        return "\n".join(lines) + "\n"

    lines += _prediction_lines(result.predictions)
    lines.append("Behavior gate: passed.")
    if result.outcome == SUSPICIOUS:
        lines.append("Public interface: members were deleted (flagged as suspicious).")
    else:
        lines.append("Public interface: no member was deleted.")
    lines.append("Explain why the structural predictions missed, then propose a revised change.")
    return "\n".join(lines) + "\n"
