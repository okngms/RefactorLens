"""Sınıfların public arayüz kümesi.

İki yerde kullanılır:

* **Koku kuralları.** `data_class` erişimci oranını sorar; erişimcinin ne
  olduğunu tanımlamak için arayüzü bilmek gerekir.
* **Goodhart koruması (Aşama 4).** v1'de bir model, sınıfın tüm public
  arayüzünü silerek dört metriği birden "iyileştirdi" ve 42 test kırıldı.
  `verify` bu kümenin küçülüp küçülmediğine bakacak.

**Public tanımı konvansiyoneldir.** Python'da erişim denetimi yoktur; `_`
öneki "dışarıdan kullanmayın" demenin yerleşik yoludur. Dunder'lar dilin
protokolüdür, arayüz değildir.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PublicInterface:
    """Bir sınıfın dışarıya açtığı isimler."""

    methods: tuple[str, ...] = ()
    attributes: tuple[str, ...] = ()
    accessors: tuple[str, ...] = ()
    """Tek satırda bir attribute döndüren metotlar. `data_class` bunu kullanır."""

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self.methods) | frozenset(self.attributes)

    @property
    def size(self) -> int:
        return len(self.names)

    @property
    def accessor_ratio(self) -> float | None:
        """Public metotların kaçta kaçı erişimci? Metot yoksa `None`.

        Sıfır yanıltıcı olurdu: metotsuz bir sınıf "hiç erişimcisi yok" değil,
        "sorulacak metodu yok" durumundadır.
        """
        if not self.methods:
            return None
        return round(len(self.accessors) / len(self.methods), 4)

    def to_dict(self) -> dict:
        return {
            "methods": list(self.methods),
            "attributes": list(self.attributes),
            "accessors": list(self.accessors),
            "size": self.size,
        }


@dataclass
class InterfaceDelta:
    """İki arayüz arasındaki fark. Aşama 4'teki Goodhart koruması bunu kullanır."""

    removed: tuple[str, ...] = ()
    added: tuple[str, ...] = ()
    kept: tuple[str, ...] = field(default_factory=tuple)

    @property
    def shrank(self) -> bool:
        return bool(self.removed)

    def to_dict(self) -> dict:
        return {
            "removed": list(self.removed),
            "added": list(self.added),
            "kept": len(self.kept),
        }


def is_public(name: str) -> bool:
    """Dunder ve `_` önekli adlar arayüzün parçası değildir."""
    return not name.startswith("_")


def _is_accessor(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Gövdesi tek bir `return self.<attr>` olan metot.

    Docstring'e izin verilir: belgelenmiş bir erişimci hâlâ erişimcidir.
    Hesaplama yapan, koşul içeren ya da başka nesneye dokunan metot değildir.
    """
    body = [
        statement
        for statement in node.body
        if not (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        )
    ]
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        return False

    value = body[0].value
    positional = node.args.posonlyargs + node.args.args
    receiver = positional[0].arg if positional else None
    return (
        isinstance(value, ast.Attribute)
        and isinstance(value.value, ast.Name)
        and value.value.id == receiver
    )


def public_interface(node: ast.ClassDef) -> PublicInterface:
    """Bir sınıfın public metot, attribute ve erişimci kümesi.

    Attribute kaynakları `class_metrics.assigned_attributes` ile aynıdır: sınıf
    düzeyi atamalar, herhangi bir metottaki `self.x = ...` ve `__slots__`.
    Burada yalnızca public olanlar tutulur.
    """
    methods: list[str] = []
    accessors: list[str] = []
    attributes: set[str] = set()

    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if is_public(item.name):
                methods.append(item.name)
                if _is_accessor(item):
                    accessors.append(item.name)
        elif isinstance(item, ast.Assign):
            attributes.update(
                target.id
                for target in item.targets
                if isinstance(target, ast.Name) and is_public(target.id)
            )
        elif (
            isinstance(item, ast.AnnAssign)
            and isinstance(item.target, ast.Name)
            and is_public(item.target.id)
        ):
            attributes.add(item.target.id)

    for child in ast.walk(node):
        if (
            isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id in ("self", "cls")
            and isinstance(child.ctx, ast.Store)
            and is_public(child.attr)
        ):
            attributes.add(child.attr)

    return PublicInterface(
        methods=tuple(sorted(methods)),
        attributes=tuple(sorted(attributes)),
        accessors=tuple(sorted(accessors)),
    )


def diff_interfaces(before: PublicInterface, after: PublicInterface) -> InterfaceDelta:
    """İki arayüzü karşılaştırır."""
    old, new = before.names, after.names
    return InterfaceDelta(
        removed=tuple(sorted(old - new)),
        added=tuple(sorted(new - old)),
        kept=tuple(sorted(old & new)),
    )
