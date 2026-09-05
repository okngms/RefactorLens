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
from rlens.analysis.model import ADVICE_SCHEMA_VERSION
from rlens.config import Config
from rlens.llm.budget import Budget, BudgetExceeded
from rlens.llm.cache import ResponseCache, prompt_hash
from rlens.providers.base import Provider, ProviderError

#: Öneri durumları (SPEC §6). Hiçbir öneri silinmez; oranlar raporlanır.
LINKED = "linked"
UNLINKED = "unlinked"
REJECTED = "rejected"

#: Hiç ayrıştırılamayan yanıtlar bu etiketi alır.
UNSTRUCTURED = "unstructured"

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


class AdviceParseError(Exception):
    """Yanıt beklenen şemaya uymadığında yükseltilir."""


@dataclass
class ExpectedEffect:
    """Modelin ölçülebilir tahmini: bir metrik, bir yön, opsiyonel güven."""

    metric: str
    direction: str
    confidence: float | None = None
    """0-1 arası öz-güven. **Opsiyoneldir ve yokluğu öneriyi düşürmez.**

    Kalibrasyon ölçümü değerlidir, ama zorunlu tutmak veremeyeceği bir sayıyı
    uyduran modellerle sonucu kirletir. `verify` yalnızca verilmiş güvenleri
    Brier ve ECE hesabına katar."""

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "direction": self.direction,
            "confidence": self.confidence,
        }


@dataclass
class Suggestion:
    title: str
    rationale_metric_link: list[str] = field(default_factory=list)
    expected_effect: list[ExpectedEffect] = field(default_factory=list)
    sketch: str = ""
    status: str = LINKED
    """`linked` / `unlinked` / `rejected`. Hiçbir öneri silinmez."""

    addresses_smells: list[str] = field(default_factory=list)
    target_layer_after: str | None = None
    claims_constraints_respected: bool | None = None
    """Modelin **beyanı**. Aracın kendi değerlendirmesiyle karşılaştırılır."""

    constraint_agreement: bool | None = None
    """Beyan ile araç değerlendirmesi uyuştu mu? 5a'nın ölçütlerinden biri."""

    notes: list[str] = field(default_factory=list)

    @property
    def is_linked(self) -> bool:
        return bool(self.rationale_metric_link)

    @property
    def is_rejected(self) -> bool:
        return self.status == REJECTED

    @property
    def tags(self) -> list[str]:
        """Geriye uyumluluk: eski raporlar `tags` alanını okuyor."""
        return [] if self.status == LINKED else [self.status]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "rationale_metric_link": list(self.rationale_metric_link),
            "expected_effect": [effect.to_dict() for effect in self.expected_effect],
            "sketch": self.sketch,
            "status": self.status,
            "addresses_smells": list(self.addresses_smells),
            "target_layer_after": self.target_layer_after,
            "claims_constraints_respected": self.claims_constraints_respected,
            "constraint_agreement": self.constraint_agreement,
            "notes": list(self.notes),
            "tags": self.tags,
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

    warnings: list[str] = field(default_factory=list)
    """Atılan alanlar ve şema ihlalleri. Ölümcül değildir ama gizlenmez."""

    prompt_hash: str = ""
    """Gönderilen prompt'un özeti. İki koşunun aynı prompt'la yapıldığını
    kanıtlamanın tek yolu budur; A/B deneylerinde zorunludur."""

    from_cache: bool = False
    """Yanıt önbellekten mi geldi? Maliyet ve tekrarlanabilirlik için kaydedilir."""

    @property
    def is_structured(self) -> bool:
        return UNSTRUCTURED not in self.tags

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["suggestions"] = [s.to_dict() for s in self.suggestions]
        return payload


@dataclass
class AdviceDocument:
    """Tek bir `advise` çalıştırmasının tam çıktısı.

    Sağlayıcı, model ve sıcaklık kaydedilir: Faz 5 deneyi "hangi model, hangi
    ayarla" sorusuna cevap veremezse karşılaştırma yapılamaz.
    """

    root: str
    generated_at: str
    rlens_version: str
    provider: str
    model: str | None
    temperature: float
    schema_version: int = ADVICE_SCHEMA_VERSION
    advices: list[Advice] = field(default_factory=list)
    budget: dict = field(default_factory=dict)
    cache: dict = field(default_factory=dict)
    partial: bool = False
    """Bütçe dolduğu için bazı hedefler atlandıysa rapor kısmidir ve bunu söyler."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "rlens_version": self.rlens_version,
            "generated_at": self.generated_at,
            "root": self.root,
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "budget": self.budget,
            "cache": self.cache,
            "partial": self.partial,
            "advices": [advice.to_dict() for advice in self.advices],
        }

    @property
    def suggestion_count(self) -> int:
        return sum(len(advice.suggestions) for advice in self.advices)

    @property
    def unlinked_count(self) -> int:
        """Hiçbir metriğe bağlanmayan öneri sayısı — projenin tezine uymayanlar."""
        return sum(
            1
            for advice in self.advices
            for suggestion in advice.suggestions
            if not suggestion.is_linked
        )

    @property
    def rejected_count(self) -> int:
        """Katman kurallarını çiğnediği için reddedilen öneri sayısı."""
        return sum(
            1
            for advice in self.advices
            for suggestion in advice.suggestions
            if suggestion.is_rejected
        )

    @property
    def constraint_disagreements(self) -> int:
        """Modelin kısıt beyanının araç değerlendirmesiyle çeliştiği durumlar."""
        return sum(
            1
            for advice in self.advices
            for suggestion in advice.suggestions
            if suggestion.constraint_agreement is False
        )


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

        confidence = item.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                errors.append(f"non-numeric confidence for {metric}")
                confidence = None
            else:
                if not 0.0 <= confidence <= 1.0:
                    errors.append(f"confidence for {metric} outside 0-1: {confidence}")
                    confidence = None

        effects.append(ExpectedEffect(metric=metric, direction=direction, confidence=confidence))
    return effects


def _validate_links(raw: Any) -> list[str]:
    """`rationale_metric_link` doğrulaması; tanınmayan adlar atılır."""
    if not isinstance(raw, list):
        return []
    return [str(item).strip().upper() for item in raw if str(item).strip().upper() in VALID_METRICS]


def validate_constraints(
    raw: dict, advice_target, scheme
) -> tuple[str | None, bool | None, list[str]]:
    """Öneriyi katman kurallarına karşı **bağımsız** denetler.

    Modelin `constraints_respected: true` demesi yeterli değildir: beyan da bir
    çıktıdır ve yanlış olabilir. Araç kendi değerlendirmesini yapar ve
    uyuşmazlığı ayrıca sayar — 5a'nın ölçütlerinden biri budur.

    Araç tarafı denetim bilinçli olarak **dar** tutulmuştur: taslak metninden
    hangi importların ekleneceğini çıkarmak güvenilir değildir. Yalnızca
    doğrulanabilir olan denetlenir.

    Returns:
        (reddetme nedeni ya da None, beyanla uyuşma ya da None, notlar)
    """
    notes: list[str] = []
    claim = raw.get("constraints_respected")
    claim = bool(claim) if isinstance(claim, bool) else None

    destination = raw.get("target_layer_after")
    destination = str(destination).strip() if destination else None

    tool_verdict: bool | None = None
    reason: str | None = None

    if scheme is not None and destination:
        if destination not in scheme.layers:
            tool_verdict = False
            reason = (
                f"target_layer_after `{destination}` is not a layer in this project "
                f"({', '.join(scheme.layers)})"
            )
        else:
            tool_verdict = True

    if claim is False:
        tool_verdict = False
        reason = reason or "the model states the suggestion breaks the layer rules"

    agreement = None if claim is None or tool_verdict is None else claim == tool_verdict
    if agreement is False:
        notes.append(f"the model claims constraints_respected={claim} but the tool disagrees")

    if advice_target is not None:
        known = set(advice_target.smell_labels)
        claimed = [str(s) for s in raw.get("addresses_smells", []) if str(s)]
        unknown = [s for s in claimed if s not in known]
        if unknown:
            notes.append(
                f"addresses_smells names labels the target does not carry: "
                f"{', '.join(sorted(unknown))}"
            )

    return reason, agreement, notes


def parse_advice(
    raw_reply: str,
    target: str,
    *,
    advice_target=None,
    scheme=None,
) -> tuple[Advice, list[str]]:
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
        reason, agreement, notes = validate_constraints(item, advice_target, scheme)

        if reason:
            status = REJECTED
            notes.insert(0, reason)
        elif links:
            status = LINKED
        else:
            status = UNLINKED

        suggestions.append(
            Suggestion(
                title=str(item.get("title", "")).strip() or "(untitled)",
                rationale_metric_link=links,
                expected_effect=effects,
                sketch=str(item.get("sketch", "")).strip(),
                status=status,
                addresses_smells=[str(s) for s in item.get("addresses_smells", []) if str(s)],
                target_layer_after=(
                    str(item["target_layer_after"]).strip()
                    if item.get("target_layer_after")
                    else None
                ),
                claims_constraints_respected=(
                    item["constraints_respected"]
                    if isinstance(item.get("constraints_respected"), bool)
                    else None
                ),
                constraint_agreement=agreement,
                notes=notes,
            )
        )

    # Hedef adı **modelden alınmaz**. Model şemadaki `"module:Name"` yer
    # tutucusunu olduğu gibi kopyalayabilir (gözlemlendi) ve o ad hiçbir sınıfa
    # karşılık gelmez. `verify --advice` öneriyi sınıfla bu adla eşleştireceği
    # için, doğrulanamayan bir dizgeye güvenmek Faz 4'ü sessizce kırar.
    echoed = str(payload.get("target") or "").strip()
    if echoed and echoed != target:
        warnings.append(f"model reported target {echoed!r}; using {target!r} instead")

    advice = Advice(
        target=target,
        diagnosis=str(payload.get("diagnosis", "")).strip(),
        suggestions=suggestions,
        risk_notes=str(payload.get("risk_notes", "")).strip(),
        raw_reply=raw_reply,
    )
    return advice, warnings


def _generate(
    provider: Provider,
    system: str,
    user: str,
    config: Config,
    cache: ResponseCache | None,
    budget: Budget | None,
    label: str,
    cache_salt: str = "",
) -> tuple[str, str, bool]:
    """Bir modeli çağırır; önbellek ve bütçeyi hesaba katar.

    Sıra bilinçlidir: **önce önbellek, sonra bütçe.** Önbellekten dönen yanıt
    para harcamadığı için bütçeden düşmez; tersi sırada, tekrarlanan bir koşu
    hiç çağrı yapmadan bütçeyi tüketirdi.

    Returns:
        (yanıt, prompt_hash, önbellekten_mi)

    Raises:
        BudgetExceeded: Çağrı sınırına ulaşıldıysa.
    """
    # `Provider` protokolü `name` ister; yokluğunda önbellek anahtarı yine
    # üretilmeli, yoksa sözleşmeyi tam uygulamayan bir adapter çöker.
    provider_name = getattr(provider, "name", config.provider.name)
    key = prompt_hash(provider_name, config.provider.model, system + "\n" + user, cache_salt)

    if cache is not None:
        cached = cache.get(key)
        if cached is not None:
            if budget is not None:
                budget.record_cache_hit()
            return cached, key, True

    if budget is not None:
        budget.check(label)

    reply = provider.generate(system, user, config.provider, config.advise.temperature)

    if budget is not None:
        budget.record_call(len(user) // 4, len(reply) // 4)
    if cache is not None:
        cache.set(key, reply, meta={"target": label, "model": config.provider.model})
    return reply, key, False


def request_advice(
    provider: Provider,
    context: PromptContext,
    config: Config,
    *,
    cache: ResponseCache | None = None,
    budget: Budget | None = None,
    scheme=None,
    metric_rules: bool = False,
    cache_salt: str = "",
) -> tuple[Advice, list[str]]:
    """Bir hedef için modelden öneri ister ve yanıtı doğrular.

    Ayrıştırma başarısız olursa **bir kez** onarım denenir. O da başarısız
    olursa ham metin `unstructured` etiketiyle döndürülür; asla sessizce
    boş dönülmez.

    Raises:
        ProviderError: Ağ, yetki veya yapılandırma sorunlarında.
    """
    target_name = context.target.qualified_name
    user_prompt = build_user_prompt(context, scheme=scheme, metric_rules=metric_rules)

    raw, key, cached = _generate(
        provider,
        SYSTEM_INSTRUCTION,
        user_prompt,
        config,
        cache,
        budget,
        target_name,
        cache_salt,
    )

    try:
        advice, warnings = parse_advice(
            raw, target_name, advice_target=context.target, scheme=scheme
        )
        advice.truncation_notes = list(context.truncation_notes)
        advice.prompt_hash = key
        advice.from_cache = cached
        return advice, warnings
    except AdviceParseError as exc:
        # `except` değişkeni blok sonunda silinir; mesajı dışarı taşıyoruz.
        first_error = str(exc)

    # Tek onarım denemesi: yeni öneri değil, aynı içeriğin geçerli JSON hali.
    try:
        repaired_raw, _, _ = _generate(
            provider,
            SYSTEM_INSTRUCTION,
            build_repair_prompt(raw, first_error),
            config,
            cache,
            budget,
            f"{target_name} (repair)",
            cache_salt,
        )
    except (ProviderError, BudgetExceeded):
        # Onarım bütçeye takılırsa ham metin yine saklanır; sessizce boş dönülmez.
        repaired_raw = ""

    if repaired_raw:
        try:
            advice, warnings = parse_advice(
                repaired_raw, target_name, advice_target=context.target, scheme=scheme
            )
            advice.repaired = True
            advice.truncation_notes = list(context.truncation_notes)
            advice.prompt_hash = key
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
            prompt_hash=key,
            from_cache=cached,
        ),
        [f"could not parse the reply even after repair: {first_error}"],
    )
