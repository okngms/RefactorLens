"""Sınıf düzeyi metrikler: NOM, WMC, DAM, LCOM4, DCC, CAM.

**Ortak metot kümesi.** Altı metriğin tamamı aynı metot kümesi üzerinde çalışır:
sınıf gövdesinde doğrudan tanımlı, dunder olmayan metotlar. Bu tutarlılık
bilinçlidir — WMC'nin "NOM'daki metotların karmaşıklık toplamı" olması, iki
metriğin birlikte okunabilmesi için gereklidir.

**`__init__` neden dışarıda?** Özellikle LCOM4 için kritiktir. Kurucu metot
tanım gereği sınıfın tüm attribute'larına dokunur; sayıma girseydi her sınıfın
bütün metotlarını tek bileşende birleştirir ve metriği tamamen işlevsiz
bırakırdı. Klasik LCOM4 tanımı da kurucuları bu sebeple dışlar.

**Hesaplanamayan metrik uydurulmaz.** Bir metrik güvenilir hesaplanamıyorsa
`None` döner ve mümkünse nedeni raporlanır (bkz. CAM).
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass

from rlens.analysis.func_metrics import (
    FunctionNode,
    cyclomatic_complexity,
    is_overload_stub,
    is_staticmethod,
    measure_function,
    parameter_slots,
)
from rlens.analysis.model import ClassReport

#: CAM atlandığında rapora yazılan neden.
CAM_INSUFFICIENT_ANNOTATIONS = "insufficient_annotations"

#: Hiç annotate parametre bulunmadığında yazılan neden.
CAM_NO_PARAMETERS = "no_annotated_parameters"


def is_dunder(name: str) -> bool:
    """`__init__`, `__repr__` gibi özel metot/attribute adları."""
    return name.startswith("__") and name.endswith("__")


def class_methods(node: ast.ClassDef) -> list[FunctionNode]:
    """Metriklerin üzerinde çalıştığı metot kümesi.

    Dahil: normal metotlar, `@property`, `@staticmethod`, `@classmethod`.
    Hariç: dunder metotlar (`__init__` dahil), iç içe tanımlı fonksiyonlar,
    iç içe sınıfların metotları, `@overload` taslakları.

    `node.body` üzerinde doğrudan yürüdüğümüz için iç içe tanımlar zaten
    kapsam dışında kalır.

    Property getter ve setter aynı adı taşır ama iki ayrı gövdedir; ikisi de
    sayılır. Taslaklar ise gövde değil tip beyanıdır.
    """
    return [
        item
        for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not is_dunder(item.name)
        and not is_overload_stub(item)
    ]


def all_methods(node: ast.ClassDef) -> list[FunctionNode]:
    """Dunder'lar dahil tüm metotlar — attribute toplamak için gerekir."""
    return [item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]


# --------------------------------------------------------------------------- #
# Taslak metotlar (K10)
# --------------------------------------------------------------------------- #


def is_stub_body(method: FunctionNode) -> bool:
    """Docstring dışında yalnızca `pass`, `...`, `return`/`return None` ya da
    `raise NotImplementedError` içeren gövde.

    Bunlar davranış değil sözleşmedir: alt sınıfın dolduracağı yer. Soyut
    arayüzler (`NodeVisitor`) yüzlerce böyle metot taşır.
    """
    body = list(method.body)
    first = body[0] if body else None
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        body = body[1:]
    if not body:
        return True
    if len(body) != 1:
        return False
    statement = body[0]
    if isinstance(statement, ast.Pass):
        return True
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
        return statement.value.value is Ellipsis
    if isinstance(statement, ast.Return):
        return statement.value is None or (
            isinstance(statement.value, ast.Constant) and statement.value.value is None
        )
    if isinstance(statement, ast.Raise) and statement.exc is not None:
        target = statement.exc.func if isinstance(statement.exc, ast.Call) else statement.exc
        return isinstance(target, ast.Name) and target.id == "NotImplementedError"
    return False


def stub_method_names(node: ast.ClassDef) -> set[str]:
    """Bütün tanımları taslak olan metot adları (`class_methods` kümesi, adla).

    Adla sayılır, çünkü `lcom4` de adla düğüm yapar: property getter/setter tek
    addır. Tanımlardan biri bile gerçek gövdeliyse ad taslak değildir.
    """
    real: set[str] = set()
    stubs: set[str] = set()
    for method in class_methods(node):
        (stubs if is_stub_body(method) else real).add(method.name)
    return stubs - real


def stub_method_share(node: ast.ClassDef) -> float | None:
    """Taslak metot adlarının bütün metot adlarına payı; metot yoksa `None`."""
    names = {method.name for method in class_methods(node)}
    if not names:
        return None
    return round(len(stub_method_names(node)) / len(names), 4)


# --------------------------------------------------------------------------- #
# NOM — Number of Methods
# --------------------------------------------------------------------------- #


def nom(node: ast.ClassDef) -> int:
    """Sınıfta tanımlı metot sayısı (dunder'lar hariç)."""
    return len(class_methods(node))


# --------------------------------------------------------------------------- #
# WMC — Weighted Methods per Class
# --------------------------------------------------------------------------- #


def wmc(node: ast.ClassDef) -> int:
    """NOM'a dahil metotların cyclomatic complexity toplamı.

    Aynı metot kümesi kullanılır; böylece "25 metot, toplam karmaşıklık 40"
    ifadesi tutarlı iki sayı verir.
    """
    return sum(cyclomatic_complexity(method) for method in class_methods(node))


# --------------------------------------------------------------------------- #
# Attribute toplama (DAM ve LCOM4'ün ortak temeli)
# --------------------------------------------------------------------------- #


def self_parameter(method: FunctionNode) -> str | None:
    """Metodun alıcı parametresinin adı (`self` / `cls`), yoksa None.

    `@staticmethod`'un alıcısı yoktur: `def from_row(row)` içindeki `row`
    sınıfın örneği değildir. İlk parametreyi alıcı saymak `row.name`'i
    sınıfın `name` attribute'u yapar ve LCOM4'ü sahte biçimde düşürür.
    """
    if is_staticmethod(method):
        return None
    positional = method.args.posonlyargs + method.args.args
    return positional[0].arg if positional else None


def _binds_name(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda, name: str) -> bool:
    """İç içe fonksiyon ya da lambda bu adı kendi parametresi olarak bağlıyor mu."""
    args = node.args
    every = args.posonlyargs + args.args + args.kwonlyargs
    for extra in (args.vararg, args.kwarg):
        if extra is not None:
            every.append(extra)
    return any(argument.arg == name for argument in every)


def walk_receiver_scope(method: FunctionNode, receiver: str) -> Iterator[ast.AST]:
    """Metodun içinde `receiver` adının hâlâ bu sınıfın örneği olduğu düğümler.

    `ast.walk` iç içe tanımların içine iner. İki durumda bu yanlıştır:

    * **İç içe sınıf.** Onun metotlarındaki `self` başka bir nesnedir.
    * **Alıcı adını yeniden bağlayan iç fonksiyon** (`def patched(self): ...`).

    Alıcıyı yakalayan kapatma (closure) ise gezilir: `def inner(): self.x`
    gerçekten dıştaki örneğe erişir.
    """
    stack: list[ast.AST] = list(ast.iter_child_nodes(method))
    while stack:
        node = stack.pop()
        if isinstance(node, ast.ClassDef):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and _binds_name(
            node, receiver
        ):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def assigned_attributes(node: ast.ClassDef) -> set[str]:
    """Sınıfın attribute kümesi.

    Üç kaynağın birleşimidir:

    1. Sınıf düzeyi atamalar ve annotation'lar (`x = 5`, `x: int`), `ClassVar` dahil
    2. **Herhangi bir** metot içindeki `self.<ad> = ...` atamaları (yalnızca
       `__init__` değil — attribute'lar başka metotlarda da doğabilir)
    3. `__slots__` içinde listelenen adlar

    Yalnızca okunan adlar (hiç atanmayan `self.x`) attribute sayılmaz; onlar
    başka bir yerden gelen veriye erişimdir, sınıfın kendi durumu değildir.

    Dunder adlar (`__slots__` gibi) kümeye alınmaz — onlar Python'un
    protokolüdür, sınıfın verisi değil.
    """
    attributes: set[str] = set()

    for item in node.body:
        # 1. Sınıf düzeyi
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    attributes.add(target.id)
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            attributes.add(item.target.id)

    # 3. __slots__
    attributes |= _slot_names(node)

    # 2. Metot içi self atamaları
    for method in all_methods(node):
        receiver = self_parameter(method)
        if receiver is None:
            continue
        attributes |= _assigned_via_self(method, receiver)

    return {name for name in attributes if not is_dunder(name)}


def _slot_names(node: ast.ClassDef) -> set[str]:
    """`__slots__ = ("a", "b")` içindeki adlar."""
    names: set[str] = set()
    for item in node.body:
        targets = item.targets if isinstance(item, ast.Assign) else []
        if not any(isinstance(t, ast.Name) and t.id == "__slots__" for t in targets):
            continue
        value = item.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            names.add(value.value)
        elif isinstance(value, (ast.Tuple, ast.List, ast.Set)):
            names.update(
                element.value
                for element in value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            )
    return names


def _assigned_via_self(method: FunctionNode, receiver: str) -> set[str]:
    """Metot içinde `self.<ad> = ...` biçiminde atanan adlar.

    Artırmalı atama (`self.x += 1`) ve çoklu hedefli atama da sayılır.
    """
    assigned: set[str] = set()

    def record(target: ast.AST) -> None:
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == receiver
        ):
            assigned.add(target.attr)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                record(element)

    for child in walk_receiver_scope(method, receiver):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                record(target)
        elif isinstance(child, (ast.AugAssign, ast.AnnAssign)):
            record(child.target)

    return assigned


def accessed_attributes(method: FunctionNode, known_methods: set[str]) -> set[str]:
    """Metodun dokunduğu `self.<ad>` adlarından metot olmayanlar.

    Okuma ve yazma ayrımı yapılmaz: LCOM4 açısından iki metot aynı veriye
    dokunuyorsa — ister okusun ister yazsın — ilişkilidir.
    """
    receiver = self_parameter(method)
    if receiver is None:
        return set()

    return {
        child.attr
        for child in walk_receiver_scope(method, receiver)
        if isinstance(child, ast.Attribute)
        and isinstance(child.value, ast.Name)
        and child.value.id == receiver
        and child.attr not in known_methods
    }


def called_methods(method: FunctionNode, known_methods: set[str]) -> set[str]:
    """Metodun çağırdığı (veya referans verdiği) kardeş metotlar.

    `self.other()` çağrısı ile `self.other` referansı aynı sayılır; ikisi de
    iki metodu birbirine bağlar.
    """
    receiver = self_parameter(method)
    if receiver is None:
        return set()

    return {
        child.attr
        for child in walk_receiver_scope(method, receiver)
        if isinstance(child, ast.Attribute)
        and isinstance(child.value, ast.Name)
        and child.value.id == receiver
        and child.attr in known_methods
    }


# --------------------------------------------------------------------------- #
# DAM — Data Access Metric
# --------------------------------------------------------------------------- #


def _is_private(name: str) -> bool:
    """`_x` ve `__x` private sayılır; dunder'lar zaten kümede yoktur."""
    return name.startswith("_")


def _is_strictly_private(name: str) -> bool:
    """Yalnızca `__x` — Python'un ad değiştirme (name mangling) mekanizması."""
    return name.startswith("__")


def dam(node: ast.ClassDef) -> tuple[float | None, float | None]:
    """Private attribute oranı.

    İki değer döner:

    * `dam` — `_x` ve `__x` birlikte. Python konvansiyonunda `_` öneki
      "dışarıdan kullanmayın" demektir ve fiilen private sayılır.
    * `dam_strict` — yalnızca `__x`. Dilin gerçekten koruma sağladığı hal.

    İkisi birlikte verilir çünkü "konvansiyon mu, gerçek koruma mu" sorusu
    tartışmalıdır ve okuyucunun kendi kararını verebilmesi gerekir.

    Attribute yoksa ikisi de `None` — bölme yapılamaz, sıfır da anlamsız olur.
    """
    attributes = assigned_attributes(node)
    if not attributes:
        return None, None

    total = len(attributes)
    loose = sum(1 for name in attributes if _is_private(name)) / total
    strict = sum(1 for name in attributes if _is_strictly_private(name)) / total
    return round(loose, 4), round(strict, 4)


# --------------------------------------------------------------------------- #
# LCOM4 — Lack of Cohesion of Methods
# --------------------------------------------------------------------------- #


def lcom4(node: ast.ClassDef) -> int | None:
    """Metot–attribute grafiğindeki bağlı bileşen sayısı.

    İki metot şu durumlarda aynı bileşendedir:

    * Ortak bir `self.<attr>` kullanıyorlarsa
    * Biri diğerini `self.<method>()` ile çağırıyorsa

    Yorumu: **1 = kohezyonlu** (tek sorumluluk), **≥2 = sınıf muhtemelen
    bölünebilir**. Değer, sınıfın kaç ayrı sorumluluğa ayrıldığını söyler.

    Hiçbir attribute'a dokunmayan ve hiçbir kardeşini çağırmayan bir metot
    kendi başına bir bileşendir — sınıfla ilişkisi yoktur, dışarı taşınabilir.

    Metot yoksa `None` döner (şema 3, `docs/v2-tanim-kararlari.md` K2):
    kohezyon sorusu sorulamaz. `None` "eksik" değil "tanımsız" demektir; veri
    sınıfı için doğru cevap budur. Şema 2 burada `0` döndürüyordu ve bu
    "hesaplanamayan metrik `null`" invariant'ını ihlal ediyordu; `0` LCOM4'ün
    tanım aralığında (≥ 1) bile değildir.
    """
    methods = class_methods(node)
    if not methods:
        return None

    known = {method.name for method in methods}
    parent: dict[str, str] = {method.name: method.name for method in methods}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    # Attribute paylaşımı üzerinden birleştirme
    owners: dict[str, list[str]] = {}
    for method in methods:
        for attribute in accessed_attributes(method, known):
            owners.setdefault(attribute, []).append(method.name)

    for sharers in owners.values():
        first = sharers[0]
        for other in sharers[1:]:
            union(first, other)

    # Metot çağrısı üzerinden birleştirme
    for method in methods:
        for target in called_methods(method, known):
            union(method.name, target)

    return len({find(name) for name in parent})


# --------------------------------------------------------------------------- #
# DCC — Direct Class Coupling
# --------------------------------------------------------------------------- #


def _annotations(node: ast.ClassDef) -> Iterator[ast.expr]:
    """Sınıf içindeki annotation ifadeleri: parametreler, dönüşler, `x: T`."""
    for child in ast.walk(node):
        if isinstance(child, ast.arg) and child.annotation is not None:
            yield child.annotation
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.returns:
            yield child.returns
        elif isinstance(child, ast.AnnAssign):
            yield child.annotation


def _subscript_name(node: ast.Subscript) -> str | None:
    """`Literal[...]`, `typing.Literal[...]`, `t.Annotated[...]` → son parça."""
    if isinstance(node.value, ast.Name):
        return node.value.id
    if isinstance(node.value, ast.Attribute):
        return node.value.attr
    return None


def _type_positions(annotation: ast.expr) -> Iterator[ast.AST]:
    """Annotation içinde **tip** yerindeki düğümler.

    İki yapı tip olmayan string taşır ve atlanır: `Literal["Order"]` bir
    değerdir, `Annotated[T, "meta"]` içinde yalnızca `T` tiptir.
    """
    stack: list[ast.AST] = [annotation]
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Subscript):
            name = _subscript_name(node)
            if name == "Literal":
                continue
            if name == "Annotated":
                inner = node.slice
                first = inner.elts[0] if isinstance(inner, ast.Tuple) and inner.elts else inner
                stack.append(first)
                continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _names_in_string_annotations(node: ast.ClassDef) -> set[str]:
    """İleri başvuru annotation'larındaki adlar (`"Order"`, `list["Order"]`).

    Yalnızca annotation konumundaki string'ler çözülür. Gövdedeki herhangi bir
    string'i ayrıştırmak `log("Order")` gibi metinleri sınıf referansı yapardı.
    Ayrıştırılamayan string sessizce atlanır — geçerli bir annotation değildir.
    """
    names: set[str] = set()
    for annotation in _annotations(node):
        for part in _type_positions(annotation):
            if not (isinstance(part, ast.Constant) and isinstance(part.value, str)):
                continue
            try:
                parsed = ast.parse(part.value.strip(), mode="eval")
            except SyntaxError:
                continue
            for inner in ast.walk(parsed):
                if isinstance(inner, ast.Name):
                    names.add(inner.id)
                elif isinstance(inner, ast.Attribute):
                    names.add(inner.attr)
    return names


def class_aliases(
    tree: ast.Module,
    project_classes: frozenset[str],
    is_project_module: Callable[[str], bool] | None = None,
) -> dict[str, str]:
    """Modülde proje sınıflarına verilen takma adlar: `{"O": "Order"}`.

    `from models import Order as O` sonrasında gövdede yalnızca `O` geçer;
    ad eşleşmesi onu göremez. Modülün her yerindeki importlar taranır —
    `if TYPE_CHECKING:` blokları ve fonksiyon içi importlar dahil.

    **Kaynak modül proje içi olmalıdır.** Takma ad çoğu zaman tam da bir ad
    çakışmasını önlemek için kullanılır: `from urllib3.exceptions import
    HTTPError as BaseHTTPError`, projede de bir `HTTPError` olduğu için
    yazılmıştır. Yalnızca ada bakmak bunu tersine çevirirdi. Göreli importlar
    her zaman proje içidir; mutlak importlar `is_project_module` onayı ister
    (bkz. `imports.project_module_predicate`). Onaylayan yoksa mutlak takma ad
    sayılmaz — doğrulanamayan referansı saymamak, yanlış saymaktan iyidir.

    `import models as m` burada yer almaz: `m.Order` nitelikli erişimi zaten
    son parçadan çözülür.
    """
    aliases: dict[str, str] = {}
    for child in ast.walk(tree):
        if not isinstance(child, ast.ImportFrom):
            continue
        if child.level == 0 and not (
            is_project_module is not None and child.module and is_project_module(child.module)
        ):
            continue
        for alias in child.names:
            if alias.asname and alias.asname != alias.name and alias.name in project_classes:
                aliases[alias.asname] = alias.name
    return aliases


def dcc(
    node: ast.ClassDef,
    project_classes: frozenset[str],
    aliases: Mapping[str, str] | None = None,
) -> int:
    """Sınıfın referans verdiği farklı proje-içi sınıf sayısı.

    Taban sınıflar, annotation'lar, atamalar ve çağrılar taranır. Standart
    kütüphane ve üçüncü parti sınıflar sayılmaz — ölçmek istediğimiz şey
    projenin kendi içindeki bağımlılık yoğunluğudur.

    **İsim çözümü en-iyi-çaba.** Python dinamik tipli olduğu için ad eşleşmesine
    dayanılır: gövdede geçen bir ad, projede tanımlı bir sınıf adıyla aynıysa
    referans sayılır. Bunun bilinen bedeli, bir sınıfla aynı adı taşıyan
    değişkenin yanlış sayılmasıdır. Bu sınırlılık README'de belgelenir.

    İki ek kaynak ad eşleşmesinin göremediği referansları kapatır: string
    annotation'lar ve modülün import takma adları (`aliases`, bkz.
    `class_aliases`).
    """
    referenced: set[str] = set()

    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            referenced.add(child.id)
        elif isinstance(child, ast.Attribute):
            # `models.Customer` gibi nitelikli erişimlerde son parça
            referenced.add(child.attr)

    referenced |= _names_in_string_annotations(node)

    if aliases:
        referenced |= {aliases[name] for name in referenced if name in aliases}

    referenced &= set(project_classes)
    referenced.discard(node.name)
    # Şema 3 (K3): kendi iç içe sınıfları aynı birimin parçasıdır, `self` gibi.
    referenced -= {
        child.name
        for child in ast.walk(node)
        if isinstance(child, ast.ClassDef) and child is not node
    }
    return len(referenced)


def collect_class_names(trees: list[ast.Module]) -> frozenset[str]:
    """Projede tanımlı tüm sınıf adları — DCC'nin sözlüğü.

    İç içe tanımlı sınıflar da dahildir; onlar da proje-içi bağımlılık
    oluşturabilir.
    """
    names: set[str] = set()
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                names.add(node.name)
    return frozenset(names)


# --------------------------------------------------------------------------- #
# CAM — Cohesion Among Methods (koşullu)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CamResult:
    value: float | None
    skipped_reason: str | None
    annotation_coverage: float


def _annotation_key(annotation: ast.expr) -> str:
    """Annotation'ı karşılaştırılabilir bir metne çevirir.

    `list[str]` ile `list[int]` farklı tiplerdir; `ast.unparse` bu ayrımı
    korur. Takma adlar (`Vector = list[float]`) çözülmez — en-iyi-çaba.
    """
    return ast.unparse(annotation)


def class_annotation_coverage(node: ast.ClassDef) -> float | None:
    """Raporlanan metotların bütün parametre yuvaları üzerinden annotation payı.

    CAM'in içeride hesapladığı kapsamın aynısı; tek fark yuvası olmayan
    sınıfta `None` dönmesi (CAM orada `0.0` taşır). Ön kayıt:
    `experiments/hardening/annotation-coverage.md`.
    """
    slots = [
        slot for method in class_methods(node) for slot in parameter_slots(method, is_method=True)
    ]
    if not slots:
        return None
    return round(sum(1 for slot in slots if slot.annotation is not None) / len(slots), 4)


def cam(node: ast.ClassDef, min_annotation_coverage: float = 0.7) -> CamResult:
    """Metotların parametre tiplerinin sınıf geneline oranlarının ortalaması.

    Klasik tanım **parametre tipleri** üzerinedir. Parametre *isimleri* bambaşka
    bir şey ölçer ve sonucu literatürle karşılaştırılamaz hale getirir; bu yüzden
    isim benzerliğine asla düşülmez.

    Python kod tabanlarının büyük kısmı annotation'sızdır. Böyle bir projede
    CAM'i yine de bir sayıya zorlamak, LLM'e kanıt diye gürültü vermek olurdu —
    bu da aracın ana tezini içeriden çürütürdü. Bu nedenle annotation kapsamı
    eşiğin altındaysa `None` döner ve nedeni raporlanır.

    Parametresiz metotlar ortalamaya katılmaz; tip çeşitliliği hakkında bilgi
    taşımazlar.
    """
    methods = class_methods(node)

    annotated = 0
    total_params = 0
    per_method_types: list[set[str]] = []

    for method in methods:
        receiver = self_parameter(method)
        arguments = method.args.posonlyargs + method.args.args + method.args.kwonlyargs
        if receiver in ("self", "cls") and arguments:
            arguments = arguments[1:]
        for extra in (method.args.vararg, method.args.kwarg):
            if extra is not None:
                arguments.append(extra)

        if not arguments:
            continue

        types = set()
        for argument in arguments:
            total_params += 1
            if argument.annotation is not None:
                annotated += 1
                types.add(_annotation_key(argument.annotation))
        per_method_types.append(types)

    if total_params == 0:
        return CamResult(None, CAM_NO_PARAMETERS, 0.0)

    coverage = annotated / total_params
    if annotated == 0:
        return CamResult(None, CAM_NO_PARAMETERS, 0.0)
    if coverage < min_annotation_coverage:
        return CamResult(None, CAM_INSUFFICIENT_ANNOTATIONS, round(coverage, 4))

    union: set[str] = set()
    for types in per_method_types:
        union |= types
    if not union:  # pragma: no cover - annotated > 0 ise union boş olamaz
        return CamResult(None, CAM_NO_PARAMETERS, round(coverage, 4))

    ratios = [len(types) / len(union) for types in per_method_types if types]
    return CamResult(round(sum(ratios) / len(ratios), 4), None, round(coverage, 4))


# --------------------------------------------------------------------------- #
# Toplama
# --------------------------------------------------------------------------- #


def measure_class(
    node: ast.ClassDef,
    *,
    module: str,
    project_classes: frozenset[str] = frozenset(),
    cam_min_annotation_coverage: float = 0.7,
    aliases: Mapping[str, str] | None = None,
    code_lines: frozenset[int],
) -> ClassReport:
    """Bir sınıfın tüm sınıf düzeyi metriklerini hesaplar.

    `aliases`, sınıfın bulunduğu modülün import takma adlarıdır
    (`class_aliases`); verilmezse DCC takma adları çözemez. `code_lines`,
    modülün `func_metrics.code_lines(source)` sonucudur (metotların LOC'u için).
    """
    loose_dam, strict_dam = dam(node)
    cam_result = cam(node, cam_min_annotation_coverage)

    return ClassReport(
        name=node.name,
        module=module,
        lineno=node.lineno,
        nom=nom(node),
        wmc=wmc(node),
        lcom4=lcom4(node),
        dam=loose_dam,
        dam_strict=strict_dam,
        dcc=dcc(node, project_classes, aliases),
        cam=cam_result.value,
        cam_skipped_reason=cam_result.skipped_reason,
        annotation_coverage=class_annotation_coverage(node),
        stub_methods=len(stub_method_names(node)),
        methods=[
            measure_function(method, code_lines=code_lines, is_method=True)
            for method in class_methods(node)
        ],
    )


def iter_module_classes(tree: ast.Module) -> list[ast.ClassDef]:
    """Modülün en üst düzeyindeki sınıflar."""
    return [node for node in tree.body if isinstance(node, ast.ClassDef)]
