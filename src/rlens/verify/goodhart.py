"""Goodhart koruması: metrik iyileşmesi gerçek mi, yoksa ölçüm oyunu mu?

FINDINGS-1'de bir model dört metriğin dördünü birden doğru tahmin etti:
`LCOM4 down, DCC down, NOM down, WMC down`. Hepsi tuttu. Sınıfın **bütün public
arayüzü silinmişti** ve 42 davranış testi kırıldı.

Yalnızca metriklere bakan bir araç bunu deneyin en başarılı vakası olarak
raporlardı: %100 tahmin isabeti, `improved` kararı. O vakayı yakalayan tek şey
davranış testleriydi.

Davranış testleri hâlâ zorunludur ve yerini hiçbir şey tutmaz. Ama araç, testler
çalıştırılmadan önce de şüphe **işaretleyebilir**: bir sınıfın metrikleri
iyileşirken public arayüzü küçülmüşse, iyileşmenin bir kısmı iş çıkarmaktan
değil **iş silmekten** gelmiş olabilir.

**`suspicious` bir suçlama değil, bir sorudur.** Meşru bir refactoring de arayüz
küçültebilir; ölü kod silmek tam olarak budur. Bu yüzden karar `regressed`
değil ayrı bir etikettir ve `verify.treat_suspicious_as_regression` ile CI
davranışı seçilebilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rlens.analysis.interface import InterfaceDelta, PublicInterface, diff_interfaces
from rlens.verify.diff import IMPROVED, MIXED, EntityDelta

SUSPICIOUS = "suspicious"


@dataclass(frozen=True)
class SuspicionCheck:
    """Tek bir sınıf için Goodhart değerlendirmesi."""

    qualified_name: str
    interface: InterfaceDelta
    metrics_improved: bool
    removed_public: tuple[str, ...] = ()

    @property
    def is_suspicious(self) -> bool:
        """Metrikler iyileşirken public arayüz küçüldü mü?

        İki koşul birden aranır. Tek başına arayüz küçülmesi meşru olabilir
        (ölü kod silme); tek başına metrik iyileşmesi zaten istenen şeydir.
        Birlikte olmaları soru işaretidir.
        """
        return self.metrics_improved and bool(self.removed_public)

    @property
    def reason(self) -> str:
        if not self.is_suspicious:
            return ""
        names = ", ".join(self.removed_public[:5])
        if len(self.removed_public) > 5:
            names += f" and {len(self.removed_public) - 5} more"
        return (
            f"metrics improved while {len(self.removed_public)} public member(s) "
            f"disappeared: {names}"
        )

    def to_dict(self) -> dict:
        return {
            "qualified_name": self.qualified_name,
            "suspicious": self.is_suspicious,
            "metrics_improved": self.metrics_improved,
            "interface": self.interface.to_dict(),
            "reason": self.reason,
        }


@dataclass
class GoodhartReport:
    """Bir doğrulamanın tüm şüphe değerlendirmeleri."""

    checks: list[SuspicionCheck] = field(default_factory=list)
    unavailable: list[str] = field(default_factory=list)
    """Arayüz bilgisi olmayan sınıflar. v1 raporlarında bu alan yoktur."""

    @property
    def suspicious(self) -> list[SuspicionCheck]:
        return [check for check in self.checks if check.is_suspicious]

    @property
    def any_suspicious(self) -> bool:
        return bool(self.suspicious)

    def to_dict(self) -> dict:
        return {
            "suspicious_count": len(self.suspicious),
            "checks": [check.to_dict() for check in self.checks if check.is_suspicious],
            "interface_data_unavailable": list(self.unavailable),
        }


def _interface_from(payload: dict | None) -> PublicInterface | None:
    """Rapordaki `public_interface` sözlüğünü nesneye çevirir."""
    if not payload:
        return None
    return PublicInterface(
        methods=tuple(payload.get("methods", ())),
        attributes=tuple(payload.get("attributes", ())),
        accessors=tuple(payload.get("accessors", ())),
    )


def check_entity(
    delta: EntityDelta,
    before: dict | None,
    after: dict | None,
) -> SuspicionCheck | None:
    """Tek bir sınıfı değerlendirir.

    Arayüz bilgisi eksikse `None` döner: v1 raporlarında bu alan yoktu ve
    yokluğundan "arayüz küçülmedi" sonucu çıkarmak yanlış olurdu.
    """
    old = _interface_from(before)
    new = _interface_from(after)
    if old is None or new is None:
        return None

    interface = diff_interfaces(old, new)
    verdict = delta.summarise()
    improved = verdict in (IMPROVED, MIXED)

    return SuspicionCheck(
        qualified_name=delta.qualified_name,
        interface=interface,
        metrics_improved=improved,
        removed_public=interface.removed,
    )


def _index_interfaces(report: dict) -> dict[str, dict]:
    """Rapordaki sınıfların `public_interface` alanları, nitelikli ada göre."""
    index: dict[str, dict] = {}
    for module in report.get("modules", []):
        for cls in module.get("classes", []):
            name = f"{module.get('module', '')}:{cls.get('name', '')}"
            if cls.get("public_interface"):
                index[name] = cls["public_interface"]
    return index


def detect(before: dict, after: dict, deltas: list[EntityDelta]) -> GoodhartReport:
    """İki tarama raporu ve hesaplanmış deltalardan şüphe raporu üretir.

    `MIXED` de iyileşme sayılır: bir metriği düzeltirken diğerini bozan bir
    değişiklik, arayüzü de siliyorsa aynı sorunun kapsamındadır.
    """
    old_index = _index_interfaces(before)
    new_index = _index_interfaces(after)

    report = GoodhartReport()
    for delta in deltas:
        if delta.kind != "class":
            continue
        check = check_entity(
            delta, old_index.get(delta.qualified_name), new_index.get(delta.qualified_name)
        )
        if check is None:
            report.unavailable.append(delta.qualified_name)
        else:
            report.checks.append(check)
    return report
