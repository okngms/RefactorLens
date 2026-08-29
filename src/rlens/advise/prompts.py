"""Prompt şablonları ve çıktı şeması.

**Projenin ana tezi buradadır.** Modele ham kod tek başına verilmez: önce
ölçülmüş metrikler kanıt olarak sunulur, sonra her önerinin bir metriğe
bağlanması ve **ölçülebilir bir tahmin** içermesi zorunlu tutulur.

İki kural özellikle dikkatle korunmalıdır:

* **Ham eşik sayıları prompt'a girmez.** Model yalnızca `warn` / `critical`
  işaretini görür. "LCOM4'ü 2'nin altına indir" bilgisi verilseydi, model
  tasarımı düzeltmek yerine sayıyı tatmin etmeyi öğrenebilirdi.
* **`expected_effect` serbest metin değildir.** Yalnızca tanımlı metrik adları
  ve `up` / `down` / `same` yönleri kabul edilir. Serbest metin bırakılsaydı
  Faz 4'te tahminin tutup tutmadığı makine tarafından karşılaştırılamazdı.
"""

from __future__ import annotations

import json

from rlens.advise.context import PromptContext

#: `expected_effect` ve `rationale_metric_link` alanlarında kabul edilen adlar.
VALID_METRICS = (
    "NOM",
    "WMC",
    "LCOM4",
    "DAM",
    "DCC",
    "CAM",
    "CC",
    "LOC",
    "PARAMS",
    "NESTING",
)

#: `expected_effect.direction` alanında kabul edilen değerler.
VALID_DIRECTIONS = ("up", "down", "same")

SYSTEM_INSTRUCTION = """\
You are a Python refactoring reviewer. You are given a code unit together with \
object-oriented design metrics measured from it by static analysis.

Rules you must follow:

1. Ground every suggestion in the measurements. Each suggestion must name at \
least one metric it addresses. Do not offer advice that the metrics do not support.
2. For every suggestion, predict its measurable effect. State, for each metric \
you expect to change, whether it will go up, down, or stay the same. Be honest \
about trade-offs: splitting a class often lowers LCOM4 while raising DCC.
3. Do not invent code that is not shown to you. Where a body has been omitted, \
say so rather than guessing what it contained.
4. Prefer a small number of substantial suggestions over many superficial ones.
5. Reply with a single JSON object and nothing else. No prose before or after, \
no markdown fences.
"""

_METRIC_GLOSSARY = {
    "NOM": "number of methods (dunders excluded)",
    "WMC": "sum of cyclomatic complexity over those methods",
    "LCOM4": "connected components in the method-attribute graph; 1 is cohesive",
    "DAM": "ratio of private attributes, 0..1",
    "DCC": "number of distinct project-internal classes referenced",
    "CAM": "cohesion among methods by parameter type, 0..1",
    "CC": "cyclomatic complexity",
    "LOC": "physical lines",
    "PARAMS": "parameter count",
    "NESTING": "deepest nesting level",
}


def output_schema() -> dict:
    """Modelden istenen JSON yapısı, örnek değerlerle."""
    return {
        "target": "module:Name",
        "diagnosis": "One paragraph on what the measurements indicate.",
        "suggestions": [
            {
                "title": "Short imperative title",
                "rationale_metric_link": ["LCOM4", "DCC"],
                "expected_effect": [
                    {"metric": "LCOM4", "direction": "down"},
                    {"metric": "DCC", "direction": "up"},
                ],
                "sketch": "How to carry out the change, in prose or brief code.",
            }
        ],
        "risk_notes": "What could break, or why this might not be worth doing.",
    }


def format_evidence(context: PromptContext) -> str:
    """Metrik kanıt bloğu.

    Ölçülen değerler ve ihlal işaretleri yer alır; **eşik sayıları yer almaz.**
    Hesaplanamayan metrikler `not computed` olarak geçer, sıfır olarak değil.
    """
    target = context.target
    lines = [f"Target: {target.qualified_name}  ({target.kind})", "", "Measurements:"]

    for metric, value in target.metrics.items():
        shown = "not computed" if value is None else value
        flag = target.violations.get(metric.lower())
        if flag is None:
            flag = target.violations.get(_violation_key(metric), None)
        marker = f"  [{flag.upper()}]" if flag else ""
        glossary = _METRIC_GLOSSARY.get(metric, "")
        lines.append(f"  {metric} = {shown}{marker}    # {glossary}")

    lines += [
        "",
        "[WARN] and [CRITICAL] mark values flagged by the project's thresholds.",
        "The threshold values themselves are deliberately not shown: aim at the "
        "design problem, not at a number.",
    ]

    if context.truncated:
        lines += [
            "",
            "NOTE: the code below is incomplete. The following were omitted to fit "
            "the context budget:",
        ]
        lines += [f"  - {note}" for note in context.truncation_notes]
        lines.append("Take this into account and do not guess at omitted code.")

    return "\n".join(lines)


def _violation_key(metric: str) -> str:
    """Metrik adı → config'teki eşik anahtarı."""
    return {
        "CC": "cyclomatic_complexity",
        "PARAMS": "max_params",
        "NESTING": "max_nesting",
    }.get(metric, metric.lower())


def build_user_prompt(context: PromptContext) -> str:
    """Modele gönderilecek kullanıcı mesajı."""
    return "\n\n".join(
        [
            format_evidence(context),
            "Code:\n```python\n" + context.as_text() + "\n```",
            "Allowed metric names: " + ", ".join(VALID_METRICS),
            "Allowed directions: " + ", ".join(VALID_DIRECTIONS),
            "Reply with exactly this JSON structure:\n" + json.dumps(output_schema(), indent=2),
        ]
    )


def build_repair_prompt(raw_reply: str, error: str) -> str:
    """Bozuk JSON için tek seferlik onarım isteği.

    Yeni bir öneri istenmez — yalnızca var olan cevabın geçerli JSON'a
    çevrilmesi istenir. Yeniden üretim istenseydi, ikinci cevap birincisinden
    farklı olur ve hangisinin değerlendirildiği belirsizleşirdi.
    """
    return (
        "Your previous reply could not be parsed as the required JSON.\n"
        f"Error: {error}\n\n"
        "Return the same content as a single valid JSON object matching the "
        "structure below. Do not add new suggestions, do not change the meaning, "
        "do not wrap it in markdown fences.\n\n"
        f"Required structure:\n{json.dumps(output_schema(), indent=2)}\n\n"
        f"Your previous reply:\n{raw_reply}"
    )
