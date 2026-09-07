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

**Taşınan üye silinmiş sayılmaz.** Extract Class tam olarak "üyeleri başka bir
sınıfa taşımak"tır ve aracın önerdiği refactoring türlerinin başında gelir.
Yalnızca hedefin kendi arayüzüne bakan bir kontrol, her Extract Class'ı
şüpheli ilan eder ve araç kendi tavsiyesini cezalandırır. Bu yüzden kaybolan
her üye önce projenin geri kalanında aranır; bulunursa `moved`, bulunmazsa
`deleted` sayılır ve şüphe yalnızca silinenlerden doğar.

FINDINGS-1'in iki vakası bu ayrımın turnusolüdür: arayüz-silme vakasında
üyeler yok oldu, denetim-çıkarma vakasında taşındı.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rlens.analysis.interface import InterfaceDelta, PublicInterface, diff_interfaces
from rlens.verify.diff import ADDED, IMPROVED, MIXED, EntityDelta

SUSPICIOUS = "suspicious"


@dataclass(frozen=True)
class SuspicionCheck:
    """Tek bir sınıf için Goodhart değerlendirmesi."""

    qualified_name: str
    interface: InterfaceDelta
    metrics_improved: bool
    moved: tuple[tuple[str, str], ...] = ()
    """`(üye adı, yeni sahibi)` çiftleri. Taşınan üye kaybolmamıştır."""

    @property
    def deleted(self) -> tuple[str, ...]:
        """Projede hiçbir yerde bulunamayan üyeler."""
        relocated = {name for name, _ in self.moved}
        return tuple(name for name in self.interface.removed if name not in relocated)

    @property
    def net_deleted(self) -> int:
        """Silinen üye sayısı eksi eklenen. Yeniden adlandırma sıfır verir."""
        return len(self.deleted) - len(self.interface.added)

    @property
    def is_suspicious(self) -> bool:
        """Metrikler iyileşirken public arayüz **net olarak silindi** mi?

        Üç şey birden aranır ve her biri bir yanlış pozitifi eler:

        * Metrikler iyileşmiş olmalı — tek başına arayüz küçülmesi meşrudur.
        * Kaybolan üye başka bir sınıfa taşınmamış olmalı — Extract Class
          cezalandırılmamalı.
        * Kayıp net olmalı — `touch_b` gidip `touch_both` geldiyse hiçbir
          yetenek kaybolmamıştır.

        Beş metot silip bir tane eklemek hâlâ yakalanır (net −4).
        """
        return self.metrics_improved and self.net_deleted > 0

    @property
    def reason(self) -> str:
        if not self.is_suspicious:
            return ""
        deleted = self.deleted
        names = ", ".join(deleted[:5])
        if len(deleted) > 5:
            names += f" and {len(deleted) - 5} more"
        text = f"metrics improved while {len(deleted)} public member(s) were deleted: {names}"
        if self.moved:
            owners = sorted({owner for _, owner in self.moved})
            text += f"; {len(self.moved)} moved to {', '.join(owners)}"
        return text

    def to_dict(self) -> dict:
        return {
            "qualified_name": self.qualified_name,
            "suspicious": self.is_suspicious,
            "metrics_improved": self.metrics_improved,
            "deleted": list(self.deleted),
            "moved": [list(pair) for pair in self.moved],
            "net_deleted": self.net_deleted,
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


def find_new_owner(
    member: str,
    exclude: str,
    interfaces: dict[str, dict],
    preferred: set[str],
    module: str,
) -> str | None:
    """Kaybolan bir üyenin projede yeniden ortaya çıktığı sınıf.

    Arama sırası daralan olasılığa göredir: önce **yeni eklenen** sınıflar
    (Extract Class'ın tipik sonucu), sonra aynı modüldekiler, sonra proje.

    **Sınırlılık:** eşleşme yalnızca ada bakar. `public_interface` parametre
    bilgisi taşımadığı için arite karşılaştırılamaz; aynı adlı ilgisiz bir
    metot yanlışlıkla "taşınmış" sayılabilir. v3'te AST diff ile
    kesinleştirilecek. Yanlış tarafı bilinçli seçildi: meşru bir Extract
    Class'ı şüpheli ilan etmek, kaçırılan bir silmeden daha zararlıdır, çünkü
    davranış testleri silmeyi zaten yakalar.
    """

    def owns(name: str) -> bool:
        payload = interfaces.get(name, {})
        return member in set(payload.get("methods", ())) | set(payload.get("attributes", ()))

    for group in (
        sorted(preferred),
        sorted(n for n in interfaces if n.startswith(f"{module}:")),
        sorted(interfaces),
    ):
        for name in group:
            if name != exclude and owns(name):
                return name
    return None


def check_entity(
    delta: EntityDelta,
    before: dict | None,
    after: dict | None,
    after_interfaces: dict[str, dict] | None = None,
    added_classes: set[str] | None = None,
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
    improved = delta.summarise() in (IMPROVED, MIXED)

    moved: list[tuple[str, str]] = []
    if after_interfaces:
        module = delta.qualified_name.split(":")[0]
        for member in interface.removed:
            owner = find_new_owner(
                member,
                delta.qualified_name,
                after_interfaces,
                added_classes or set(),
                module,
            )
            if owner:
                moved.append((member, owner))

    return SuspicionCheck(
        qualified_name=delta.qualified_name,
        interface=interface,
        metrics_improved=improved,
        moved=tuple(moved),
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
    # Extract Class'ın sonucu genelde yeni bir sınıftır; taşınan üye önce orada
    # aranır.
    added = {d.qualified_name for d in deltas if d.kind == "class" and d.status == ADDED}

    report = GoodhartReport()
    for delta in deltas:
        if delta.kind != "class":
            continue
        check = check_entity(
            delta,
            old_index.get(delta.qualified_name),
            new_index.get(delta.qualified_name),
            new_index,
            added,
        )
        if check is None:
            report.unavailable.append(delta.qualified_name)
        else:
            report.checks.append(check)
    return report
