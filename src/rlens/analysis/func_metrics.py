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

    for child in _walk_own_scope(node):
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


def function_loc(node: FunctionNode) -> int:
    """Fonksiyonun kapladığı fiziksel satır sayısı.

    `def` satırından son satıra kadar, boş satırlar ve yorumlar dahil.
    Dekoratörler hariçtir — dekoratör fonksiyonun uzunluğu değildir.

    Boş satırları ayıklamak daha "adil" görünebilir ama tartışmalıdır ve
    araçlar arasında farklılık yaratır. Basit ve öngörülebilir tanım tercih
    edildi.
    """
    end = getattr(node, "end_lineno", None)
    if end is None:  # pragma: no cover - Python 3.8 öncesi
        return 1
    return end - node.lineno + 1


# --------------------------------------------------------------------------- #
# Parametre sayısı
# --------------------------------------------------------------------------- #


def param_count(node: FunctionNode, *, is_method: bool = False) -> int:
    """Parametre sayısı.

    Konumsal, yalnızca-konumsal, yalnızca-anahtar parametrelerin tümü ile
    `*args` ve `**kwargs` sayılır.

    Metotlarda ilk parametre (`self` / `cls`) sayılmaz — çağıran onu vermez,
    dolayısıyla çağrı yükü oluşturmaz. `@staticmethod` bu kuraldan muaftır;
    onun ilk parametresi gerçek bir parametredir.
    """
    args = node.args
    total = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
    if args.vararg is not None:
        total += 1
    if args.kwarg is not None:
        total += 1

    if is_method and not _is_staticmethod(node):
        positional = args.posonlyargs + args.args
        if positional and positional[0].arg in ("self", "cls"):
            total -= 1

    return total


def _is_staticmethod(node: FunctionNode) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "staticmethod":
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == "staticmethod":
            return True
    return False


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


def measure_function(node: FunctionNode, *, is_method: bool = False) -> FunctionReport:
    """Bir fonksiyonun tüm fonksiyon düzeyi metriklerini hesaplar."""
    return FunctionReport(
        name=node.name,
        lineno=node.lineno,
        cyclomatic_complexity=cyclomatic_complexity(node),
        loc=function_loc(node),
        param_count=param_count(node, is_method=is_method),
        max_nesting=max_nesting(node),
    )


def iter_module_functions(tree: ast.Module) -> list[FunctionNode]:
    """Modülün en üst düzeyindeki fonksiyonlar.

    Sınıf metotları buraya dahil değildir; onlar sınıfın metrikleri kapsamında
    ayrıca ölçülür.
    """
    return [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
