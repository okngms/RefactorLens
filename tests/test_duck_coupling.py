"""v2.2 §3, K14: duck typing yapısal kuplajı (ön kayıt: `experiments/hardening/duck-coupling.md`).

Beklenen değerler kodu yazmadan önce elle hesaplandı.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from duck_coupling import class_members  # noqa: E402

from rlens.analysis.func_metrics import duck_coupling, duck_pairs  # noqa: E402

EVERYTHING = """
def f(order, customer, items, cfg, *args, **kwargs):
    total = order.total + order.tax
    order.status = "paid"
    customer.notify(order.id)
    for items in []:
        pass
    items.append(1)
    cfg = load()
    cfg.debug
    kwargs.get("x")
    args.count(1)
    names = [order for order in customer.orders]
    order.chain.deep

    def inner(order):
        return order.hidden

    return order.total
"""


def _fn(source: str):
    return ast.parse(source).body[0]


def _method(source: str):
    return ast.parse(source).body[0].body[0]


class TestPairs:
    def test_every_rule(self):
        # Sayılan çiftler:
        #   order.total, order.tax, order.status, order.id, order.chain
        #   customer.notify, customer.orders
        #   kwargs.get, args.count
        # Dışarıda: items (for hedefi), cfg (atama) — yeniden bağlanmış;
        # `order.chain.deep`'in yalnız ilk halkası; iç içe `inner`; kavrama
        # hedefi `order` kendi kapsamındadır, parametreyi yeniden bağlamaz ama
        # kavramanın içindeki `order` erişimi yoktur.
        pairs = duck_pairs(_fn(EVERYTHING))
        assert pairs == {
            ("order", "total"),
            ("order", "tax"),
            ("order", "status"),
            ("order", "id"),
            ("order", "chain"),
            ("customer", "notify"),
            ("customer", "orders"),
            ("kwargs", "get"),
            ("args", "count"),
        }
        assert duck_coupling(_fn(EVERYTHING)) == 9

    def test_receiver_is_not_a_parameter(self):
        method = _method("class A:\n    def m(self, other):\n        return self.x + other.x\n")
        assert duck_pairs(method, is_method=True) == {("other", "x")}

    def test_augmented_assignment_rebinds(self):
        assert duck_coupling(_fn("def f(n):\n    n += 1\n    return n.real\n")) == 0

    def test_walrus_and_with_rebind(self):
        source = "def f(a, b):\n    with open(a) as b:\n        b.read()\n    return a.upper()\n"
        assert duck_pairs(_fn(source)) == {("a", "upper")}

    def test_no_access_is_zero(self):
        assert duck_coupling(_fn("def h(a):\n    return a + 1\n")) == 0

    def test_no_slots_is_null(self):
        assert duck_coupling(_fn("def g():\n    return 1\n")) is None
        assert (
            duck_coupling(
                _method("class A:\n    def m(self):\n        return self.x\n"), is_method=True
            )
            is None
        )


class TestMembers:
    def test_attributes_and_methods_without_inheritance(self):
        source = """
class Order(Base):
    kind = "sale"

    def __init__(self):
        self.total = 0

    def pay(self):
        self.status = "paid"

    @property
    def label(self):
        return "x"
"""
        node = ast.parse(source).body[0]
        assert class_members(node) == {"kind", "total", "status", "pay", "label", "__init__"}


class TestHiddenRebinding:
    """Adı `ast.Name` olarak değil düz metin olarak saklayan bağlamalar."""

    def test_except_as_rebinds(self):
        source = "def f(e):\n    try:\n        pass\n    except ValueError as e:\n        e.args\n"
        assert duck_coupling(_fn(source)) == 0

    def test_import_as_rebinds(self):
        source = (
            "def f(json, mod):\n    import json\n    import x.y as mod\n"
            "    return json.dumps, mod.z\n"
        )
        assert duck_coupling(_fn(source)) == 0

    def test_match_capture_rebinds(self):
        source = (
            "def f(data, rest):\n"
            "    match data:\n"
            "        case {'k': 1, **rest}:\n"
            "            return rest.keys()\n"
            "        case [*data]:\n"
            "            return data.count(1)\n"
        )
        # `data` MatchStar, `rest` MatchMapping.rest ile yeniden bağlanıyor.
        assert duck_coupling(_fn(source)) == 0


# --------------------------------------------------------------------------- #
# Altın değerler — examples/messy_project (elle, alan rapora bağlanmadan önce)
# --------------------------------------------------------------------------- #


class TestGoldenMessyProject:
    """Fikstürde parametre üzerinden tek erişim `OrderManager.notify`'daki
    `customer.email`. `place_order` `customer`/`lines`'ı yalnız `isinstance`
    ve döngüde kullanır (`line` döngü değişkeni, parametre değil)."""

    def test_values(self):
        from rlens.analysis.scanner import scan_project
        from rlens.config import load_config

        project = REPO_ROOT / "examples" / "messy_project"
        report = scan_project(project, load_config(search_from=project))
        values = {}
        for module in report.modules:
            for function in module.functions:
                values[function.name] = function.duck_coupling
        for cls in report.iter_classes():
            for method in cls.methods:
                values[f"{cls.name}.{method.name}"] = method.duck_coupling
        assert values["OrderManager.notify"] == 1
        assert values["OrderManager.place_order"] == 0
        assert values["classify_order"] == 0
        assert values["OrderManager.order_count"] is None
        assert sum(v for v in values.values() if v) == 1
