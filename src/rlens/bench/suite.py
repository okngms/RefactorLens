"""Suite tanımı, proje ve istem özetleri.

Bir sonuç dosyası üç özet taşır; rapor, özetleri farklı sonuçları aynı
tabloda birleştirmez (scan `schema_version` invariant'ının benchmark hali):

* `suite_hash` — suite dosyasının içeriği (hedefler, koşullar, tekrarlar),
* `project_hashes` — her projenin kaynak dosyaları,
* `prompt_hash` — modele giden sabit talimatlar (advise, apply, chartests,
  geri besleme başlığı).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

#: Dondurmaya ve özetlere girmeyen yollar: araç çıktısı ve yorumlayıcı artığı.
IGNORED_PARTS = frozenset({"__pycache__", "reports", ".rlens-cache", ".pytest_cache"})


class BenchError(Exception):
    """Suite ya da sonuç dosyası kullanılamıyor; mesaj kullanıcıya gösterilir."""


@dataclass(frozen=True)
class Condition:
    name: str
    arch_context: bool
    metric_rules: bool
    max_iter: int


@dataclass(frozen=True)
class Target:
    project: str
    target: str
    tests: str | None


@dataclass(frozen=True)
class Suite:
    name: str
    repeats: int
    temperature: float
    conditions: tuple[Condition, ...]
    targets: tuple[Target, ...]
    path: Path
    sha: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BenchError(message)


def load_suite(path: Path) -> Suite:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
        raw = yaml.safe_load(text) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise BenchError(f"Could not read the suite {path}: {exc}") from exc
    _require(isinstance(raw, dict), f"{path}: the suite must be a mapping")
    for key in ("name", "repeats", "temperature", "conditions", "targets"):
        _require(key in raw, f"{path}: missing `{key}`")
    _require(isinstance(raw["repeats"], int) and raw["repeats"] >= 1, "`repeats` must be >= 1")
    conditions = []
    for item in raw["conditions"]:
        _require(
            set(item) == {"name", "arch_context", "metric_rules", "max_iter"},
            f"condition {item!r}: expected name, arch_context, metric_rules, max_iter",
        )
        conditions.append(Condition(**item))
    names = [c.name for c in conditions]
    _require(len(names) == len(set(names)), "condition names must be unique")
    targets = []
    for item in raw["targets"]:
        _require({"project", "target"} <= set(item), f"target {item!r}: needs project, target")
        targets.append(Target(item["project"], item["target"], item.get("tests")))
    return Suite(
        name=str(raw["name"]),
        repeats=raw["repeats"],
        temperature=float(raw["temperature"]),
        conditions=tuple(conditions),
        targets=tuple(targets),
        path=path,
        sha=hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
    )


def project_files(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in Path(directory).rglob("*")
        if path.is_file()
        and not IGNORED_PARTS.intersection(path.relative_to(directory).parts)
        and path.suffix not in (".pyc",)
    )


def project_hash(directory: Path) -> str:
    """Kaynak dosyaların özeti (yol + içerik); satır sonu farkı yok sayılır."""
    digest = hashlib.sha256()
    for path in project_files(directory):
        digest.update(path.relative_to(directory).as_posix().encode("utf-8"))
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()[:16]


def prompt_hash() -> str:
    """Modele giden sabit talimatların özeti; biri değişirse sonuçlar ayrışır."""
    from rlens.advise.prompts import SYSTEM_INSTRUCTION as ADVISE
    from rlens.apply.prompts import SYSTEM_INSTRUCTION as APPLY
    from rlens.chartests.generator import SYSTEM_INSTRUCTION as CHARTESTS
    from rlens.loop.feedback import HEADER

    text = "\n---\n".join([ADVISE, APPLY, CHARTESTS, HEADER])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
