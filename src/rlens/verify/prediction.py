"""Modelin öngörülerinin denetimi: `expected_effect` ↔ gerçekleşen delta.

**Projenin en özgün ölçümü burasıdır.** Diğer araçlar "AI ne önerdi" gösterir;
bu modül "AI'nın kendi önerisi hakkındaki tahmini tuttu mu" sorusunu sayıya
çevirir.

İki kural sonucun dürüstlüğünü belirler:

1. **Doğrulanamayan tahmin yanlış sayılmaz.** Model "CAM düşecek" der ve CAM
   zaten hesaplanamıyorsa, bu modelin hatası değil bizim ölçüm boşluğumuzdur.
   Bunlar ayrı sayılır ve isabet oranının **paydasına girmez**; aksi halde
   modeli kendi eksiğimiz yüzünden cezalandırmış olurduk.

2. **Hangi önerinin uygulandığı bilinmelidir.** Bir hedef için üç öneri gelip
   biri uygulanmışsa, diğer ikisinin tahminini "tutmadı" saymak anlamsızdır.
   `applied` süzgeci bu yüzden vardır; kullanılmazsa rapor tüm önerileri
   gösterir ama bu sınırlılık açıkça belirtilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rlens.verify.diff import (
    CLASS_METRIC_FIELDS,
    FUNCTION_METRIC_FIELDS,
    REMOVED,
    ProjectDelta,
)

#: Tahmin sonuçları.
HIT = "hit"
MISS = "miss"
UNVERIFIABLE = "unverifiable"

#: Hangi metrikler hangi öğe türü için ölçülür.
_MEASURABLE = {
    "class": set(CLASS_METRIC_FIELDS.values()),
    "function": set(FUNCTION_METRIC_FIELDS.values()),
}


@dataclass(frozen=True)
class PredictionCheck:
    """Tek bir `{metric, direction}` tahmininin denetimi."""

    target: str
    suggestion_index: int
    suggestion_title: str
    metric: str
    predicted: str
    actual: str | None = None
    outcome: str = UNVERIFIABLE
    reason: str | None = None
    """Doğrulanamadıysa nedeni. Boş bırakılmaz — okuyucu neden bilmeli."""

    confidence: float | None = None
    """Modelin bu tahmine verdiği güven. Kalibrasyon hesabı bunu kullanır."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "suggestion_index": self.suggestion_index,
            "suggestion_title": self.suggestion_title,
            "metric": self.metric,
            "predicted": self.predicted,
            "actual": self.actual,
            "outcome": self.outcome,
            "reason": self.reason,
            "confidence": self.confidence,
        }


@dataclass
class SuggestionScore:
    """Tek bir önerinin tahmin karnesi."""

    target: str
    index: int
    title: str
    checks: list[PredictionCheck] = field(default_factory=list)

    @property
    def hits(self) -> int:
        return sum(1 for check in self.checks if check.outcome == HIT)

    @property
    def misses(self) -> int:
        return sum(1 for check in self.checks if check.outcome == MISS)

    @property
    def unverifiable(self) -> int:
        return sum(1 for check in self.checks if check.outcome == UNVERIFIABLE)

    @property
    def verifiable(self) -> int:
        return self.hits + self.misses

    @property
    def accuracy(self) -> float | None:
        """Doğrulanabilir tahminler içinde isabet oranı.

        Hiç doğrulanabilir tahmin yoksa `None` — sıfır demek "hepsi yanlış"
        anlamına gelirdi, oysa doğrusu "ölçemedik".
        """
        if self.verifiable == 0:
            return None
        return round(self.hits / self.verifiable, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "suggestion_index": self.index,
            "title": self.title,
            "hits": self.hits,
            "misses": self.misses,
            "unverifiable": self.unverifiable,
            "accuracy": self.accuracy,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass
class PredictionReport:
    """Bir `advise` çalıştırmasının tüm tahminlerinin denetimi."""

    scores: list[SuggestionScore] = field(default_factory=list)
    filtered: bool = False
    """Yalnızca uygulandığı belirtilen öneriler mi denetlendi?"""

    comparable: bool = True
    incompatibility: str | None = None

    @property
    def hits(self) -> int:
        return sum(score.hits for score in self.scores)

    @property
    def misses(self) -> int:
        return sum(score.misses for score in self.scores)

    @property
    def unverifiable(self) -> int:
        return sum(score.unverifiable for score in self.scores)

    @property
    def verifiable(self) -> int:
        return self.hits + self.misses

    @property
    def accuracy(self) -> float | None:
        if self.verifiable == 0:
            return None
        return round(self.hits / self.verifiable, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparable": self.comparable,
            "incompatibility": self.incompatibility,
            "filtered_to_applied": self.filtered,
            "hits": self.hits,
            "misses": self.misses,
            "unverifiable": self.unverifiable,
            "accuracy": self.accuracy,
            "suggestions": [score.to_dict() for score in self.scores],
        }


def _check_one(
    target: str,
    index: int,
    title: str,
    metric: str,
    predicted: str,
    delta: ProjectDelta,
    confidence: float | None = None,
) -> PredictionCheck:
    """Tek bir tahmini denetler."""
    entity = delta.by_name(target)

    def unverifiable(reason: str) -> PredictionCheck:
        return PredictionCheck(
            target=target,
            suggestion_index=index,
            suggestion_title=title,
            metric=metric,
            predicted=predicted,
            confidence=confidence,
            outcome=UNVERIFIABLE,
            reason=reason,
        )

    if entity is None:
        return unverifiable("target not found in either report")
    if entity.status == REMOVED:
        # Sınıf tamamen kaldırıldıysa metrikleri yoktur. Bu bir başarısızlık
        # değil, farklı bir sonuçtur ve öyle raporlanır.
        return unverifiable("target no longer exists after the change")
    if metric not in _MEASURABLE.get(entity.kind, set()):
        return unverifiable(f"{metric} is not measured for a {entity.kind} target")

    measured = entity.metrics.get(metric)
    if measured is None:
        return unverifiable(f"{metric} is not part of this report")
    if not measured.comparable:
        return unverifiable(f"{metric} could not be computed in one of the reports")

    actual = measured.direction
    return PredictionCheck(
        target=target,
        suggestion_index=index,
        suggestion_title=title,
        metric=metric,
        predicted=predicted,
        confidence=confidence,
        actual=actual,
        outcome=HIT if actual == predicted else MISS,
    )


def check_predictions(
    advice_document: dict,
    delta: ProjectDelta,
    applied: dict[str, list[int]] | None = None,
) -> PredictionReport:
    """Bir öneri belgesindeki tüm tahminleri gerçekleşen deltayla karşılaştırır.

    Args:
        advice_document: `advise` çıktısının JSON'dan okunmuş hali.
        delta: `diff_reports` sonucu.
        applied: Hedef adı → uygulanan öneri sıraları (1'den başlayarak).
            Verilirse yalnızca bunlar denetlenir. Verilmezse tüm öneriler
            denetlenir; bu durumda uygulanmamış önerilerin "tutmadı" görünmesi
            beklenen bir yanlılıktır ve rapor bunu belirtir.

    Returns:
        Öneri başına ve toplam isabet karnesi.
    """
    report = PredictionReport(
        filtered=applied is not None,
        comparable=delta.comparable,
        incompatibility=delta.incompatibility,
    )

    for advice in advice_document.get("advices", []):
        target = advice.get("target", "")
        allowed = None if applied is None else set(applied.get(target, []))

        for index, suggestion in enumerate(advice.get("suggestions", []), start=1):
            if allowed is not None and index not in allowed:
                continue

            score = SuggestionScore(
                target=target,
                index=index,
                title=suggestion.get("title", "(untitled)"),
            )
            for effect in suggestion.get("expected_effect", []):
                metric = str(effect.get("metric", "")).upper()
                predicted = str(effect.get("direction", "")).lower()
                if not metric or not predicted:
                    continue
                confidence = effect.get("confidence")
                if confidence is not None:
                    try:
                        confidence = float(confidence)
                    except (TypeError, ValueError):
                        confidence = None
                score.checks.append(
                    _check_one(target, index, score.title, metric, predicted, delta, confidence)
                )
            report.scores.append(score)

    return report


def parse_applied(values: list[str]) -> dict[str, list[int]]:
    """`--applied "god:OrderManager=1,2"` biçimini sözlüğe çevirir.

    Raises:
        ValueError: Biçim tanınmazsa.
    """
    applied: dict[str, list[int]] = {}
    for value in values:
        target, separator, indices = value.partition("=")
        if not separator:
            raise ValueError(
                f"expected TARGET=INDEX[,INDEX...], got {value!r} "
                f'(for example: "god:OrderManager=1")'
            )
        numbers: list[int] = []
        for part in indices.split(","):
            part = part.strip()
            if not part.isdigit() or int(part) < 1:
                raise ValueError(f"suggestion index must be a positive number, got {part!r}")
            numbers.append(int(part))
        applied.setdefault(target.strip(), []).extend(numbers)
    return applied
