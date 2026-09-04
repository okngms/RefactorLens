"""Modül düzeyi import grafiği.

Katman analizinin temeli budur: kim kimi import ediyor. Grafik yalnızca
**proje-içi** kenarları içerir; standart kütüphane ve üçüncü parti importlar
mimari bir şey söylemez.

İki zorluk var ve ikisi de burada karara bağlanır.

**İsim çözümü.** Tarayıcı modülleri yola göre adlandırır
(`src.domain.entities`), ama kod `from domain.entities import Order` yazar —
çünkü çalışma zamanında `src/` yolun kökündedir. Bu ikisini eşlemek gerekir.
Eşleme belirsizse kenar **kurulmaz** ve `unresolved` listesine yazılır; yanlış
kenar, olmayan kenardan kötüdür çünkü olmayan bir ihlal üretir.

**Zayıf importlar.** Fonksiyon veya koşul içindeki import gerçek bir
bağımlılıktır ama farklı ağırlıktadır: çoğu zaman döngüyü kırmak için bilerek
oraya konmuştur. Kenar `weak` işaretlenir; ihlal tespiti bunu dikkate alır.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from rlens.analysis.parser import ParsedModule


@dataclass(frozen=True)
class ImportEdge:
    """Bir modülden diğerine bağımlılık."""

    source: str
    target: str
    weak: bool
    """Fonksiyon/koşul içinde mi? Modül düzeyi importlar güçlüdür."""

    lineno: int

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "weak": self.weak,
            "lineno": self.lineno,
        }


@dataclass(frozen=True)
class UnresolvedImport:
    """Proje-içi olabilecek ama kesin eşlenemeyen import."""

    source: str
    text: str
    lineno: int
    reason: str


@dataclass
class ImportGraph:
    """Proje-içi modül bağımlılıkları."""

    modules: tuple[str, ...]
    edges: list[ImportEdge] = field(default_factory=list)
    unresolved: list[UnresolvedImport] = field(default_factory=list)

    def imports_of(self, module: str, *, include_weak: bool = True) -> set[str]:
        """Bu modülün bağımlı olduğu modüller (efferent)."""
        return {
            edge.target
            for edge in self.edges
            if edge.source == module and (include_weak or not edge.weak)
        }

    def importers_of(self, module: str, *, include_weak: bool = True) -> set[str]:
        """Bu modülü import eden modüller (afferent)."""
        return {
            edge.source
            for edge in self.edges
            if edge.target == module and (include_weak or not edge.weak)
        }

    def adjacency(self, *, include_weak: bool = True) -> dict[str, set[str]]:
        """Her modül için hedef kümesi. Kenarsız modüller de anahtar olarak yer alır."""
        result: dict[str, set[str]] = {module: set() for module in self.modules}
        for edge in self.edges:
            if include_weak or not edge.weak:
                result.setdefault(edge.source, set()).add(edge.target)
        return result

    def edges_between(self, source: str, target: str) -> list[ImportEdge]:
        return [e for e in self.edges if e.source == source and e.target == target]

    def to_dict(self) -> dict:
        return {
            "modules": list(self.modules),
            "edges": [edge.to_dict() for edge in self.edges],
            "unresolved": [
                {"source": u.source, "text": u.text, "lineno": u.lineno, "reason": u.reason}
                for u in self.unresolved
            ],
        }


class _Resolver:
    """Import ifadesindeki adı proje modülüne eşler.

    Eşleme sırayla denenir ve ilk kesin sonuçta durur:

    1. **Tam eşleşme.** `domain.entities` diye bir modül var mı?
    2. **Kök paket kırpma.** Tarama kökü paketin kendisiyse (`rlens arch
       src/rlens`) modül adları paket önekini taşımaz (`verify.diff`) ama kod
       taşır (`rlens.verify.diff`). Bilinen kök paket adı kırpılıp yeniden
       denenir. Yalnızca **bilinen** kök adı kırpılır; rastgele önek atmak
       `os.path` gibi importları proje modülüne eşleyebilirdi.
    3. **Sonek eşleşmesi.** `src.domain.entities` gibi tek bir modül bu adla
       bitiyor mu? Birden fazla aday varsa belirsizdir ve kenar kurulmaz.
    4. **Üst paket.** `from domain import entities` biçiminde `domain.entities`
       bir modül olabilir.
    """

    def __init__(self, modules: tuple[str, ...], root_package: str | None = None):
        self._modules = set(modules)
        self._root_package = root_package
        self._by_suffix: dict[str, list[str]] = {}
        for module in modules:
            parts = module.split(".")
            for index in range(len(parts)):
                self._by_suffix.setdefault(".".join(parts[index:]), []).append(module)

    def resolve(self, name: str) -> tuple[str | None, str]:
        """Returns: (modül adı ya da None, neden)."""
        if not name:
            return None, "empty import target"
        if name in self._modules:
            return name, ""
        if self._root_package and name.startswith(self._root_package + "."):
            stripped = name[len(self._root_package) + 1 :]
            if stripped in self._modules:
                return stripped, ""
        candidates = self._by_suffix.get(name, [])
        if len(candidates) == 1:
            return candidates[0], ""
        if len(candidates) > 1:
            return None, f"ambiguous: matches {', '.join(sorted(candidates))}"
        return None, "not a project module"


def _is_weak(node: ast.AST, strong_nodes: set[int]) -> bool:
    """Modül gövdesinin en üstünde olmayan her import zayıftır."""
    return id(node) not in strong_nodes


def _strong_import_ids(tree: ast.Module) -> set[int]:
    """Modül gövdesinde doğrudan duran import ifadeleri."""
    return {id(node) for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))}


def _absolute_name(module: ParsedModule, node: ast.ImportFrom) -> str | None:
    """Göreli importu mutlak modül adına çevirir.

    `from .entities import X` → paket + `entities`.
    `from ..core import Y`    → bir üst paket + `core`.
    """
    if node.level == 0:
        return node.module
    parts = module.module.split(".")
    # `__init__` zaten paket adına indirgenmiştir; bir seviye çıkmak yeterlidir.
    base = parts[: len(parts) - node.level]
    if node.module:
        base = base + node.module.split(".")
    return ".".join(base) if base else None


def build_import_graph(modules: list[ParsedModule], root_package: str | None = None) -> ImportGraph:
    """Ayrıştırılmış modüllerden proje-içi import grafiğini kurar.

    Args:
        modules: Ayrıştırılmış modüller.
        root_package: Tarama kökünün paket adı. `rlens arch src/rlens`
            çalıştırıldığında modül adları paket önekini taşımaz ama kod taşır;
            bu ad verilirse kırpılarak eşleme yapılır.
    """
    names = tuple(module.module for module in modules)
    resolver = _Resolver(names, root_package)
    graph = ImportGraph(modules=names)
    seen: set[tuple[str, str, bool]] = set()

    for module in modules:
        strong = _strong_import_ids(module.tree)

        for node in ast.walk(module.tree):
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
                text = "import " + ", ".join(targets)
            elif isinstance(node, ast.ImportFrom):
                base = _absolute_name(module, node)
                if base is None:
                    continue
                # `from pkg import mod` biçiminde `mod` bir alt modül olabilir.
                targets = [base] + [f"{base}.{alias.name}" for alias in node.names]
                text = f"from {base} import " + ", ".join(a.name for a in node.names)
            else:
                continue

            weak = _is_weak(node, strong)
            resolved_any = False
            reasons: list[str] = []

            for target in targets:
                name, reason = resolver.resolve(target)
                if name is None:
                    if reason and reason != "not a project module":
                        reasons.append(f"{target}: {reason}")
                    continue
                if name == module.module:
                    continue  # kendini import etmek kenar değildir
                resolved_any = True
                key = (module.module, name, weak)
                if key in seen:
                    continue
                seen.add(key)
                graph.edges.append(
                    ImportEdge(
                        source=module.module,
                        target=name,
                        weak=weak,
                        lineno=node.lineno,
                    )
                )

            if not resolved_any and reasons:
                graph.unresolved.append(
                    UnresolvedImport(
                        source=module.module,
                        text=text,
                        lineno=node.lineno,
                        reason="; ".join(reasons),
                    )
                )

    graph.edges.sort(key=lambda e: (e.source, e.target, e.lineno))
    return graph
