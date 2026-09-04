"""Rapor veri sınıfları ve rapor şema sürümü.

`SCHEMA_VERSION` neden burada ve neden kritik (bkz. doküman Bölüm 3):
`verify`, iki JSON raporu karşılaştırarak metrik deltası üretir. Metrik
hesaplama kuralları Aşama 1–5 boyunca değişecektir. Şema sürümü olmasaydı,
farklı kurallarla üretilmiş iki rapor karşılaştırıldığında araç **sessizce
yanlış delta** üretirdi. Bu yüzden her rapor kendi şema sürümünü taşır ve
`verify` uyumsuzlukta uyarıp deltayı "karşılaştırılamaz" işaretler.

Sürüm artırma kuralı: bir metriğin *hesaplama kuralı* değiştiğinde veya rapor
alan yapısı bozucu şekilde değiştiğinde `SCHEMA_VERSION` artırılır.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

#: Tarama raporu formatı sürümü. Paket sürümünden bağımsızdır.
SCHEMA_VERSION = 1

#: Mimari raporu formatı sürümü. Tarama ve öneri şemalarından **ayrıdır**:
#: ihlal tespiti değişmeden metrik kuralları değişebilir, ya da tersi. Tek sayaç
#: kullanılsaydı birinin değişmesi diğerinin geçmiş raporlarını gereksiz yere
#: geçersiz kılardı.
ARCH_SCHEMA_VERSION = 1

#: Öneri raporu formatı sürümü. Taramadan **ayrıdır**: metrik kuralları
#: değişmeden öneri formatı değişebilir, ya da tersi. Tek bir sayı kullanılsaydı
#: birinin değişmesi diğerinin geçmiş raporlarını gereksiz yere geçersiz kılardı.
ADVICE_SCHEMA_VERSION = 1


@dataclass
class FunctionReport:
    """Bir fonksiyon/metot için ölçülen değerler (Aşama 1'de doldurulur)."""

    name: str
    lineno: int
    cyclomatic_complexity: int | None = None
    loc: int | None = None
    param_count: int | None = None
    max_nesting: int | None = None


@dataclass
class ClassReport:
    """Bir sınıf için ölçülen metrikler (Aşama 1'de doldurulur).

    `None` değerler "hesaplanamadı" demektir, "sıfır" değil. CAM'in atlanma
    nedeni ayrı bir alanda taşınır ki rapor okuyucusu neden `null` olduğunu
    bilsin.
    """

    name: str
    module: str
    lineno: int
    nom: int | None = None
    wmc: int | None = None
    lcom4: int | None = None
    dam: float | None = None
    dam_strict: float | None = None
    dcc: int | None = None
    cam: float | None = None
    cam_skipped_reason: str | None = None
    methods: list[FunctionReport] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        """`verify` deltalarında sınıfları eşleştirmek için kullanılan kimlik."""
        return f"{self.module}:{self.name}"


@dataclass
class ModuleReport:
    path: str
    module: str
    classes: list[ClassReport] = field(default_factory=list)
    functions: list[FunctionReport] = field(default_factory=list)


@dataclass
class ProjectReport:
    """Bir `scan` çalışmasının tam çıktısı."""

    root: str
    generated_at: str
    rlens_version: str
    schema_version: int = SCHEMA_VERSION
    modules: list[ModuleReport] = field(default_factory=list)
    skipped_files: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """JSON'a yazılabilir sözlük. `schema_version` kökte ve ilk sıradadır."""
        return asdict(self)

    def iter_classes(self):
        for module in self.modules:
            yield from module.classes
