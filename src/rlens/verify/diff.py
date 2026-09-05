"""İki tarama raporu arasında metrik farkı.

Üç şey burada karara bağlanır:

1. **Karşılaştırma geçerli mi?** Metrik hesaplama kuralları sürümler arasında
   değişir. Farklı `schema_version` taşıyan iki rapor karşılaştırılırsa araç
   sessizce yanlış delta üretir — sayılar tutarlı görünür ama anlamları farklıdır.
   Bu yüzden uyumsuzluk sessizce geçiştirilmez.

2. **Hangi yön iyileşmedir?** Her metrik için aynı değildir: LCOM4 düşerse iyi,
   DAM yükselirse iyi. Bu tabloya bağlanmadan "iyileşti" denemez.

3. **Refactoring sınıf ekler ve siler.** "Sınıfı böl" önerisi uygulandığında
   yeni sınıflar doğar, bazen hedef sınıf tamamen kaybolur. Yalnızca eşleşen
   sınıflara bakmak, işin yarısını görmezden gelmek olurdu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Metrik → yükselmesi iyileşme mi?
#: DAM ve CAM dışında hepsinde düşük değer daha iyidir.
HIGHER_IS_BETTER = {
    "NOM": False,
    "WMC": False,
    "LCOM4": False,
    "DCC": False,
    "DAM": True,
    "CAM": True,
    "CC": False,
    "LOC": False,
    "PARAMS": False,
    "NESTING": False,
}

#: Sınıf raporundaki alan adı → metrik adı.
CLASS_METRIC_FIELDS = {
    "nom": "NOM",
    "wmc": "WMC",
    "lcom4": "LCOM4",
    "dam": "DAM",
    "dcc": "DCC",
    "cam": "CAM",
}

#: Fonksiyon raporundaki alan adı → metrik adı.
FUNCTION_METRIC_FIELDS = {
    "cyclomatic_complexity": "CC",
    "loc": "LOC",
    "param_count": "PARAMS",
    "max_nesting": "NESTING",
}

#: Sonuç etiketleri.
IMPROVED = "improved"
REGRESSED = "regressed"
MIXED = "mixed"
UNCHANGED = "unchanged"
ADDED = "added"
REMOVED = "removed"


@dataclass(frozen=True)
class MetricDelta:
    """Tek bir metriğin öncesi, sonrası ve yorumu."""

    metric: str
    before: float | int | None
    after: float | int | None

    @property
    def comparable(self) -> bool:
        """Hesaplanamayan bir değer varsa fark alınamaz.

        `None` "hesaplanamadı" demektir; sıfır kabul edip çıkarmak, CAM'i olmayan
        bir sınıfı "CAM'i 0.8 düştü" diye raporlamak olurdu.
        """
        return self.before is not None and self.after is not None

    @property
    def change(self) -> float | None:
        if not self.comparable:
            return None
        return round(self.after - self.before, 4)

    @property
    def direction(self) -> str | None:
        """`up` / `down` / `same` — modelin tahmin diliyle aynı sözlük."""
        change = self.change
        if change is None:
            return None
        if change > 0:
            return "up"
        if change < 0:
            return "down"
        return "same"

    @property
    def improved(self) -> bool | None:
        """Bu değişim iyileşme mi? Yön tek başına yetmez, metriğe bağlıdır."""
        direction = self.direction
        if direction is None or direction == "same":
            return None
        higher_is_better = HIGHER_IS_BETTER.get(self.metric)
        if higher_is_better is None:
            return None
        return (direction == "up") == higher_is_better

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "before": self.before,
            "after": self.after,
            "change": self.change,
            "direction": self.direction,
            "improved": self.improved,
            "comparable": self.comparable,
        }


@dataclass
class EntityDelta:
    """Bir sınıf veya modül düzeyi fonksiyonun tüm metrik farkları."""

    kind: str
    """`"class"` veya `"function"`."""

    module: str
    name: str
    status: str
    metrics: dict[str, MetricDelta] = field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        return f"{self.module}:{self.name}"

    @property
    def changed_metrics(self) -> dict[str, MetricDelta]:
        return {
            metric: delta
            for metric, delta in self.metrics.items()
            if delta.direction not in (None, "same")
        }

    def summarise(self) -> str:
        """`improved` / `regressed` / `mixed` / `unchanged`.

        `mixed` gizlenmez: "bir metriği düzeltirken diğerini bozdu" bulgusu,
        temiz bir iyileşme kadar önemlidir.
        """
        if self.status in (ADDED, REMOVED):
            return self.status
        verdicts = {delta.improved for delta in self.metrics.values() if delta.improved is not None}
        if not verdicts:
            return UNCHANGED
        if verdicts == {True}:
            return IMPROVED
        if verdicts == {False}:
            return REGRESSED
        return MIXED

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "module": self.module,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "status": self.status,
            "verdict": self.summarise(),
            "metrics": {name: delta.to_dict() for name, delta in self.metrics.items()},
        }


@dataclass(frozen=True)
class SetDelta:
    """İki küme arasındaki fark. İhlaller ve kokular için ortak biçim."""

    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    kept: tuple[str, ...] = ()

    @property
    def improved(self) -> bool:
        """Kaybolan var, yeni gelen yok."""
        return bool(self.removed) and not self.added

    @property
    def worsened(self) -> bool:
        return bool(self.added)

    def to_dict(self) -> dict[str, Any]:
        return {
            "added": list(self.added),
            "removed": list(self.removed),
            "kept": len(self.kept),
        }


@dataclass
class ProjectDelta:
    """İki rapor arasındaki tam fark."""

    before_generated_at: str
    after_generated_at: str
    comparable: bool = True
    incompatibility: str | None = None
    """Karşılaştırma geçersizse nedeni. `None` ise karşılaştırma geçerlidir."""

    entities: list[EntityDelta] = field(default_factory=list)
    violations: SetDelta = field(default_factory=SetDelta)
    """Mimari ihlal farkı. v1 raporlarında ihlal alanı yoktur ve boş kalır."""

    smells: SetDelta = field(default_factory=SetDelta)

    def by_name(self, qualified_name: str) -> EntityDelta | None:
        for entity in self.entities:
            if entity.qualified_name == qualified_name:
                return entity
        return None

    def with_status(self, status: str) -> list[EntityDelta]:
        return [entity for entity in self.entities if entity.status == status]

    @property
    def changed(self) -> list[EntityDelta]:
        """Yalnızca gerçekten değişen öğeler — rapor bunları gösterir."""
        return [
            entity
            for entity in self.entities
            if entity.status != UNCHANGED or entity.changed_metrics
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "before_generated_at": self.before_generated_at,
            "after_generated_at": self.after_generated_at,
            "comparable": self.comparable,
            "incompatibility": self.incompatibility,
            "entities": [entity.to_dict() for entity in self.entities],
            "violations": self.violations.to_dict(),
            "smells": self.smells.to_dict(),
        }


def _violation_keys(report: dict) -> set[str]:
    """İhlallerin kimlikleri: `KOD source → target`.

    `LV-CYCLE` için üyeler sıralı olduğu için kimlik kararlıdır; aynı döngü
    iki taramada aynı anahtarı üretir.
    """
    keys = set()
    for violation in report.get("violations", []):
        members = violation.get("members") or []
        if members:
            keys.add(f"{violation['code']} {' ↔ '.join(members)}")
        else:
            keys.add(
                f"{violation['code']} {violation.get('source', '')} → {violation.get('target', '')}"
            )
    return keys


def _smell_keys(report: dict) -> set[str]:
    """Koku kimlikleri: `etiket @ hedef`."""
    keys = set()
    for module in report.get("modules", []):
        for smell in module.get("smells", []):
            keys.add(f"{smell['label']} @ {smell['target']}")
        for cls in module.get("classes", []):
            for smell in cls.get("smells", []):
                keys.add(f"{smell['label']} @ {smell['target']}")
    return keys


def _set_delta(before: set[str], after: set[str]) -> SetDelta:
    return SetDelta(
        added=tuple(sorted(after - before)),
        removed=tuple(sorted(before - after)),
        kept=tuple(sorted(before & after)),
    )


def _index_entities(report: dict) -> dict[tuple[str, str, str], dict]:
    """Raporu `(tür, modül, ad)` anahtarlı sözlüğe çevirir."""
    index: dict[tuple[str, str, str], dict] = {}
    for module in report.get("modules", []):
        module_name = module.get("module", "")
        for cls in module.get("classes", []):
            index[("class", module_name, cls.get("name", ""))] = cls
        for function in module.get("functions", []):
            index[("function", module_name, function.get("name", ""))] = function
    return index


def _metric_deltas(kind: str, before: dict | None, after: dict | None) -> dict[str, MetricDelta]:
    fields = CLASS_METRIC_FIELDS if kind == "class" else FUNCTION_METRIC_FIELDS
    return {
        metric: MetricDelta(
            metric=metric,
            before=None if before is None else before.get(field_name),
            after=None if after is None else after.get(field_name),
        )
        for field_name, metric in fields.items()
    }


def check_compatibility(before: dict, after: dict) -> str | None:
    """Karşılaştırma geçerli mi? Değilse nedeni, geçerliyse `None`.

    Şema sürümü farklıysa metrik kuralları da farklı olabilir. Deltalar sayı
    olarak hesaplanabilir ama anlamları karşılaştırılabilir değildir; bunu
    sessizce yapmak aracı yanıltıcı hale getirir.
    """
    before_schema = before.get("schema_version")
    after_schema = after.get("schema_version")
    if before_schema != after_schema:
        return (
            f"report schema versions differ (before: {before_schema}, "
            f"after: {after_schema}); metric rules may have changed, so the "
            f"deltas are not comparable"
        )
    return None


def diff_reports(before: dict, after: dict) -> ProjectDelta:
    """İki tarama raporu arasındaki farkı hesaplar.

    Args:
        before: Değişiklikten önceki rapor (JSON'dan okunmuş sözlük).
        after: Değişiklikten sonraki rapor.

    Returns:
        Uyumsuzluk varsa `comparable=False` işaretli, aksi halde tam delta.
        Uyumsuzlukta bile öğe listesi doldurulur — kullanıcı ne olduğunu
        görebilmeli, ama sonuca güvenmemesi gerektiğini de bilmelidir.
    """
    incompatibility = check_compatibility(before, after)

    before_index = _index_entities(before)
    after_index = _index_entities(after)

    entities: list[EntityDelta] = []
    for key in sorted(set(before_index) | set(after_index)):
        kind, module, name = key
        old = before_index.get(key)
        new = after_index.get(key)

        if old is None:
            status = ADDED
        elif new is None:
            status = REMOVED
        else:
            status = UNCHANGED

        entities.append(
            EntityDelta(
                kind=kind,
                module=module,
                name=name,
                status=status,
                metrics=_metric_deltas(kind, old, new),
            )
        )

    return ProjectDelta(
        before_generated_at=before.get("generated_at", ""),
        after_generated_at=after.get("generated_at", ""),
        comparable=incompatibility is None,
        incompatibility=incompatibility,
        entities=entities,
        violations=_set_delta(_violation_keys(before), _violation_keys(after)),
        smells=_set_delta(_smell_keys(before), _smell_keys(after)),
    )
