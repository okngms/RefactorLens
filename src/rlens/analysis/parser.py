"""Dosya keşfi ve `ast` ile ayrıştırma.

Sorumluluğu iki şey:

1. **Hangi dosyalar taranacak?** `rlens.yaml` içindeki `scan.include` ve
   `scan.exclude` kurallarına göre karar verir.
2. **Ayrıştırma.** Standart kütüphanenin `ast` modülünü kullanır; üçüncü parti
   ayrıştırıcıya bağımlılık yoktur.

**Bozuk dosya taramayı çökertmez.** Sözdizimi hatası olan, okunamayan veya
farklı bir Python sürümüne ait bir dosya atlanır ve nedeniyle birlikte raporun
`skipped_files` alanına yazılır. Gerçek kod tabanlarında böyle dosyalar her
zaman vardır (yarım kalmış taslaklar, şablon dosyaları, eski sürüm kodu) ve
araç bunlar yüzünden kullanılamaz hale gelmemelidir.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

#: Hiçbir config kuralı yazılmasa bile atlanan dizinler.
#: Bunlar kullanıcının kodu değildir; taranmaları hem yavaşlatır hem metrikleri
#: anlamsız verilerle kirletir.
ALWAYS_EXCLUDED_DIRS = frozenset(
    {
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "node_modules",
        "site-packages",
        ".eggs",
    }
)


@dataclass(frozen=True)
class ParsedModule:
    """Başarıyla ayrıştırılmış tek bir Python dosyası."""

    path: Path
    """Diskteki tam yol."""

    relative_path: str
    """Tarama köküne göre yol — raporlarda bu gösterilir (taşınabilir olsun diye)."""

    module: str
    """Noktalı modül adı, örn. `analysis.parser`."""

    tree: ast.Module
    """Ayrıştırılmış sözdizimi ağacı."""

    source: str
    """Ham kaynak metin. `advise` fazında koda geri dönmek için saklanır."""


@dataclass(frozen=True)
class SkippedFile:
    """Ayrıştırılamayan dosya ve nedeni."""

    relative_path: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.relative_path, "reason": self.reason}


def _is_hidden(part: str) -> bool:
    """`.venv`, `.idea` gibi gizli dizinler taranmaz. `.` ve `..` istisnadır."""
    return part.startswith(".") and part not in (".", "..")


def _normalize(pattern: str) -> str:
    """Config'teki yol desenini karşılaştırılabilir hale getirir.

    `"src/"`, `"src"` ve `"./src"` aynı şeyi ifade eder; kullanıcı hangisini
    yazarsa yazsın çalışmalıdır.
    """
    cleaned = pattern.strip().replace("\\", "/").strip("/")
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def _matches(relative_path: str, pattern: str) -> bool:
    """Bir yol, verilen desenin kapsamına giriyor mu?

    Desen üç şekilde eşleşir:

    * `"."` veya boş → her şey (tüm projeyi tara)
    * Yol öneki → `"src"` deseni `"src/rlens/cli.py"` ile eşleşir
    * Dizin adı → `"tests"` deseni `"examples/messy_project/tests/a.py"` ile de
      eşleşir. Bu esneklik bilinçlidir: kullanıcı `exclude: ["tests/"]` yazdığında
      genellikle "adı tests olan her dizin" demek ister, "yalnızca kökteki tests"
      değil.
    """
    pattern = _normalize(pattern)
    if pattern in ("", "."):
        return True
    if relative_path == pattern or relative_path.startswith(pattern + "/"):
        return True
    return pattern in relative_path.split("/")[:-1]


def discover_files(
    root: Path,
    include: tuple[str, ...] = (".",),
    exclude: tuple[str, ...] = (),
) -> list[Path]:
    """Taranacak `.py` dosyalarını bulur; sonuç sıralıdır.

    Sıralı olması önemlidir: aynı proje iki kez tarandığında rapor sırası
    değişmemelidir, yoksa `verify` gereksiz fark üretir.
    """
    root = root.resolve()
    if root.is_file():
        return [root] if root.suffix == ".py" else []

    found: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        parts = relative.split("/")[:-1]

        if any(part in ALWAYS_EXCLUDED_DIRS or _is_hidden(part) for part in parts):
            continue
        if not any(_matches(relative, pattern) for pattern in include or (".",)):
            continue
        if any(_matches(relative, pattern) for pattern in exclude):
            continue
        found.append(path)
    return found


def module_name(root: Path, path: Path) -> str:
    """Dosya yolundan noktalı modül adı üretir.

    `src/rlens/analysis/parser.py` → `rlens.analysis.parser`
    `src/rlens/__init__.py`        → `rlens`

    `src` gibi ara dizinler kırpılmaz; kırpmak farklı köklerde çakışan adlar
    üretebilir. Rapor okunurluğu için yeterince açıktır.
    """
    relative = path.resolve().relative_to(root.resolve())
    parts = list(relative.parts)
    parts[-1] = parts[-1].removesuffix(".py")
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) if parts else relative.stem


def parse_file(path: Path, root: Path) -> ParsedModule | SkippedFile:
    """Tek bir dosyayı ayrıştırır. Başarısızlık istisna değil, dönüş değeridir.

    Ayrıştırma hatası beklenen bir durumdur (bkz. modül docstring'i), bu yüzden
    istisna fırlatmak yerine `SkippedFile` döndürülür ve çağıran taramaya devam
    eder.
    """
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return SkippedFile(relative, "not readable as utf-8")
    except OSError as exc:
        return SkippedFile(relative, f"unreadable: {exc.strerror or exc}")

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        line = exc.lineno or "?"
        return SkippedFile(relative, f"syntax error (line {line}): {exc.msg}")
    except (ValueError, RecursionError) as exc:
        # Çok derin iç içelik veya null bayt gibi uç durumlar.
        return SkippedFile(relative, f"could not parse: {type(exc).__name__}")

    return ParsedModule(
        path=path,
        relative_path=relative,
        module=module_name(root, path),
        tree=tree,
        source=source,
    )


def parse_project(
    root: Path,
    include: tuple[str, ...] = (".",),
    exclude: tuple[str, ...] = (),
) -> tuple[list[ParsedModule], list[SkippedFile]]:
    """Bir projenin tamamını ayrıştırır.

    Returns:
        (ayrıştırılan modüller, atlanan dosyalar)
    """
    modules: list[ParsedModule] = []
    skipped: list[SkippedFile] = []

    for path in discover_files(root, include, exclude):
        result = parse_file(path, root)
        if isinstance(result, ParsedModule):
            modules.append(result)
        else:
            skipped.append(result)

    return modules, skipped
