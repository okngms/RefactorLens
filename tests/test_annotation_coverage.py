"""v2.2 §3: anotasyon kapsamı (ön kayıt: `experiments/hardening/annotation-coverage.md`).

Beklenen değerler kodu yazmadan önce elle hesaplandı. Sabitlenenler:

* Yuvalar `param_count` ile aynı: alıcı sayılmaz, `*args`/`**kwargs` sayılır.
* Yuvası olmayan fonksiyonda ve sınıfta değer `null`, asla `0`.
* Sınıf değeri CAM'in iç kapsamıyla aynı (ön kayıt 9c).
"""

import ast
from pathlib import Path

import pytest

from rlens.analysis.class_metrics import cam, class_annotation_coverage
from rlens.analysis.func_metrics import annotation_coverage, param_count, returns_annotated


def _fn(source: str):
    return ast.parse(source).body[0]


def _method(source: str):
    """Bir sınıfın ilk metodu (dekoratörleri korunur)."""
    return ast.parse(source).body[0].body[0]


def _class(source: str) -> ast.ClassDef:
    return ast.parse(source).body[0]


class TestFunction:
    def test_every_slot_kind(self):
        # a, b, *args, c, **kw = 5 yuva; annotation'lı a, args, c = 3 → 0.6
        node = _fn("def f(a: int, b, *args: str, c: int = 1, **kw): pass")
        assert param_count(node) == 5
        assert annotation_coverage(node) == 0.6

    def test_receiver_is_not_a_slot(self):
        node = _method("class A:\n    def m(self, x: int, y): pass\n")
        assert annotation_coverage(node, is_method=True) == 0.5

    def test_staticmethod_first_parameter_is_a_slot(self):
        node = _method("class A:\n    @staticmethod\n    def s(a: int, b: int): pass\n")
        assert annotation_coverage(node, is_method=True) == 1.0

    def test_string_and_any_count(self):
        node = _fn("def f(a: 'Order', b: Any): pass")
        assert annotation_coverage(node) == 1.0

    @pytest.mark.parametrize(
        "source, is_method",
        [("def g(): pass", False), ("class A:\n    def h(self): pass\n", True)],
    )
    def test_no_slots_is_null(self, source, is_method):
        node = _method(source) if is_method else _fn(source)
        assert annotation_coverage(node, is_method=is_method) is None

    def test_returns(self):
        assert returns_annotated(_fn("def r() -> None: pass")) is True
        assert returns_annotated(_fn("def r(): pass")) is False


CLASS = """
class Service:
    def __init__(self, z):
        self.z = z

    def m(self, x: int, y):
        return x

    @staticmethod
    def s(a: int, b: int):
        return a + b
"""


class TestClass:
    def test_pooled_over_reported_methods_dunders_excluded(self):
        # m: x, y; s: a, b → 4 yuva, 3 annotation'lı → 0.75. `__init__` dunder, sayılmaz.
        assert class_annotation_coverage(_class(CLASS)) == 0.75

    def test_equals_cams_internal_coverage(self):
        node = _class(CLASS)
        assert class_annotation_coverage(node) == cam(node).annotation_coverage

    def test_no_slots_is_null_where_cam_says_zero(self):
        node = _class("class P:\n    def f(self):\n        return 1\n")
        assert class_annotation_coverage(node) is None
        assert cam(node).annotation_coverage == 0.0


# --------------------------------------------------------------------------- #
# Altın değerler — examples/messy_project (elle, alanlar rapora bağlanmadan önce)
# --------------------------------------------------------------------------- #

MESSY_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "messy_project"

#: Sınıf → beklenen kapsam. `__init__` dunder'dır, sayılmaz.
#: OrderManager: hiç annotation yok. Customer: name, tier, note. Product: dört
#: `quantity`. OrderLine: extra. ReportBuilder: text (annotation'lı), title,
#: width. Order ve Invoice: `__init__` dışında yuva yok. EmailNotifier:
#: address, subject. ShippingCalculator: weight, express.
GOLD_CLASSES = {
    "OrderManager": 0.0,
    "Customer": 1.0,
    "Product": 1.0,
    "OrderLine": 1.0,
    "ReportBuilder": 0.3333,
    "Order": None,
    "Invoice": None,
    "EmailNotifier": 1.0,
    "ShippingCalculator": 1.0,
}


@pytest.fixture(scope="module")
def messy_report():
    from rlens.analysis.scanner import scan_project
    from rlens.config import load_config

    return scan_project(MESSY_PROJECT, load_config(search_from=MESSY_PROJECT))


class TestGoldenMessyProject:
    @pytest.mark.parametrize("name, expected", GOLD_CLASSES.items())
    def test_class_coverage(self, messy_report, name, expected):
        cls = next(c for c in messy_report.iter_classes() if c.name == name)
        assert cls.annotation_coverage == expected

    def test_module_function(self, messy_report):
        utils = next(m for m in messy_report.modules if m.module == "utils")
        classify = next(f for f in utils.functions if f.name == "classify_order")
        assert classify.annotation_coverage == 0.0
        assert classify.returns_annotated is False

    def test_method(self, messy_report):
        customer = next(c for c in messy_report.iter_classes() if c.name == "Customer")
        rename = next(m for m in customer.methods if m.name == "rename")
        assert rename.annotation_coverage == 1.0
        assert rename.returns_annotated is True
        is_premium = next(m for m in customer.methods if m.name == "is_premium")
        assert is_premium.annotation_coverage is None
