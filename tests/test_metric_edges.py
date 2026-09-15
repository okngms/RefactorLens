"""Metrik uygulamalarının şüpheli noktaları (sertleştirme Blok 1, madde 3).

`test_func_metrics.py` ve `test_class_metrics.py` kuralları ve fikstür altın
değerlerini sınar. Bu dosya ise gerçek Python kodunda karşılaşılan ama
fikstürlerde hiç bulunmayan deyimleri sınar: dekoratörler, `@overload`,
`except*`, string annotation'lar, takma adlı importlar, iç içe sınıflar.

Her test iki türden biridir:

* **Düzeltilen hata.** Test önce kırmızıydı; uygulama `docs/04` tanımına
  çekildi. Docstring'de neyin yanlış sayıldığı yazılıdır.
* **Sabitlenen davranış.** Uygulama zaten doğruydu ya da bilinçli bir
  sınırlılıktır; test, ileride sessizce değişmesin diye vardır.

Bir test burada kırılırsa önce `docs/04 §2`'ye bakın: tanım mı değişti,
uygulama mı bozuldu?
"""

from __future__ import annotations

import ast
import textwrap

from rlens.analysis.class_metrics import (
    accessed_attributes,
    assigned_attributes,
    class_aliases,
    class_methods,
    dcc,
    lcom4,
    nom,
    wmc,
)
from rlens.analysis.func_metrics import (
    cyclomatic_complexity,
    function_loc,
    iter_module_functions,
    max_nesting,
)
from rlens.analysis.imports import project_module_predicate
from rlens.analysis.interface import public_interface
from rlens.analysis.scanner import scan_project
from rlens.config import load_config


def parse(source: str) -> ast.Module:
    return ast.parse(textwrap.dedent(source).strip())


def first(source: str):
    return parse(source).body[0]


def only_class(source: str) -> ast.ClassDef:
    tree = parse(source)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    assert len(classes) == 1
    return classes[0]


# --------------------------------------------------------------------------- #
# CC
# --------------------------------------------------------------------------- #


class TestComplexityEdges:
    def test_decorator_expression_is_not_a_decision(self):
        """Düzeltilen hata: dekoratör ifadesindeki `or` fonksiyona yazılıyordu.

        Dekoratör tanım anında bir kez değerlendirilir; fonksiyonun yürütme
        yollarından biri değildir. radon da yalnızca gövdeyi gezer.
        """
        node = first(
            """
            @register(name or "default", strict=a if b else c)
            def handler():
                return 1
            """
        )
        assert cyclomatic_complexity(node) == 1

    def test_default_argument_is_not_a_decision(self):
        """Düzeltilen hata: varsayılan değerler tanım anında hesaplanır."""
        node = first(
            """
            def f(x=a or b, y=[i for i in range(3) if i]):
                return x
            """
        )
        assert cyclomatic_complexity(node) == 1

    def test_return_annotation_is_not_a_decision(self):
        node = first(
            """
            def f(x: int | None = None) -> (A if TYPE_CHECKING else B):
                return x
            """
        )
        assert cyclomatic_complexity(node) == 1

    def test_decorated_body_still_counts(self):
        node = first(
            """
            @app.command()
            def run(flag):
                if flag:
                    return 1
                return 0
            """
        )
        assert cyclomatic_complexity(node) == 2

    def test_match_counts_every_case_including_wildcard(self):
        """Sabitlenen davranış: `04 §2.3` her `case`'i sayar.

        radon joker `case _:`'i düşer; bu bir tanım farkıdır, hata değil
        (`experiments/hardening/metric-accuracy.md`, `match_wildcard`).
        """
        node = first(
            """
            def f(command):
                match command:
                    case "start":
                        return 1
                    case "stop" | "halt":
                        return 2
                    case _:
                        return 0
            """
        )
        assert cyclomatic_complexity(node) == 4

    def test_match_guard_boolop_counts_but_guard_itself_does_not(self):
        node = first(
            """
            def f(point):
                match point:
                    case (x, y) if x and y:
                        return 1
            """
        )
        # 1 + case + `and`
        assert cyclomatic_complexity(node) == 3

    def test_async_for_counts_async_with_does_not(self):
        node = first(
            """
            async def f(stream, lock):
                async with lock:
                    async for item in stream:
                        yield item
            """
        )
        assert cyclomatic_complexity(node) == 2

    def test_nested_comprehension_counts_every_generator_and_condition(self):
        node = first(
            """
            def f(rows):
                return [[c for c in row if c] for row in rows if row]
            """
        )
        # 1 + (dış for + if) + (iç for + if)
        assert cyclomatic_complexity(node) == 5

    def test_try_finally_adds_nothing(self):
        node = first(
            """
            def f():
                try:
                    work()
                finally:
                    cleanup()
            """
        )
        assert cyclomatic_complexity(node) == 1

    def test_try_else_and_loop_else_add_nothing(self):
        """Sabitlenen davranış: `else` dal açmaz (`04 §2.3`). radon +1 sayar."""
        node = first(
            """
            def f(items):
                for item in items:
                    pass
                else:
                    done()
                try:
                    work()
                except ValueError:
                    pass
                else:
                    ok()
            """
        )
        # 1 + for + except
        assert cyclomatic_complexity(node) == 3

    def test_except_star_handlers_count(self):
        node = first(
            """
            def f():
                try:
                    work()
                except* ValueError:
                    pass
                except* TypeError:
                    pass
            """
        )
        assert cyclomatic_complexity(node) == 3

    def test_lambda_body_counts_toward_enclosing_function(self):
        """Sabitlenen davranış: lambda ayrı bir fonksiyon olarak ölçülmez.

        `04 §2.3`'ün "iç içe fonksiyon girilmez" kuralı `def` içindir; lambda
        rapor edilmediği için içeriği kaybolmasın diye dıştakine yazılır.
        radon da aynı şekilde sayar.
        """
        node = first(
            """
            def f(items):
                return sorted(items, key=lambda x: x.a if x else 0)
            """
        )
        assert cyclomatic_complexity(node) == 2

    def test_assert_adds_nothing(self):
        node = first(
            """
            def f(x):
                assert x
                return x
            """
        )
        assert cyclomatic_complexity(node) == 1


class TestNestingEdges:
    def test_except_star_body_is_nested(self):
        """Düzeltilen hata: `TryStar` iç içelik düğümü sayılmıyordu.

        Gövdesine inilmediği için `except*` altındaki bloklar görünmezdi.
        """
        node = first(
            """
            def f():
                try:
                    work()
                except* ValueError:
                    if retry:
                        for _ in range(3):
                            work()
            """
        )
        assert max_nesting(node) == 3

    def test_match_case_body_is_nested(self):
        node = first(
            """
            def f(x):
                match x:
                    case 1:
                        if y:
                            pass
            """
        )
        assert max_nesting(node) == 2


class TestLocDefinitionMismatch:
    def test_loc_counts_blank_lines_and_comments(self):
        """Sabitlenen davranış — **açık karar.**

        `docs/04 §2.3` LOC'u "gövde satır sayısı (boş/yorum hariç)" diye
        tanımlar; uygulama `def` satırından son satıra kadar boş ve yorum
        dahil sayar. FINDINGS-1/2'nin LOC verisi uygulamanın tanımıyla
        toplandı. Hangisinin düzeltileceği bir tanım kararıdır ve
        `schema_version` gerektirir; bkz. `docs/STATUS.md`.
        """
        node = first(
            """
            def f():
                # yorum

                return 1
            """
        )
        assert function_loc(node) == 4


# --------------------------------------------------------------------------- #
# NOM / WMC
# --------------------------------------------------------------------------- #


class TestMethodSetEdges:
    def test_overload_stubs_are_not_methods(self):
        """Düzeltilen hata: `@overload` taslakları ayrı metot sayılıyordu.

        Taslaklar çalışma zamanında son tanımla ezilir; yalnızca tip
        beyanıdır. Üç taslaklı bir metot NOM'u 3 artırıyordu.
        """
        node = only_class(
            """
            class Parser:
                @overload
                def parse(self, data: str) -> str: ...
                @typing.overload
                def parse(self, data: bytes) -> bytes: ...
                def parse(self, data):
                    if isinstance(data, str):
                        return data
                    return data
            """
        )
        assert nom(node) == 1
        assert wmc(node) == 2

    def test_overload_stubs_are_not_module_functions(self):
        tree = parse(
            """
            @overload
            def load(x: int) -> int: ...
            @overload
            def load(x: str) -> str: ...
            def load(x):
                return x
            """
        )
        assert len(iter_module_functions(tree)) == 1

    def test_static_and_class_methods_count_once(self):
        node = only_class(
            """
            class Factory:
                @staticmethod
                def make():
                    return 1
                @classmethod
                def build(cls):
                    return cls()
            """
        )
        assert nom(node) == 2
        assert wmc(node) == 2

    def test_property_getter_and_setter_are_two_methods(self):
        """Sabitlenen davranış: getter ve setter ayrı gövdelerdir, ikisi de sayılır."""
        node = only_class(
            """
            class Box:
                @property
                def size(self):
                    return self._size
                @size.setter
                def size(self, value):
                    if value < 0:
                        raise ValueError
                    self._size = value
            """
        )
        assert nom(node) == 2
        assert wmc(node) == 3

    def test_protocol_and_abc_methods_count(self):
        """Sabitlenen davranış: soyut metot bir metottur, gövdesi `...` olsa da."""
        node = only_class(
            """
            class Store(Protocol):
                def get(self, key: str) -> bytes: ...
                def put(self, key: str, value: bytes) -> None: ...
            """
        )
        assert nom(node) == 2
        assert wmc(node) == 2

    def test_post_init_is_a_dunder_and_excluded(self):
        node = only_class(
            """
            @dataclass
            class Point:
                x: int
                def __post_init__(self):
                    if self.x < 0:
                        raise ValueError
            """
        )
        assert nom(node) == 0
        assert wmc(node) == 0


# --------------------------------------------------------------------------- #
# LCOM4
# --------------------------------------------------------------------------- #


class TestCohesionEdges:
    def test_staticmethod_first_parameter_is_not_a_receiver(self):
        """Düzeltilen hata: `@staticmethod`'un ilk parametresi `self` sanılıyordu.

        `def from_row(row): return row.name` içindeki `row.name`, sınıfın
        `name` attribute'u sayılıp metodu `self.name` kullanan kardeşiyle
        birleştiriyordu; LCOM4 olduğundan düşük çıkıyordu.
        """
        node = only_class(
            """
            class User:
                def display(self):
                    return self.name
                @staticmethod
                def from_row(row):
                    return row.name
            """
        )
        assert lcom4(node) == 2
        methods = {m.name: m for m in class_methods(node)}
        assert accessed_attributes(methods["from_row"], {"display", "from_row"}) == set()

    def test_classmethod_cls_is_a_receiver(self):
        node = only_class(
            """
            class Registry:
                items = []
                @classmethod
                def add(cls, item):
                    cls.items.append(item)
                def count(self):
                    return len(self.items)
            """
        )
        assert lcom4(node) == 1

    def test_property_access_links_methods(self):
        node = only_class(
            """
            class Order:
                @property
                def total(self):
                    return self._total
                def report(self):
                    return f"{self.total}"
            """
        )
        assert lcom4(node) == 1

    def test_nested_class_self_does_not_leak_into_outer_method(self):
        """Düzeltilen hata: iç içe sınıfın `self`'i dıştaki metoda yazılıyordu."""
        node = only_class(
            """
            class Outer:
                def a(self):
                    class Helper:
                        def run(self):
                            return self.shared
                    return Helper
                def b(self):
                    return self.shared
            """
        )
        assert lcom4(node) == 2
        assert "shared" not in accessed_attributes(class_methods(node)[0], {"a", "b"})

    def test_nested_function_shadowing_self_does_not_leak(self):
        node = only_class(
            """
            class Outer:
                def a(self):
                    def patched(self):
                        self.flag = True
                    return patched
                def b(self):
                    return self.flag
            """
        )
        assert lcom4(node) == 2
        assert "flag" not in assigned_attributes(node)

    def test_closure_capturing_self_still_counts(self):
        node = only_class(
            """
            class Outer:
                def a(self):
                    def inner():
                        return self.shared
                    return inner
                def b(self):
                    return self.shared
            """
        )
        assert lcom4(node) == 1

    def test_dataclass_fields_are_attributes(self):
        node = only_class(
            """
            @dataclass
            class Point:
                x: int
                y: int = 0
                def norm(self):
                    return self.x
            """
        )
        assert assigned_attributes(node) == {"x", "y"}
        assert lcom4(node) == 1

    def test_namedtuple_and_typeddict_fields_are_attributes(self):
        for base in ("NamedTuple", "TypedDict"):
            node = only_class(
                f"""
                class Row({base}):
                    id: int
                    name: str
                """
            )
            assert assigned_attributes(node) == {"id", "name"}

    def test_enum_members_are_attributes(self):
        node = only_class(
            """
            class Color(Enum):
                RED = 1
                GREEN = 2
            """
        )
        assert assigned_attributes(node) == {"RED", "GREEN"}

    def test_slots_are_attributes(self):
        node = only_class(
            """
            class Vec:
                __slots__ = ("x", "y")
                def dot(self, other):
                    return self.x * other.x
            """
        )
        assert assigned_attributes(node) == {"x", "y"}

    def test_class_without_methods_is_zero_not_null(self):
        """Sabitlenen davranış — **açık karar.**

        `docs/04 §2.2` metotsuz sınıfta LCOM4'ü `null` tanımlar; uygulama 0
        döndürür ve bunun gerekçesi `lcom4` docstring'inde yazılıdır. İkisi
        çelişiyor. Çözüm bir tanım kararıdır (`schema_version`, koku
        eşikleri `None` karşılaştırması); bkz. `docs/STATUS.md`.
        """
        node = only_class(
            """
            class Empty:
                x = 1
            """
        )
        assert lcom4(node) == 0


# --------------------------------------------------------------------------- #
# DCC
# --------------------------------------------------------------------------- #

PROJECT = frozenset({"Order", "Customer", "Invoice", "HTTPError"})
IS_PROJECT_MODULE = project_module_predicate(("models", "billing", "exceptions"))


class TestCouplingEdges:
    def test_string_annotation_counts(self):
        """Düzeltilen hata: ileri başvuru annotation'ları görünmüyordu.

        `TYPE_CHECKING` altında import edilen sınıf yalnızca string olarak
        kullanılabilir; bu kodda tek referans budur.
        """
        node = only_class(
            """
            class Service:
                def place(self, order: "Order") -> "Invoice":
                    return make(order)
            """
        )
        assert dcc(node, PROJECT) == 2

    def test_string_inside_generic_annotation_counts(self):
        node = only_class(
            """
            class Service:
                items: list["Order"]
                def owners(self) -> dict[str, "models.Customer"]:
                    return {}
            """
        )
        assert dcc(node, PROJECT) == 2

    def test_plain_string_value_is_not_a_reference(self):
        """Log mesajı ya da sözlük anahtarı sınıf adıyla aynı olabilir; sayılmaz."""
        node = only_class(
            """
            class Service:
                def run(self):
                    log("Order")
                    return {"Customer": 1}
            """
        )
        assert dcc(node, PROJECT) == 0

    def test_literal_values_and_annotated_metadata_are_not_references(self):
        """`Literal["Order"]` bir değerdir; `Annotated`'ta yalnızca ilk argüman tiptir."""
        node = only_class(
            """
            class Service:
                kind: Literal["Order", "Invoice"]
                note: typing.Annotated["Customer", "Order"]
                def run(self, x: t.Literal["Customer"]) -> None:
                    return None
            """
        )
        assert dcc(node, PROJECT) == 1

    def test_unparseable_string_annotation_is_ignored(self):
        node = only_class(
            """
            class Service:
                def run(self, x: "not valid python ((") -> None:
                    return None
            """
        )
        assert dcc(node, PROJECT) == 0

    def test_import_alias_counts(self):
        """Düzeltilen hata: `from models import Order as O` ile kullanılan sınıf kaçıyordu."""
        tree = parse(
            """
            from models import Order as O
            from billing import Invoice as Bill

            class Service:
                def run(self) -> Bill:
                    return O()
            """
        )
        node = [n for n in tree.body if isinstance(n, ast.ClassDef)][0]
        aliases = class_aliases(tree, PROJECT, IS_PROJECT_MODULE)
        assert aliases == {"O": "Order", "Bill": "Invoice"}
        assert dcc(node, PROJECT) == 0
        assert dcc(node, PROJECT, aliases) == 2

    def test_alias_of_non_project_class_is_ignored(self):
        tree = parse(
            """
            from collections import OrderedDict as Order2
            import json as Customer_json
            """
        )
        assert class_aliases(tree, PROJECT, IS_PROJECT_MODULE) == {}

    def test_alias_from_third_party_module_with_colliding_name_is_ignored(self):
        """Referans setinde bulunan yanlış pozitif (`requests.exceptions`).

        `from urllib3.exceptions import HTTPError as BaseHTTPError`: kod
        takma adı tam da projedeki `HTTPError` ile çakışmayı önlemek için
        kullanır. Yalnızca ada bakan bir kural bunu tersine çevirip urllib3
        sınıfını proje sınıfı sayar. Kaynak modül proje modülü olmalıdır.
        """
        tree = parse(
            """
            from urllib3.exceptions import HTTPError as BaseHTTPError
            from .exceptions import HTTPError as RequestsHTTPError
            """
        )
        assert class_aliases(tree, PROJECT, IS_PROJECT_MODULE) == {"RequestsHTTPError": "HTTPError"}

    def test_absolute_alias_without_resolver_is_not_trusted(self):
        """Kaynağı doğrulanamayan mutlak takma ad sayılmaz; göreli olan sayılır."""
        tree = parse(
            """
            from models import Order as O
            from .billing import Invoice as Bill
            """
        )
        assert class_aliases(tree, PROJECT) == {"Bill": "Invoice"}

    def test_relative_and_module_imports_count(self):
        tree = parse(
            """
            from . import models
            from .billing import Invoice

            class Service:
                def run(self):
                    return models.Customer(), Invoice()
            """
        )
        node = [n for n in tree.body if isinstance(n, ast.ClassDef)][0]
        assert dcc(node, PROJECT, class_aliases(tree, PROJECT, IS_PROJECT_MODULE)) == 2

    def test_type_checking_import_with_string_annotation(self):
        tree = parse(
            """
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                from models import Order as _Order

            class Service:
                def run(self, order: "_Order") -> None:
                    return None
            """
        )
        node = [n for n in tree.body if isinstance(n, ast.ClassDef)][0]
        assert dcc(node, PROJECT, class_aliases(tree, PROJECT, IS_PROJECT_MODULE)) == 1

    def test_scan_resolves_aliases_across_modules(self, tmp_path):
        """Takma ad çözümü tarama akışına bağlı: birim testte değil raporda görünmeli."""
        (tmp_path / "models.py").write_text("class Order:\n    pass\n")
        (tmp_path / "service.py").write_text(
            "from models import Order as O\n\n"
            "class Service:\n"
            "    def run(self):\n"
            "        return O()\n"
        )
        (tmp_path / "exceptions.py").write_text("class HTTPError(Exception):\n    pass\n")
        (tmp_path / "adapter.py").write_text(
            "from urllib3.exceptions import HTTPError as BaseHTTPError\n\n"
            "class Adapter:\n"
            "    def run(self):\n"
            "        raise BaseHTTPError()\n"
        )
        report = scan_project(tmp_path, load_config(search_from=tmp_path), no_arch=True)
        service = next(m for m in report.modules if m.module == "service")
        adapter = next(m for m in report.modules if m.module == "adapter")
        assert service.classes[0].dcc == 1
        assert adapter.classes[0].dcc == 0

    def test_parameter_name_colliding_with_class_is_a_false_positive(self):
        """Sabitlenen sınırlılık: isim tabanlı çözüm, sınıf adıyla aynı yerel adı sayar.

        Parametre tanımı (`ast.arg`) sayılmaz; ama o ad gövdede kullanıldığında
        sınıf referansından ayırt edilemez. `04 §2.2` bunu `resolution:
        inferred` olarak belgeler.
        """
        node = only_class(
            """
            class Service:
                def run(self, Order):
                    return Order
            """
        )
        assert dcc(node, PROJECT) == 1


# --------------------------------------------------------------------------- #
# Public interface
# --------------------------------------------------------------------------- #


class TestInterfaceEdges:
    def test_property_setter_is_one_public_name(self):
        """Düzeltilen hata: getter/setter aynı adı iki kez listeliyordu.

        `accessor_ratio`'nun paydası şişiyor, erişimci oranı düşük çıkıyordu.
        """
        node = only_class(
            """
            class Box:
                @property
                def size(self):
                    return self._size
                @size.setter
                def size(self, value):
                    self._size = value
            """
        )
        interface = public_interface(node)
        assert interface.methods == ("size",)
        assert interface.accessors == ("size",)
        assert interface.accessor_ratio == 1.0

    def test_overload_stubs_are_listed_once(self):
        node = only_class(
            """
            class Parser:
                @overload
                def parse(self, data: str) -> str: ...
                def parse(self, data):
                    return data
            """
        )
        assert public_interface(node).methods == ("parse",)

    def test_slots_are_public_attributes(self):
        node = only_class(
            """
            class Vec:
                __slots__ = ("x", "_y")
            """
        )
        assert public_interface(node).attributes == ("x",)

    def test_class_and_instance_attributes_are_both_listed(self):
        node = only_class(
            """
            class Config:
                debug = False
                def load(self):
                    self.path = "x"
            """
        )
        assert public_interface(node).attributes == ("debug", "path")

    def test_nested_class_attributes_are_not_outer_interface(self):
        """Düzeltilen hata: iç içe sınıfın `self.x = ...` atamaları dıştakine yazılıyordu."""
        node = only_class(
            """
            class Outer:
                class Meta:
                    def __init__(self):
                        self.ordering = []
                def run(self):
                    self.result = 1
            """
        )
        assert public_interface(node).attributes == ("result",)
