"""Fonksiyon ve metot düzeyi metrikler.

Her metriğin kuralı burada açıkça tanımlıdır. Bir metrik ancak neyi saydığı
bilindiğinde anlamlıdır: "karmaşıklık 15" tek başına bir şey ifade etmez,
"15 karar noktası" eder.

**Ortak kural — iç içe tanımlara inilmez.** Bir fonksiyonun içinde tanımlanmış
başka bir fonksiyon veya sınıf varsa, onun gövdesi dıştaki fonksiyonun
metriklerine dahil edilmez. Aksi halde tek bir kapatma (closure) barındıran
fonksiyon, kendi mantığı basit olmasına rağmen karmaşık görünürdü.
"""

from __future__ import annotations

import ast
import io
import tokenize

from rlens.analysis.entry_points import entry_point_kind
from rlens.analysis.model import FunctionReport

#: Bir fonksiyonun gövdesinde iç içelik seviyesi oluşturan düğümler.
_NESTING_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.TryStar,
    ast.Match,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
)

#: İç içe tanımlar: metrik hesabında gövdelerine inilmez.
_NESTED_DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def _child_statements(node: ast.AST) -> list[ast.stmt]:
    """Bir düğümün doğrudan alt gövdelerindeki ifadeleri toplar."""
    statements: list[ast.stmt] = []
    for field in ("body", "orelse", "finalbody"):
        statements.extend(getattr(node, field, []) or [])
    for handler in getattr(node, "handlers", []) or []:
        statements.extend(handler.body)
    for case in getattr(node, "cases", []) or []:
        statements.extend(case.body)
    return statements


def _is_elif(node: ast.If) -> bool:
    """`else: if ...` ile `elif` ayrımı.

    `ast` her ikisini de aynı şekilde temsil eder: `orelse` içinde tek bir `If`.
    Ayrım sütun konumundan yapılır — `elif` dıştaki `if` ile aynı sütunda başlar,
    `else` içindeki `if` ise girintilidir.

    Bu ayrım iç içelik derinliği için gereklidir: on dallı bir `elif` zinciri
    on seviye derin değildir, düz bir zincirdir.
    """
    if len(node.orelse) != 1:
        return False
    inner = node.orelse[0]
    return isinstance(inner, ast.If) and inner.col_offset == node.col_offset


# --------------------------------------------------------------------------- #
# Cyclomatic complexity
# --------------------------------------------------------------------------- #


def _walk_own_scope(node: ast.AST):
    """Düğümün kendi kapsamındaki tüm alt düğümleri gezer.

    `ast.walk` ağacı düzleştirir ve iç içe tanımların içine de girer; bu yüzden
    kullanılamaz. Burada iç içe fonksiyon/sınıf tanımlarına **inilmez**, böylece
    bir kapatma (closure) barındıran fonksiyon, kendi mantığı basit olmasına
    rağmen karmaşık görünmez.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _NESTED_DEFINITIONS):
            continue
        yield child
        yield from _walk_own_scope(child)


def _walk_body(node: FunctionNode):
    """Fonksiyon gövdesindeki düğümler; imza ve dekoratörler hariç."""
    for statement in node.body:
        if isinstance(statement, _NESTED_DEFINITIONS):
            continue
        yield statement
        yield from _walk_own_scope(statement)


def cyclomatic_complexity(node: FunctionNode) -> int:
    """Karar noktası sayısı + 1.

    Sayılanlar:

    * `if` / `elif` — her biri ayrı bir karar (`else` sayılmaz, dal eklemez)
    * `for`, `while` — döngü koşulları
    * `except` bloğu — her biri ayrı bir yol
    * üçlü ifade (`x if c else y`)
    * `and` / `or` — ilk operanddan sonraki her operand (kısa devre = ayrı yol)
    * üreteç/kapsam (comprehension) içindeki her `for` ve her `if`
    * `match` içindeki her `case`

    Sayılmayanlar: `else`, `with`, `assert`, `try` bloğunun kendisi. Bunlar
    yürütme yolu çeşitlendirmez.

    **Yalnızca gövde gezilir.** Dekoratörler, varsayılan argüman değerleri ve
    annotation'lar tanım anında bir kez değerlendirilir; fonksiyon
    çağrıldığında açılan bir yol değildir. `@register(a or b)` fonksiyonun
    karmaşıklığını artırmaz. radon da aynı sınırı çizer.
    """
    complexity = 1

    # Her biri tek bir ek yürütme yolu açan düğümler.
    single_branch = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.IfExp,
        ast.ExceptHandler,
    )

    for child in _walk_body(node):
        if isinstance(child, single_branch):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
        elif isinstance(child, ast.comprehension):
            complexity += 1 + len(child.ifs)
        elif isinstance(child, ast.match_case):
            complexity += 1

    return complexity


# --------------------------------------------------------------------------- #
# Uzunluk
# --------------------------------------------------------------------------- #


_NON_CODE_TOKENS = frozenset(
    {
        tokenize.COMMENT,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENCODING,
        tokenize.ENDMARKER,
    }
)


def code_lines(source: str) -> frozenset[int]:
    """Kaynakta en az bir kod token'ı taşıyan satırların numaraları (1'den).

    Boş satırlar ve yalnızca yorum içeren satırlar dışarıda kalır. Çok satırlı
    bir string'in (docstring dahil) bütün satırları içeridedir; docstring'leri
    ayıklamak `function_loc`'un işidir, çünkü neyin docstring olduğunu AST bilir.

    Modül başına bir kez hesaplanır ve o modüldeki her fonksiyon için kullanılır.
    """
    lines: set[int] = set()
    readline = io.StringIO(source).readline
    for token in tokenize.generate_tokens(readline):
        if token.type in _NON_CODE_TOKENS:
            continue
        lines.update(range(token.start[0], token.end[0] + 1))
    return frozenset(lines)


def _docstring_lines(node: ast.AST, first_code_line: int) -> set[int]:
    """Düğümün kendi docstring'inin satırları; tanım satırıyla aynı satırdaysa boş."""
    body = getattr(node, "body", None)
    if not body:
        return set()
    first = body[0]
    if not (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return set()
    if first.lineno <= first_code_line:
        return set()  # `def f(): "belge"` — satırda kod da var
    return set(range(first.lineno, (first.end_lineno or first.lineno) + 1))


def function_loc(node: FunctionNode, code_lines: frozenset[int]) -> int:
    """Fonksiyonun kod satırı sayısı (şema 3, `docs/v2-tanim-kararlari.md` K1).

    `def` satırından son satıra kadar, **en az bir kod token'ı içeren**
    satırlar. Sayılmayanlar: boş satırlar, yalnızca yorum içeren satırlar,
    fonksiyonun ve içindeki iç içe tanımların docstring'leri. Dekoratörler
    hariçtir — dekoratör fonksiyonun uzunluğu değildir. İmza satırları, `else:`
    ve yalnızca kapanış parantezi içeren satırlar koddur.

    **Neden fiziksel satır değil.** RefactorLens refactoring önerir ve metrik
    iyileşmesini raporlar. Fiziksel sayımda yorum ve docstring silmek LOC'u
    "iyileştirir" ve hiçbir kontrol bunu görmez. Araç belgelenmiş kodu
    cezalandırmamalı. Şema 2 fiziksel satır sayıyordu.

    `code_lines` modülün `code_lines(source)` sonucudur ve zorunludur: kaynak
    metin olmadan yorumlar görünmez, ve kaynaksız bir yedek tanım iki farklı
    LOC'u sessizce aynı rapor alanına yazardı.
    """
    end = node.end_lineno or node.lineno
    span = set(range(node.lineno, end + 1))
    excluded: set[int] = set()
    for child in ast.walk(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            excluded |= _docstring_lines(child, child.lineno)
    return len((span & code_lines) - excluded)


# --------------------------------------------------------------------------- #
# Parametre sayısı
# --------------------------------------------------------------------------- #


def parameter_slots(node: FunctionNode, *, is_method: bool = False) -> list[ast.arg]:
    """Parametre yuvaları; `param_count` ve anotasyon kapsamı aynı kümeyi sayar.

    Konumsal, yalnızca-konumsal, yalnızca-anahtar parametrelerin tümü ile
    `*args` ve `**kwargs`.

    Metotlarda ilk parametre (`self` / `cls`) yuva değildir — çağıran onu
    vermez, dolayısıyla çağrı yükü oluşturmaz. `@staticmethod` bu kuraldan
    muaftır; onun ilk parametresi gerçek bir parametredir.
    """
    args = node.args
    positional = args.posonlyargs + args.args
    if (
        is_method
        and not _is_staticmethod(node)
        and positional
        and positional[0].arg in ("self", "cls")
    ):
        positional = positional[1:]
    slots = positional + args.kwonlyargs
    slots += [extra for extra in (args.vararg, args.kwarg) if extra is not None]
    return slots


def param_count(node: FunctionNode, *, is_method: bool = False) -> int:
    """Parametre sayısı: `parameter_slots`'un uzunluğu."""
    return len(parameter_slots(node, is_method=is_method))


# --------------------------------------------------------------------------- #
# Anotasyon kapsamı (v2.2 §3)
# --------------------------------------------------------------------------- #


def annotation_coverage(node: FunctionNode, *, is_method: bool = False) -> float | None:
    """Annotation'lı parametre yuvası payı; yuva yoksa `None`.

    Betimseldir, yönü yoktur: yüksek değer "daha iyi" demek değil, imzada daha
    çok tip bilgisi **yazılı** demektir. String annotation ve `Any` sayılır.
    Ön kayıt: `experiments/hardening/annotation-coverage.md`.
    """
    slots = parameter_slots(node, is_method=is_method)
    if not slots:
        return None
    return round(sum(1 for slot in slots if slot.annotation is not None) / len(slots), 4)


def returns_annotated(node: FunctionNode) -> bool:
    """Dönüş annotation'ı yazılmış mı (`-> None` dahil)."""
    return node.returns is not None


def _has_decorator(node: FunctionNode, name: str) -> bool:
    """`@name` ya da `@modul.name` biçiminde dekore edilmiş mi."""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == name:
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == name:
            return True
    return False


def _is_staticmethod(node: FunctionNode) -> bool:
    return _has_decorator(node, "staticmethod")


def is_staticmethod(node: FunctionNode) -> bool:
    """`@staticmethod`: ilk parametresi alıcı (`self`/`cls`) değildir."""
    return _is_staticmethod(node)


def is_overload_stub(node: FunctionNode) -> bool:
    """`@overload` / `@typing.overload` taslağı.

    Taslaklar yalnızca tip beyanıdır; çalışma zamanında aynı adlı son tanım
    onları ezer. Metot ya da fonksiyon olarak sayılırsa üç taslaklı bir
    fonksiyon NOM'u üç kez artırır.
    """
    return _has_decorator(node, "overload")


# --------------------------------------------------------------------------- #
# İç içelik derinliği
# --------------------------------------------------------------------------- #


def max_nesting(node: FunctionNode) -> int:
    """En derin iç içe blok seviyesi.

    Fonksiyon gövdesi 0'dır. Gövdedeki bir `for` 1, onun içindeki bir `if` 2
    olur. `elif` zincirleri derinlik eklemez (bkz. `_is_elif`).

    İç içe fonksiyon/sınıf tanımları bir seviye sayılır ama gövdelerine
    inilmez — dıştaki fonksiyonun karmaşıklığı, içindeki fonksiyonun
    karmaşıklığı değildir.
    """

    def depth_of(statements: list[ast.stmt], current: int) -> int:
        deepest = current
        for statement in statements:
            if not isinstance(statement, _NESTING_NODES):
                continue

            if isinstance(statement, _NESTED_DEFINITIONS):
                deepest = max(deepest, current + 1)
                continue

            if isinstance(statement, ast.If):
                # `elif` zincirini yatay olarak yürü, derinlik ekleme.
                branch: ast.If = statement
                while True:
                    deepest = max(deepest, depth_of(branch.body, current + 1))
                    if _is_elif(branch):
                        branch = branch.orelse[0]  # type: ignore[assignment]
                        continue
                    if branch.orelse:
                        deepest = max(deepest, depth_of(branch.orelse, current + 1))
                    break
                deepest = max(deepest, current + 1)
                continue

            deepest = max(deepest, depth_of(_child_statements(statement), current + 1))
        return deepest

    return depth_of(node.body, 0)


# --------------------------------------------------------------------------- #
# Toplama
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Dinamik opaklık (v2.2 §3, K13)
# --------------------------------------------------------------------------- #

_ATTRIBUTE_BUILTINS = ("getattr", "setattr", "delattr", "hasattr")
_DYNAMIC_IMPORTS = ("__import__", "importlib.import_module")


def _is_string(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _callee(call: ast.Call) -> str | None:
    """`f(...)` → "f"; `importlib.import_module(...)` → "importlib.import_module"."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
        return f"{call.func.value.id}.{call.func.attr}"
    return None


def dynamic_sites(node: FunctionNode) -> list[tuple[int, str]]:
    """Statik analizin hedefini göremediği noktalar: (satır, tür), konuma göre.

    Türler: ikinci argümanı string sabiti olmayan `getattr`/`setattr`/
    `delattr`/`hasattr`; `eval`/`exec`; ilk argümanı sabit olmayan
    `__import__`/`importlib.import_module`; fonksiyonun **kendi** `**kwargs`
    parametresinin bir çağrıya aktarılması (`kwargs`). İç içe tanımlara
    inilmez; dekoratörler ve varsayılan değerler gövde değildir. Betimseldir,
    yönü yoktur. Ön kayıt: `experiments/hardening/dynamic-opacity.md`.
    """
    own_kwargs = node.args.kwarg.arg if node.args.kwarg else None
    found: list[tuple[int, int, str]] = []
    for child in _walk_body(node):
        if not isinstance(child, ast.Call):
            continue
        name = _callee(child)
        kind = None
        if name in _ATTRIBUTE_BUILTINS:
            if len(child.args) >= 2 and not _is_string(child.args[1]):
                kind = name
        elif name in ("eval", "exec"):
            kind = name
        elif name in _DYNAMIC_IMPORTS and child.args and not _is_string(child.args[0]):
            kind = "import"
        if kind:
            found.append((child.lineno, child.col_offset, kind))
        if own_kwargs:
            for keyword in child.keywords:
                if (
                    keyword.arg is None
                    and isinstance(keyword.value, ast.Name)
                    and keyword.value.id == own_kwargs
                ):
                    found.append((keyword.value.lineno, keyword.value.col_offset, "kwargs"))
    return [(line, kind) for line, _, kind in sorted(found)]


def measure_function(
    node: FunctionNode, *, code_lines: frozenset[int], is_method: bool = False
) -> FunctionReport:
    """Bir fonksiyonun tüm fonksiyon düzeyi metriklerini hesaplar.

    `code_lines`, fonksiyonun modülünün `code_lines(source)` sonucudur (LOC için).
    """
    return FunctionReport(
        name=node.name,
        lineno=node.lineno,
        cyclomatic_complexity=cyclomatic_complexity(node),
        loc=function_loc(node, code_lines),
        param_count=param_count(node, is_method=is_method),
        max_nesting=max_nesting(node),
        entry_point=entry_point_kind(node),
        annotation_coverage=annotation_coverage(node, is_method=is_method),
        returns_annotated=returns_annotated(node),
        dynamic_sites=len(dynamic_sites(node)),
    )


def iter_module_functions(tree: ast.Module) -> list[FunctionNode]:
    """Modülün en üst düzeyindeki fonksiyonlar.

    Sınıf metotları buraya dahil değildir; onlar sınıfın metrikleri kapsamında
    ayrıca ölçülür. `@overload` taslakları da dahil değildir (bkz.
    `is_overload_stub`).
    """
    return [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not is_overload_stub(node)
    ]
