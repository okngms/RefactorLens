"""Yorum isteği, ayrıştırma ve doğrulama.

`advise` ile aynı iki ilkeyi paylaşır:

* **Hiçbir gözlem silinmez.** Metriğe bağlanmayan gözlem `unlinked` etiketiyle
  raporda kalır; hiç ayrıştırılamayan yanıt `unstructured` etiketiyle ham
  metnini korur. Silinirse modelin sözleşmeyi ne sıklıkla göz ardı ettiği
  ölçülemez.
* **Geçersiz metrik adları düşürülür ama sessizce değil.** Uydurulmuş bir
  metrik adı `warnings` listesine yazılır.

`advise`'dan ayrıldığı yer: bu çıktı **doğruluk oranına ve FINDINGS'e girmez**
(`docs/v2.1-explain.md` §3). "Bu sınıf çok fazla sorumluluk taşıyor" cümlesi ne
doğrulanabilir ne çürütülebilir; advise/verify döngüsünün tüm değeri, modelin
yanılabilir bir iddiaya bağlanmasıydı.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from rlens.advise.advisor import AdviceParseError, extract_json_object
from rlens.advise.prompts import VALID_METRICS
from rlens.analysis.model import EXPLAIN_SCHEMA_VERSION
from rlens.config import Config
from rlens.explain.prompts import SYSTEM_INSTRUCTION, build_user_prompt
from rlens.llm.budget import Budget
from rlens.llm.cache import ResponseCache, prompt_hash
from rlens.providers.base import Provider

#: Gözlem durumları. `advise`'ın etiketleriyle aynı adlar kullanılır: iki
#: raporu okuyan tek bir gözün iki sözlük öğrenmesi gerekmesin.
LINKED = "linked"
UNLINKED = "unlinked"
UNSTRUCTURED = "unstructured"

#: Kalibrasyona dayalı sıfatlar. Bunların hiçbirinin dayanağı yok: `wmc: 50`
#: eşiği Java'dan geliyor ve Python persentilleri henüz ölçülmedi
#: (`docs/v2-sertlestirme.md` Blok 1).
#:
#: Liste **etiketlemek** için var, silmek için değil. İlk gerçek koşuda model,
#: talimatta birebir yasaklanmış olmasına rağmen "low", "limited", "fragmented"
#: ve "moderate" kelimelerini kullandı. Talimatın tutup tutmadığı ancak
#: ihlaller sayılabilirse bilinir; sessizce kabul etmek onu ölçülemez yapar.
GRADED_TERMS = frozenset(
    {
        "high",
        "low",
        "good",
        "bad",
        "poor",
        "excellent",
        "healthy",
        "concerning",
        "limited",
        "fragmented",
        "moderate",
        "severe",
        "weak",
        "strong",
        "problematic",
        "optimal",
        "maximal",
        "minimal",
        "acceptable",
    }
)

_WORD = re.compile(r"[a-z]+")


def graded_terms(statement: str) -> list[str]:
    """Cümledeki derecelendirme sıfatlarını bulur.

    Kelime sınırına bakar: "lower" ve "slowly" eşleşmez, "low" eşleşir. Basit
    olması kasıtlı — amaç dil analizi değil, talimatın tutup tutmadığını
    sayılabilir kılmak.
    """
    words = set(_WORD.findall(statement.lower()))
    return sorted(words & GRADED_TERMS)


@dataclass
class Finding:
    """Birden fazla ölçümü ya da özneyi birleştiren tek bir tespit.

    `subjects` çoğuldur ve bu şeklin kendisi bir kısıttır: ilk şema sınıf
    başına tek gözlem istiyordu ve model tam onu verdi — tabloyu satır satır
    tekrarladı. Sentez istemek için şemanın sentezi mümkün kılması gerekiyor.
    """

    statement: str
    subjects: list[str] = field(default_factory=list)
    metric_link: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return LINKED if self.metric_link else UNLINKED

    @property
    def graded(self) -> list[str]:
        return graded_terms(self.statement)

    def to_dict(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "subjects": list(self.subjects),
            "metric_link": list(self.metric_link),
            "status": self.status,
            "graded_terms": self.graded,
        }


@dataclass
class Explanation:
    """Bir yorum raporunun tamamı."""

    summary: str = ""
    findings: list[Finding] = field(default_factory=list)
    not_shown: str = ""
    raw_reply: str | None = None
    prompt_hash: str = ""
    model: str = ""
    from_cache: bool = False

    @property
    def is_structured(self) -> bool:
        return self.raw_reply is None

    @property
    def unlinked_count(self) -> int:
        return sum(1 for f in self.findings if f.status == UNLINKED)

    @property
    def graded_count(self) -> int:
        """Derecelendirme sıfatı içeren tespit sayısı.

        Raporlanır ama hiçbir şeyi düşürmez: talimatın ne sıklıkla tutmadığı
        bir ölçüdür, bir hata değil.
        """
        return sum(1 for f in self.findings if f.graded)

    @property
    def single_metric_count(self) -> int:
        """Tek metriğe ve tek özneye dayanan tespit sayısı.

        Sentez yerine tablo tekrarı yapıldığının göstergesi. İlk koşuda yedi
        gözlemin yedisi böyleydi.
        """
        return sum(1 for f in self.findings if len(f.metric_link) < 2 and len(f.subjects) < 2)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": EXPLAIN_SCHEMA_VERSION,
            "model": self.model,
            "prompt_hash": self.prompt_hash,
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
            "not_shown": self.not_shown,
            "finding_count": len(self.findings),
            "unlinked_count": self.unlinked_count,
            "graded_count": self.graded_count,
            "single_metric_count": self.single_metric_count,
        }
        if not self.is_structured:
            payload["status"] = UNSTRUCTURED
            payload["raw_reply"] = self.raw_reply
        return payload


def _validate_links(raw: Any, warnings: list[str]) -> list[str]:
    """Metrik adlarını süzer. Tanımsız adlar düşer ve uyarı üretir."""
    if not isinstance(raw, list):
        return []
    links = []
    for item in raw:
        name = str(item).upper()
        if name in VALID_METRICS:
            links.append(name)
        else:
            warnings.append(f"unknown metric name in metric_link: {item!r}")
    return links


def parse_explanation(reply: str) -> tuple[Explanation, list[str]]:
    """Model yanıtını `Explanation`a çevirir.

    Ayrıştırılamayan yanıt istisna fırlatmaz: ham metniyle birlikte
    `unstructured` olarak döner. Çağıran taraf onu yine de raporlayabilmelidir.
    """
    warnings: list[str] = []
    try:
        payload = json.loads(extract_json_object(reply))
    except (ValueError, AdviceParseError) as error:
        warnings.append(f"reply was not a JSON object: {error}")
        return Explanation(raw_reply=reply), warnings

    if not isinstance(payload, dict):
        warnings.append("reply was not a JSON object")
        return Explanation(raw_reply=reply), warnings

    findings = []
    raw_findings = payload.get("findings")
    if isinstance(raw_findings, list):
        for item in raw_findings:
            if not isinstance(item, dict):
                warnings.append("finding was not an object; dropped")
                continue
            statement = str(item.get("statement", "")).strip()
            if not statement:
                warnings.append("finding had no statement; dropped")
                continue
            raw_subjects = item.get("subjects")
            # Tekil `subject` de kabul edilir: eski şemayı hatırlayan bir model
            # yüzünden tüm tespiti kaybetmek, şemayı korumaktan daha pahalı.
            if raw_subjects is None and item.get("subject"):
                raw_subjects = [item["subject"]]
            subjects = [str(s).strip() for s in raw_subjects or [] if str(s).strip()]
            findings.append(
                Finding(
                    statement=statement,
                    subjects=subjects,
                    metric_link=_validate_links(item.get("metric_link"), warnings),
                )
            )
    else:
        warnings.append("reply had no findings list")

    explanation = Explanation(
        summary=str(payload.get("summary", "")).strip(),
        findings=findings,
        not_shown=str(payload.get("not_shown", "")).strip(),
    )
    if explanation.graded_count:
        warnings.append(
            f"{explanation.graded_count} finding(s) used grading language "
            "the instruction forbids; kept and tagged"
        )
    return explanation, warnings


def request_explanation(
    provider: Provider,
    report: dict,
    config: Config,
    *,
    cache: ResponseCache | None = None,
    budget: Budget | None = None,
    max_classes: int = 25,
) -> tuple[Explanation, list[str]]:
    """Tarama raporu için modelden yorum ister.

    `advise`'ın tek onarım denemesi burada **yoktur**: yorum ölçülmediği için
    ikinci bir çağrının bedeli karşılığında kazandığı bir şey yok. Yanıt
    ayrıştırılamazsa ham metniyle döner.
    """
    system = SYSTEM_INSTRUCTION
    user = build_user_prompt(report, max_classes=max_classes)

    provider_name = getattr(provider, "name", config.provider.name)
    key = prompt_hash(provider_name, config.provider.model, system + "\n" + user, "explain")

    # Sıra `advise` ile aynı: önce önbellek, sonra bütçe. Önbellekten dönen
    # yanıt para harcamadığı için bütçeden düşmez.
    if cache is not None:
        cached = cache.get(key)
        if cached is not None:
            if budget is not None:
                budget.record_cache_hit()
            explanation, warnings = parse_explanation(cached)
            explanation.prompt_hash = key
            explanation.model = config.provider.model
            explanation.from_cache = True
            return explanation, warnings

    if budget is not None:
        budget.check("explain")

    reply = provider.generate(system, user, config.provider, config.advise.temperature)

    if budget is not None:
        budget.record_call(len(user) // 4, len(reply) // 4)
    if cache is not None:
        cache.set(key, reply, meta={"target": "explain", "model": config.provider.model})

    explanation, warnings = parse_explanation(reply)
    explanation.prompt_hash = key
    explanation.model = config.provider.model
    return explanation, warnings
