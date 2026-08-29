"""LLM çağrısı, yanıtın ayrıştırılması ve şema doğrulaması.

Üç davranış kuralı:

1. **Bozuk JSON'da tek onarım denemesi.** Modele "bunu geçerli JSON yap" denir,
   yeni öneri istenmez. Sonsuz deneme maliyeti şişirir; hiç denememek ise küçük
   biçim hataları yüzünden iyi bir öneriyi çöpe atar.
2. **Metriğe bağlanmayan öneri silinmez, `unlinked` etiketlenir.** Projenin
   tezi "her öneri bir ölçüme dayanmalı"dır; bu teze uymayan çıktıyı gizlemek
   yerine işaretlemek, Faz 5'te "modeller bu kurala ne kadar uyuyor" sorusunu
   ölçülebilir kılar.
3. **Hiçbir şekilde ayrıştırılamayan yanıt `unstructured` olarak saklanır.**
   Ham metin atılmaz. Sessizce boş dönmek, kullanıcıya "model bir şey demedi"
   izlenimi verirdi.

`expected_effect` doğrulaması özellikle katıdır: yalnızca tanımlı metrik adları
ve `up`/`down`/`same` yönleri kabul edilir. Bu alan Faz 4'te gerçekleşen
deltayla makine tarafından karşılaştırılacaktır; serbest metin olsaydı
karşılaştırma imkânsız olurdu.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from rlens.advise.context import PromptContext
from rlens.advise.prompts import (
    SYSTEM_INSTRUCTION,
    VALID_DIRECTIONS,
    VALID_METRICS,
    build_repair_prompt,
    build_user_prompt,
)
from rlens.config import Config
from rlens.providers.base import Provider, ProviderError

#: Metriğe bağlanmamış öneriler bu etiketi alır.
UNLINKED = "unlinked"

#: Hiç ayrıştırılamayan yanıtlar bu etiketi alır.
UNSTRUCTURED = "unstructured"

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


class AdviceParseError(Exception):
    """Yanıt beklenen şemaya uymadığında yükseltilir."""


@dataclass
class ExpectedEffect:
    """Modelin ölçülebilir tahmini: bir metrik, bir yön."""

    metric: str
    direction: str

    def to_dict(self) -> dict[str, str]:
        return {"metric": self.metric, "direction": self.direction}


@dataclass
class Suggestion:
    title: str
    rationale_metric_link: list[str] = field(default_factory=list)
    expected_effect: list[ExpectedEffect] = field(default_factory=list)
    sketch: str = ""
    tags: list[str] = field(default_factory=list)
    """`unlinked` gibi işaretler."""

    @property
    def is_linked(self) -> bool:
        return bool(self.rationale_metric_link)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "rationale_metric_link": list(self.rationale_metric_link),
            "expected_effect": [effect.to_dict() for effect in self.expected_effect],
            "sketch": self.sketch,
            "tags": list(self.tags),
        }


@dataclass
class Advice:
    """Tek bir hedef için modelin cevabı."""

    target: str
    diagnosis: str = ""
    suggestions: list[Suggestion] = field(default_factory=list)
    risk_notes: str = ""
    tags: list[str] = field(default_factory=list)
    raw_reply: str = ""
    """Ayrıştırma başarısız olsa bile ham metin saklanır."""

    truncation_notes: list[str] = field(default_factory=list)
    repaired: bool = False
    """Onarım denemesi gerekmiş miydi? Faz 5'te modelleri karşılaştırırken sayılır."""

    @property
    def is_structured(self) -> bool:
        return UNSTRUCTURED not in self.tags

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["suggestions"] = [s.to_dict() for s in self.suggestions]
        return payload


def strip_code_fences(text: str) -> str:
    """Modelin JSON'u markdown çitiyle sarmasını tolere eder."""
    return _FENCE.sub("", text).strip()


def extract_json_object(text: str) -> str:
    """Metin içindeki ilk dengeli JSON nesnesini bulur.

    Modeller talimata rağmen bazen açıklama cümlesi ekler. Çitleri temizlemek
    çoğu vakayı çözer; kalanlar için ilk `{` ile eşleşen `}` arası alınır.
    """
    cleaned = strip_code_fences(text)
    start = cleaned.find("{")
    if start == -1:
        raise AdviceParseError("No JSON object found in the reply.")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(cleaned)):
        char = cleaned[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : index + 1]
    raise AdviceParseError("Unbalanced braces in the reply.")


def _validate_effects(raw: Any, errors: list[str]) -> list[ExpectedEffect]:
    """`expected_effect` doğrulaması. Geçersiz girdiler atılır ve raporlanır."""
    effects: list[ExpectedEffect] = []
    if not isinstance(raw, list):
        errors.append("expected_effect must be a list")
        return effects

    for item in raw:
        if not isinstance(item, dict):
            errors.append("expected_effect entries must be objects")
            continue
        metric = str(item.get("metric", "")).strip().upper()
        direction = str(item.get("direction", "")).strip().lower()
        if metric not in VALID_METRICS:
            errors.append(f"unknown metric in expected_effect: {metric or '(empty)'}")
            continue
        if direction not in VALID_DIRECTIONS:
            errors.append(f"invalid direction for {metric}: {direction or '(empty)'}")
            continue
        effects.append(ExpectedEffect(metric=metric, direction=direction))
    return effects


def _validate_links(raw: Any) -> list[str]:
    """`rationale_metric_link` doğrulaması; tanınmayan adlar atılır."""
    if not isinstance(raw, list):
        return []
    return [str(item).strip().upper() for item in raw if str(item).strip().upper() in VALID_METRICS]


def parse_advice(raw_reply: str, target: str) -> tuple[Advice, list[str]]:
    """Ham yanıtı `Advice` nesnesine çevirir.

    Returns:
        (advice, uyarılar). Uyarılar ölümcül değildir; atılan alanları anlatır.

    Raises:
        AdviceParseError: Yanıt hiç JSON olarak okunamazsa.
    """
    payload_text = extract_json_object(raw_reply)
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise AdviceParseError(f"Invalid JSON: {exc.msg} (line {exc.lineno})") from exc

    if not isinstance(payload, dict):
        raise AdviceParseError("Top-level JSON value must be an object.")

    warnings: list[str] = []
    suggestions: list[Suggestion] = []

    raw_suggestions = payload.get("suggestions")
    if not isinstance(raw_suggestions, list):
        raise AdviceParseError("`suggestions` must be a list.")

    for item in raw_suggestions:
        if not isinstance(item, dict):
            warnings.append("skipped a suggestion that was not an object")
            continue
        links = _validate_links(item.get("rationale_metric_link"))
        effects = _validate_effects(item.get("expected_effect"), warnings)
        tags = [] if links else [UNLINKED]
        suggestions.append(
            Suggestion(
                title=str(item.get("title", "")).strip() or "(untitled)",
                rationale_metric_link=links,
                expected_effect=effects,
                sketch=str(item.get("sketch", "")).strip(),
                tags=tags,
            )
        )

    advice = Advice(
        target=str(payload.get("target") or target),
        diagnosis=str(payload.get("diagnosis", "")).strip(),
        suggestions=suggestions,
        risk_notes=str(payload.get("risk_notes", "")).strip(),
        raw_reply=raw_reply,
    )
    return advice, warnings


def request_advice(
    provider: Provider,
    context: PromptContext,
    config: Config,
) -> tuple[Advice, list[str]]:
    """Bir hedef için modelden öneri ister ve yanıtı doğrular.

    Ayrıştırma başarısız olursa **bir kez** onarım denenir. O da başarısız
    olursa ham metin `unstructured` etiketiyle döndürülür; asla sessizce
    boş dönülmez.

    Raises:
        ProviderError: Ağ, yetki veya yapılandırma sorunlarında.
    """
    target_name = context.target.qualified_name
    user_prompt = build_user_prompt(context)

    raw = provider.generate(
        SYSTEM_INSTRUCTION, user_prompt, config.provider, config.advise.temperature
    )

    try:
        advice, warnings = parse_advice(raw, target_name)
        advice.truncation_notes = list(context.truncation_notes)
        return advice, warnings
    except AdviceParseError as exc:
        # `except` değişkeni blok sonunda silinir; mesajı dışarı taşıyoruz.
        first_error = str(exc)

    # Tek onarım denemesi: yeni öneri değil, aynı içeriğin geçerli JSON hali.
    try:
        repaired_raw = provider.generate(
            SYSTEM_INSTRUCTION,
            build_repair_prompt(raw, first_error),
            config.provider,
            config.advise.temperature,
        )
    except ProviderError:
        repaired_raw = ""

    if repaired_raw:
        try:
            advice, warnings = parse_advice(repaired_raw, target_name)
            advice.repaired = True
            advice.truncation_notes = list(context.truncation_notes)
            warnings.insert(0, f"reply needed repair: {first_error}")
            return advice, warnings
        except AdviceParseError:
            pass

    return (
        Advice(
            target=target_name,
            diagnosis="",
            suggestions=[],
            risk_notes="",
            tags=[UNSTRUCTURED],
            raw_reply=raw,
            truncation_notes=list(context.truncation_notes),
            repaired=True,
        ),
        [f"could not parse the reply even after repair: {first_error}"],
    )
