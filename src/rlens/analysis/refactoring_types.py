"""Refactoring türü tespiti: önce/sonra kaynaklarından kural tabanlı sınıflandırma.

`docs/02` §5; RefactoringMiner'ın Python için hafif karşılığı. Yalnızca `ast`.

Birimler: modül fonksiyonları (`f`), metotlar (`Sınıf.m`) ve sınıflar. Gövdeler
satır düzeninden bağımsız karşılaştırılır: üst düzey deyimlerin AST dökümü
(docstring hariç). Kurallar sırayla uygulanır ve açıkladıkları birimleri
tüketir; hiçbir kurala uymayan değişmiş birim `unknown` olur:

1. **Rename**: aynı sahipte bir birim kayboldu, aynı gövdeyle başka adla belirdi.
2. **Extract Class**: yeni bir sınıf, metotlarından en az biri mevcut bir
   sınıfın metoduyla benzer gövdeli. Eski sınıfta aynı adla **delege eden bir
   sarmalayıcı** kaldıysa `delegates: True` ve `delegating_wrappers` — NOM ve
   LCOM4'ü yerinde tutan kalıntı (FINDINGS). Eski sınıfın `__init__`'inden
   yeni sınıfa giden atamalar da bu tespite katılır.
3. **Move Method**: bir metot bir sınıftan kayboldu (ya da sarmalayıcıya
   döndü) ve var olan başka bir sınıfta benzer gövdeyle belirdi.
4. **Extract Method**: yeni bir fonksiyon/metot; değişen bir birim artık onu
   çağırıyor ve küçüldü.
5. **Inline**: bir fonksiyon/metot kayboldu; onu çağıran birim artık
   çağırmıyor ve büyüdü.

`confidence`: kuralın ne kadar emin olduğu. Gövde birebir aynıysa yüksek,
benzerse orta, yalnızca çağrı ilişkisine dayanıyorsa düşük. `unknown` için
0.5: hiçbir kural eşleşmedi, değişiklik ise kesin.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from difflib import SequenceMatcher

EXTRACT_METHOD = "extract_method"
MOVE_METHOD = "move_method"
EXTRACT_CLASS = "extract_class"
INLINE = "inline"
RENAME = "rename"
UNKNOWN = "unknown"

_ORDER = [RENAME, EXTRACT_CLASS, MOVE_METHOD, EXTRACT_METHOD, INLINE, UNKNOWN]

#: Benzer gövde eşiği (deyim dizilerinin oranı).
SIMILAR = 0.8


@dataclass(frozen=True)
class Detection:
    kind: str
    source: str
    target: str
    confidence: float
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "source": self.source,
            "target": self.target,
            "confidence": self.confidence,
            "details": dict(self.details),
        }


@dataclass
class _Unit:
    path: str
    owner: str | None
    name: str
    node: ast.FunctionDef | ast.AsyncFunctionDef

    @property
    def qualname(self) -> str:
        return f"{self.owner}.{self.name}" if self.owner else self.name

    @property
    def key(self) -> tuple[str, str]:
        return (self.path, self.qualname)

    @property
    def body(self) -> tuple[str, ...]:
        statements = list(self.node.body)
        if (
            statements
            and isinstance(statements[0], ast.Expr)
            and isinstance(statements[0].value, ast.Constant)
            and isinstance(statements[0].value.value, str)
        ):
            statements = statements[1:]
        return tuple(ast.dump(statement) for statement in statements)

    @property
    def statements(self) -> set[str]:
        """Gövdedeki her deyimin dökümü, iç içe olanlar dahil."""
        return {
            ast.dump(node)
            for node in ast.walk(self.node)
            if isinstance(node, ast.stmt) and node is not self.node
        }

    @property
    def size(self) -> int:
        return len([n for n in ast.walk(self.node) if isinstance(n, ast.stmt)]) - 1

    @property
    def calls(self) -> set[str]:
        found = set()
        for node in ast.walk(self.node):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    found.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    found.add(node.func.attr)
        return found

    def delegates_to(self, name: str) -> bool:
        """Gövde tek bir `self.<...>.name(...)` çağrısı mı (return ya da ifade)."""
        body = [s for s in self.node.body if not _is_docstring(s)]
        if len(body) != 1 or not isinstance(body[0], (ast.Return, ast.Expr)):
            return False
        call = body[0].value
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)):
            return False
        if call.func.attr != name:
            return False
        base = call.func.value
        while isinstance(base, ast.Attribute):
            base = base.value
        return isinstance(base, ast.Name)


def _is_docstring(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _units(sources: dict[str, str]) -> tuple[dict, dict] | None:
    units: dict[tuple[str, str], _Unit] = {}
    classes: dict[str, str] = {}
    for path, source in sources.items():
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                unit = _Unit(path, None, node.name, node)
                units[unit.key] = unit
            elif isinstance(node, ast.ClassDef):
                classes[node.name] = path
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        unit = _Unit(path, node.name, item.name, item)
                        units[unit.key] = unit
    return units, classes


def _similarity(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def detect(before: dict[str, str], after: dict[str, str]) -> list[Detection]:
    """Önce/sonra kaynakları (yol → metin) arasındaki refactoring'ler."""
    parsed_before, parsed_after = _units(before), _units(after)
    if parsed_before is None or parsed_after is None:
        return []
    old, old_classes = parsed_before
    new, new_classes = parsed_after

    removed = {k: u for k, u in old.items() if k not in new}
    added = {k: u for k, u in new.items() if k not in old}
    changed = {k: new[k] for k in old.keys() & new.keys() if old[k].body != new[k].body}
    found: list[Detection] = []

    # 1. Rename
    for rkey, gone in list(removed.items()):
        for akey, came in list(added.items()):
            if gone.owner == came.owner and gone.path == came.path and gone.body == came.body:
                found.append(Detection(RENAME, gone.qualname, came.qualname, 0.95))
                del removed[rkey], added[akey]
                break

    # 2. Extract Class
    extracted: dict[str, set[str]] = {}
    for cls in sorted(set(new_classes) - set(old_classes)):
        members = [u for u in added.values() if u.owner == cls and not u.name.startswith("__")]
        matches: dict[str, list[tuple[_Unit, _Unit, bool]]] = {}
        for came in members:
            for gone in old.values():
                if not gone.owner or gone.owner == cls or gone.name != came.name:
                    continue
                similar = _similarity(gone.body, came.body) >= SIMILAR
                # Gövde yeniden yazılmış olabilir; eski metot ona delege ediyorsa
                # yine de taşınmıştır (gerçek koşuda `discount_for`).
                current = new.get(gone.key)
                wrapped = current is not None and current.delegates_to(gone.name)
                if similar or wrapped:
                    matches.setdefault(gone.owner, []).append((gone, came, not similar))
        if not matches:
            continue
        source = max(sorted(matches), key=lambda owner: len(matches[owner]))
        pairs = matches[source]
        extracted.setdefault(source, set()).add(cls)
        wrappers = []
        for gone, came, _ in pairs:
            added.pop(came.key, None)
            removed.pop(gone.key, None)
            current = new.get(gone.key)
            if current is not None and current.delegates_to(gone.name):
                wrappers.append(gone.name)
                changed.pop(gone.key, None)
        moved_statements = set().union(*(u.statements for u in new.values() if u.owner == cls))
        for key, unit in list(changed.items()):
            lost = old[key].statements - unit.statements
            if unit.owner == source and lost and lost <= moved_statements:
                changed.pop(key)
        for unit in [u for u in added.values() if u.owner == cls]:
            added.pop(unit.key)
        found.append(
            Detection(
                EXTRACT_CLASS,
                source,
                cls,
                round(min(0.95, 0.6 + 0.1 * len(pairs)), 2),
                {
                    "members": sorted(gone.name for gone, _, _ in pairs),
                    "rewritten": sorted(gone.name for gone, _, rewritten in pairs if rewritten),
                    "delegates": bool(wrappers),
                    "delegating_wrappers": sorted(wrappers),
                },
            )
        )
    # Kaynağın kurucusu çıkarılan sınıfları örnekliyorsa bu Extract Class'ın
    # bağlama adımıdır, ayrı bir değişiklik değil.
    for source, classes in extracted.items():
        for key, unit in list(changed.items()):
            if unit.owner == source and unit.name == "__init__" and unit.calls & classes:
                changed.pop(key)

    # 3. Move Method
    candidates = list(removed.values()) + [
        old[k] for k, u in changed.items() if old[k].owner and u.delegates_to(u.name)
    ]
    for gone in candidates:
        if not gone.owner:
            continue
        for akey, came in list(added.items()):
            if not came.owner or came.owner == gone.owner or came.owner not in old_classes:
                continue
            similarity = _similarity(gone.body, came.body)
            if (came.name == gone.name and similarity >= SIMILAR) or similarity == 1.0:
                delegating = gone.key in new and new[gone.key].delegates_to(gone.name)
                found.append(
                    Detection(
                        MOVE_METHOD,
                        gone.qualname,
                        came.qualname,
                        1.0 if similarity == 1.0 else 0.8,
                        {"delegates": delegating} if delegating else {},
                    )
                )
                del added[akey]
                removed.pop(gone.key, None)
                changed.pop(gone.key, None)
                break

    # 4. Extract Method
    # Çağıran ya küçülmeli ya da kaybettiği deyimler yeni birimde görünmeli:
    # tek satırlık bir gövdeyi dışarı çıkarmak çağıranı küçültmez.
    for akey, came in sorted(added.items()):
        callers = []
        for key, unit in changed.items():
            if came.name not in unit.calls or unit.owner != came.owner:
                continue
            moved = (old[key].statements - unit.statements) & came.statements
            if unit.size < old[key].size or moved:
                callers.append((bool(moved), old[key].size - unit.size, key, unit))
        if not callers:
            continue
        moved, _, key, caller = max(callers)
        found.append(
            Detection(EXTRACT_METHOD, caller.qualname, came.qualname, 0.9 if moved else 0.6)
        )
        del added[akey], changed[key]

    # 5. Inline — simetrik: çağıran büyüdü ya da kaybolan birimin deyimlerini kazandı.
    for rkey, gone in sorted(removed.items()):
        callers = []
        for key, unit in changed.items():
            if gone.name not in old[key].calls or gone.name in unit.calls:
                continue
            moved = (unit.statements - old[key].statements) & gone.statements
            if unit.size > old[key].size or moved:
                callers.append((bool(moved), unit.size - old[key].size, key, unit))
        if not callers:
            continue
        moved, _, key, caller = max(callers)
        found.append(Detection(INLINE, gone.qualname, caller.qualname, 0.9 if moved else 0.6))
        del removed[rkey], changed[key]

    for unit in changed.values():
        found.append(Detection(UNKNOWN, unit.qualname, unit.qualname, 0.5))

    return sorted(found, key=lambda d: (_ORDER.index(d.kind), d.source, d.target))
