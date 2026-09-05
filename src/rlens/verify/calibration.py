"""Öz-güven kalibrasyonu: Brier skoru ve ECE.

FINDINGS-1 modellerin **ne kadar** yanıldığını ölçtü. Bu modül farklı bir soru
sorar: yanılırken bunu biliyorlar mıydı?

Model artık her tahmine opsiyonel bir `confidence` iliştirebiliyor. Kalibre bir
model "%80 eminim" dediklerinin yaklaşık %80'inde haklı çıkar. Kalibre olmayan
bir model her şeye 0.9 der ve yarısında yanılır — ki bu, güveni işe yaramaz
kılar.

**Neden değerli:** metrik temelli bir araçta kalibre güven, kullanıcının hangi
öneriyi elle doğrulayacağını seçmesini sağlar. Kalibre değilse güven alanı
gürültüdür ve kaldırılmalıdır. Hangisi olduğu ölçülmeden bilinemez.

**Yalnızca verilmiş güvenler sayılır.** Eksik güveni 0.5 varsaymak, söylenmemiş
bir şeyi modele atfetmek olurdu; sayı düşük çıkar ve suç modele yazılır.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: ECE için varsayılan kova sayısı. Küçük örneklemde çok kova gürültü üretir.
DEFAULT_BINS = 5


@dataclass(frozen=True)
class CalibrationPoint:
    """Tek bir tahmin: model ne kadar emindi, haklı çıktı mı?"""

    confidence: float
    correct: bool
    metric: str = ""
    target: str = ""

    @property
    def error(self) -> float:
        """Kare hata. Brier skoru bunların ortalamasıdır."""
        return (self.confidence - (1.0 if self.correct else 0.0)) ** 2


@dataclass
class Bin:
    """Bir güven aralığı ve içindeki tahminler."""

    low: float
    high: float
    points: list[CalibrationPoint] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.points)

    @property
    def mean_confidence(self) -> float | None:
        if not self.points:
            return None
        return round(sum(p.confidence for p in self.points) / self.count, 4)

    @property
    def accuracy(self) -> float | None:
        if not self.points:
            return None
        return round(sum(1 for p in self.points if p.correct) / self.count, 4)

    @property
    def gap(self) -> float | None:
        """Güven ile gerçek isabet arasındaki fark. Pozitif = fazla özgüven."""
        if not self.points:
            return None
        return round(self.mean_confidence - self.accuracy, 4)

    def to_dict(self) -> dict:
        return {
            "range": [self.low, self.high],
            "count": self.count,
            "mean_confidence": self.mean_confidence,
            "accuracy": self.accuracy,
            "gap": self.gap,
        }


@dataclass
class CalibrationReport:
    """Bir çalıştırmanın kalibrasyon karnesi."""

    points: list[CalibrationPoint] = field(default_factory=list)
    without_confidence: int = 0
    """Güven vermemiş tahmin sayısı. Cezalandırılmaz, sayılır."""

    bins: list[Bin] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.points)

    @property
    def brier(self) -> float | None:
        """Ortalama kare hata. 0 mükemmel, 0.25 rastgele, 1 tam ters.

        Hiç güven verilmemişse `None` — sıfır "mükemmel kalibre" demek olurdu.
        """
        if not self.points:
            return None
        return round(sum(p.error for p in self.points) / self.count, 4)

    @property
    def ece(self) -> float | None:
        """Beklenen kalibrasyon hatası: kova başına |güven − isabet| ağırlıklı ortalaması."""
        if not self.points:
            return None
        total = sum(b.count * abs(b.gap) for b in self.bins if b.count and b.gap is not None)
        return round(total / self.count, 4)

    @property
    def mean_confidence(self) -> float | None:
        if not self.points:
            return None
        return round(sum(p.confidence for p in self.points) / self.count, 4)

    @property
    def accuracy(self) -> float | None:
        if not self.points:
            return None
        return round(sum(1 for p in self.points if p.correct) / self.count, 4)

    @property
    def overconfidence(self) -> float | None:
        """Ortalama güven eksi gerçek isabet. Pozitif = fazla özgüven."""
        if not self.points:
            return None
        return round(self.mean_confidence - self.accuracy, 4)

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "without_confidence": self.without_confidence,
            "brier": self.brier,
            "ece": self.ece,
            "mean_confidence": self.mean_confidence,
            "accuracy": self.accuracy,
            "overconfidence": self.overconfidence,
            "bins": [b.to_dict() for b in self.bins if b.count],
        }


def make_bins(points: list[CalibrationPoint], count: int = DEFAULT_BINS) -> list[Bin]:
    """Tahminleri güven aralıklarına dağıtır.

    Sınır değerler **üst** kovaya yazılır (`low < c <= high`), 0.0 istisnasıyla:
    aksi halde 0.2 hem birinci hem ikinci kovaya girebilirdi.
    """
    width = 1.0 / count
    bins = [
        Bin(low=round(index * width, 4), high=round((index + 1) * width, 4))
        for index in range(count)
    ]
    for point in points:
        index = min(count - 1, max(0, int((point.confidence - 1e-9) // width)))
        if point.confidence == 0.0:
            index = 0
        bins[index].points.append(point)
    return bins


def calibrate(
    points: list[CalibrationPoint], without_confidence: int = 0, bins: int = DEFAULT_BINS
) -> CalibrationReport:
    """Kalibrasyon raporu üretir."""
    return CalibrationReport(
        points=list(points),
        without_confidence=without_confidence,
        bins=make_bins(points, bins),
    )


def collect_points(prediction_report) -> CalibrationReport:
    """Tahmin denetimi sonucundan kalibrasyon noktalarını çıkarır.

    Yalnızca **doğrulanabilir** tahminler sayılır. Ölçemediğimiz bir tahminin
    güveni hakkında konuşamayız; `unverifiable` olanlar hem isabet oranından
    hem kalibrasyondan dışarıdadır — aynı dürüstlük kuralı.
    """
    from rlens.verify.prediction import HIT, MISS

    points: list[CalibrationPoint] = []
    missing = 0

    for score in prediction_report.scores:
        for check in score.checks:
            if check.outcome not in (HIT, MISS):
                continue
            confidence = getattr(check, "confidence", None)
            if confidence is None:
                missing += 1
                continue
            points.append(
                CalibrationPoint(
                    confidence=confidence,
                    correct=check.outcome == HIT,
                    metric=check.metric,
                    target=check.target,
                )
            )
    return calibrate(points, without_confidence=missing)
