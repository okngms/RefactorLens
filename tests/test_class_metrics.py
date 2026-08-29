"""Sınıf metrikleri testleri.

Altın değerler `examples/messy_project` üzerinde **elle hesaplanmış**, sonra
koda bakılmıştır. Ters sırada yapılsaydı test, kodun hatasını da birlikte
onaylardı.
"""

import ast
from pathlib import Path

import pytest

from rlens.analysis.class_metrics import (
    CAM_INSUFFICIENT_ANNOTATIONS,
    CAM_NO_PARAMETERS,
    accessed_attributes,
    assigned_attributes,
    cam,
    class_methods,
    collect_class_names,
    dam,
    dcc,
    iter_module_classes,
    lcom4,
    measure_class,
    nom,
    wmc,
)

MESSY_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "messy_project"


def parse_class(source: str) -> ast.ClassDef:
    return ast.parse(source.strip()).body[0]


# --------------------------------------------------------------------------- #
# Metot kümesi
# --------------------------------------------------------------------------- #


class TestMethodSet:
    def test_dunder_methods_are_excluded(self):
        node = parse_class(
            "class C:\n"
            "    def __init__(self):\n        pass\n"
            "    def __repr__(self):\n        return ''\n"
            "    def work(self):\n        pass\n"
        )
        assert [m.name for m in class_methods(node)] == ["work"]

    def test_decorated_methods_are_included(self):
        node = parse_class(
            "class C:\n"
            "    @property\n    def a(self):\n        return 1\n"
            "    @staticmethod\n    def b():\n        return 2\n"
            "    @classmethod\n    def c(cls):\n        return 3\n"
        )
        assert nom(node) == 3

    def test_nested_function_is_not_a_method(self):
        node = parse_class(
            "class C:\n"
            "    def outer(self):\n"
            "        def inner():\n            pass\n"
            "        return inner\n"
        )
        assert nom(node) == 1

    def test_nested_class_methods_do_not_count(self):
        node = parse_class(
            "class Outer:\n"
            "    class Inner:\n"
            "        def a(self):\n            pass\n"
            "        def b(self):\n            pass\n"
            "    def only(self):\n        pass\n"
        )
        assert nom(node) == 1

    def test_empty_class(self):
        assert nom(parse_class("class C:\n    pass")) == 0


# --------------------------------------------------------------------------- #
# WMC
# --------------------------------------------------------------------------- #


class TestWmc:
    def test_sums_method_complexity(self):
        node = parse_class(
            "class C:\n"
            "    def a(self, x):\n        if x:\n            return 1\n        return 2\n"
            "    def b(self):\n        return 3\n"
        )
        # a: 1 + 1 (if) = 2, b: 1  →  3
        assert wmc(node) == 3

    def test_init_is_excluded(self):
        node = parse_class(
            "class C:\n"
            "    def __init__(self, x):\n        if x:\n            self.x = x\n"
            "    def a(self):\n        return 1\n"
        )
        assert wmc(node) == 1

    def test_empty_class_is_zero(self):
        assert wmc(parse_class("class C:\n    pass")) == 0


# --------------------------------------------------------------------------- #
# Attribute toplama
# --------------------------------------------------------------------------- #


class TestAssignedAttributes:
    def test_class_level_assignment(self):
        assert assigned_attributes(parse_class("class C:\n    x = 5")) == {"x"}

    def test_class_level_annotation(self):
        assert assigned_attributes(parse_class("class C:\n    x: int")) == {"x"}

    def test_init_assignments(self):
        node = parse_class("class C:\n    def __init__(self):\n        self.a = 1")
        assert assigned_attributes(node) == {"a"}

    def test_assignments_in_any_method(self):
        """Attribute yalnızca __init__'te doğmaz."""
        node = parse_class(
            "class C:\n"
            "    def __init__(self):\n        self.a = 1\n"
            "    def later(self):\n        self.b = 2\n"
        )
        assert assigned_attributes(node) == {"a", "b"}

    def test_augmented_assignment_counts(self):
        node = parse_class("class C:\n    def m(self):\n        self.count += 1")
        assert assigned_attributes(node) == {"count"}

    def test_tuple_unpacking_counts(self):
        node = parse_class("class C:\n    def m(self):\n        self.a, self.b = 1, 2")
        assert assigned_attributes(node) == {"a", "b"}

    def test_read_only_access_is_not_an_attribute(self):
        node = parse_class("class C:\n    def m(self):\n        return self.external")
        assert assigned_attributes(node) == set()

    def test_slots_are_attributes(self):
        node = parse_class("class C:\n    __slots__ = ('a', 'b')")
        assert assigned_attributes(node) == {"a", "b"}

    def test_dunder_names_are_excluded(self):
        node = parse_class("class C:\n    __slots__ = ('a',)")
        assert "__slots__" not in assigned_attributes(node)


# --------------------------------------------------------------------------- #
# DAM
# --------------------------------------------------------------------------- #


class TestDam:
    def test_all_public(self):
        node = parse_class(
            "class C:\n    def __init__(self):\n        self.a = 1\n        self.b = 2"
        )
        assert dam(node) == (0.0, 0.0)

    def test_all_private(self):
        node = parse_class(
            "class C:\n    def __init__(self):\n        self._a = 1\n        self._b = 2"
        )
        assert dam(node) == (1.0, 0.0)

    def test_mixed(self):
        node = parse_class(
            "class C:\n    def __init__(self):\n        self.a = 1\n        self._b = 2"
        )
        assert dam(node) == (0.5, 0.0)

    def test_strict_counts_only_name_mangled(self):
        node = parse_class(
            "class C:\n    def __init__(self):\n        self.__a = 1\n        self._b = 2"
        )
        loose, strict = dam(node)
        assert loose == 1.0
        assert strict == 0.5

    def test_no_attributes_returns_none(self):
        """Bölme yapılamaz; sıfır da yanıltıcı olurdu."""
        assert dam(parse_class("class C:\n    def m(self):\n        return 1")) == (None, None)


# --------------------------------------------------------------------------- #
# LCOM4
# --------------------------------------------------------------------------- #


class TestLcom4:
    def test_cohesive_class_is_one(self):
        node = parse_class(
            "class C:\n"
            "    def __init__(self):\n        self.x = 0\n"
            "    def a(self):\n        return self.x\n"
            "    def b(self):\n        self.x += 1\n"
        )
        assert lcom4(node) == 1

    def test_two_disjoint_groups(self):
        node = parse_class(
            "class C:\n"
            "    def __init__(self):\n        self.x = 0\n        self.y = 0\n"
            "    def a(self):\n        return self.x\n"
            "    def b(self):\n        self.x += 1\n"
            "    def c(self):\n        return self.y\n"
            "    def d(self):\n        self.y += 1\n"
        )
        assert lcom4(node) == 2

    def test_method_call_bridges_groups(self):
        """Bir metot diğerini çağırıyorsa aynı bileşendedir."""
        node = parse_class(
            "class C:\n"
            "    def __init__(self):\n        self.x = 0\n        self.y = 0\n"
            "    def a(self):\n        return self.x\n"
            "    def b(self):\n        return self.y + self.a()\n"
        )
        assert lcom4(node) == 1

    def test_method_reference_without_call_also_bridges(self):
        node = parse_class(
            "class C:\n"
            "    def __init__(self):\n        self.x = 0\n        self.y = 0\n"
            "    def a(self):\n        return self.x\n"
            "    def b(self):\n        handler = self.a\n        return self.y\n"
        )
        assert lcom4(node) == 1

    def test_method_touching_nothing_is_its_own_component(self):
        node = parse_class(
            "class C:\n"
            "    def __init__(self):\n        self.x = 0\n"
            "    def a(self):\n        return self.x\n"
            "    def lonely(self):\n        return 42\n"
        )
        assert lcom4(node) == 2

    def test_init_does_not_merge_components(self):
        """Kurucu tüm attribute'lara dokunur; sayılsaydı LCOM4 hep 1 olurdu."""
        node = parse_class(
            "class C:\n"
            "    def __init__(self):\n        self.x = 0\n        self.y = 0\n"
            "    def a(self):\n        return self.x\n"
            "    def b(self):\n        return self.y\n"
        )
        assert lcom4(node) == 2

    def test_class_without_methods_is_zero(self):
        assert lcom4(parse_class("class C:\n    x: int = 1")) == 0


# --------------------------------------------------------------------------- #
# DCC
# --------------------------------------------------------------------------- #


class TestDcc:
    def test_counts_project_classes_only(self):
        node = parse_class(
            "class C:\n"
            "    def m(self):\n"
            "        a = Widget()\n"
            "        b = datetime.now()\n"
            "        return a, b\n"
        )
        assert dcc(node, frozenset({"Widget", "C"})) == 1

    def test_base_class_counts(self):
        node = parse_class("class C(Base):\n    pass")
        assert dcc(node, frozenset({"Base"})) == 1

    def test_annotation_counts(self):
        node = parse_class("class C:\n    def m(self, x: Widget) -> Gadget:\n        return x")
        assert dcc(node, frozenset({"Widget", "Gadget"})) == 2

    def test_self_reference_is_not_counted(self):
        node = parse_class("class C:\n    def clone(self):\n        return C()")
        assert dcc(node, frozenset({"C"})) == 0

    def test_repeated_reference_counts_once(self):
        node = parse_class(
            "class C:\n    def m(self):\n        return Widget(), Widget(), Widget()"
        )
        assert dcc(node, frozenset({"Widget"})) == 1

    def test_qualified_attribute_reference_counts(self):
        node = parse_class("class C:\n    def m(self):\n        return models.Widget()")
        assert dcc(node, frozenset({"Widget"})) == 1

    def test_empty_registry_gives_zero(self):
        node = parse_class("class C:\n    def m(self):\n        return Widget()")
        assert dcc(node, frozenset()) == 0


def test_collect_class_names_includes_nested():
    tree = ast.parse("class A:\n    class B:\n        pass\nclass C:\n    pass\n")
    assert collect_class_names([tree]) == frozenset({"A", "B", "C"})


# --------------------------------------------------------------------------- #
# CAM
# --------------------------------------------------------------------------- #


class TestCam:
    def test_single_type_gives_one(self):
        node = parse_class(
            "class C:\n"
            "    def a(self, x: int) -> None:\n        pass\n"
            "    def b(self, y: int) -> None:\n        pass\n"
        )
        assert cam(node).value == 1.0

    def test_disjoint_types_give_half(self):
        node = parse_class(
            "class C:\n"
            "    def a(self, x: int) -> None:\n        pass\n"
            "    def b(self, y: str) -> None:\n        pass\n"
        )
        # Birleşim {int, str}; her metot 1/2 → ortalama 0.5
        assert cam(node).value == 0.5

    def test_parameterless_methods_are_skipped(self):
        node = parse_class(
            "class C:\n"
            "    def a(self, x: int) -> None:\n        pass\n"
            "    def b(self) -> int:\n        return 1\n"
        )
        assert cam(node).value == 1.0

    def test_generic_types_are_distinct(self):
        node = parse_class(
            "class C:\n"
            "    def a(self, x: list[str]) -> None:\n        pass\n"
            "    def b(self, y: list[int]) -> None:\n        pass\n"
        )
        assert cam(node).value == 0.5

    def test_no_annotations_returns_none(self):
        node = parse_class("class C:\n    def a(self, x):\n        return x")
        result = cam(node)
        assert result.value is None
        assert result.skipped_reason == CAM_NO_PARAMETERS

    def test_below_coverage_threshold_returns_none(self):
        node = parse_class(
            "class C:\n"
            "    def a(self, x: int) -> None:\n        pass\n"
            "    def b(self, y) -> None:\n        pass\n"
            "    def c(self, z) -> None:\n        pass\n"
        )
        result = cam(node)
        assert result.value is None
        assert result.skipped_reason == CAM_INSUFFICIENT_ANNOTATIONS
        assert result.annotation_coverage == 0.3333  # 4 haneye yuvarlanır

    def test_threshold_is_configurable(self):
        node = parse_class(
            "class C:\n"
            "    def a(self, x: int) -> None:\n        pass\n"
            "    def b(self, y) -> None:\n        pass\n"
        )
        assert cam(node, min_annotation_coverage=0.9).value is None
        assert cam(node, min_annotation_coverage=0.4).value is not None

    def test_class_without_parameters_returns_none(self):
        node = parse_class("class C:\n    def a(self) -> int:\n        return 1")
        assert cam(node).skipped_reason == CAM_NO_PARAMETERS


# --------------------------------------------------------------------------- #
# Altın değerler — examples/messy_project
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def messy_classes():
    """messy_project'teki tüm sınıflar, adlarıyla eşlenmiş."""
    classes: dict[str, ast.ClassDef] = {}
    trees: list[ast.Module] = []
    for path in sorted(MESSY_PROJECT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        trees.append(tree)
        for node in iter_module_classes(tree):
            classes[node.name] = node
    return classes, collect_class_names(trees)


class TestGoldenOrderManager:
    """god.py — ana denek. Beklentiler SMELLS.md'de belgelendi."""

    def test_nom_is_25(self, messy_classes):
        # 8 (sipariş) + 7 (fiyatlandırma) + 5 (günlük) + 5 (bildirim)
        classes, _ = messy_classes
        assert nom(classes["OrderManager"]) == 25

    def test_lcom4_is_4(self, messy_classes):
        """Dört ayrık sorumluluk — sınıfın dörde bölünebileceğinin kanıtı."""
        classes, _ = messy_classes
        assert lcom4(classes["OrderManager"]) == 4

    def test_wmc_is_49(self, messy_classes):
        """25 metodun karmaşıklık toplamı — eşik 50'ye çok yakın."""
        classes, _ = messy_classes
        assert wmc(classes["OrderManager"]) == 49

    def test_dcc_is_8(self, messy_classes):
        # Customer, Product, OrderLine, Order, Invoice, AuditEntry,
        # EmailNotifier, ShippingCalculator
        classes, registry = messy_classes
        assert dcc(classes["OrderManager"], registry) == 8

    def test_all_attributes_are_underscore_private(self, messy_classes):
        classes, _ = messy_classes
        loose, strict = dam(classes["OrderManager"])
        assert loose == 1.0
        assert strict == 0.0

    def test_attribute_set(self, messy_classes):
        classes, _ = messy_classes
        assert assigned_attributes(classes["OrderManager"]) == {
            "_orders",
            "_next_id",
            "_tax_rate",
            "_discount_rules",
            "_log",
            "_smtp_host",
            "_sent",
        }

    def test_cam_is_none_without_annotations(self, messy_classes):
        classes, _ = messy_classes
        result = cam(classes["OrderManager"])
        assert result.value is None
        assert result.annotation_coverage == 0.0


class TestGoldenCleanClasses:
    """models.py — düşük coupling, hesaplanabilir CAM, düşük karmaşıklık.

    **Önemli bulgu:** Bu sınıfların LCOM4'ü 1 değildir. `Customer`'ın her alanı
    için ayrı erişimcisi vardır (`rename` → `name`, `promote` → `tier`,
    `add_note` → `_notes`) ve bu metotlar birbirine hiç dokunmaz. LCOM4 tanımı
    gereği bunu üç ayrı sorumluluk sayar.

    Bu, LCOM4'ün literatürde bilinen zayıflığıdır: **veri taşıyıcı sınıfları
    kohezyonsuz gösterir.** Sınıf kötü tasarlanmış değildir.

    Fikstürü metriği memnun edecek şekilde değiştirmiyoruz; bu tam olarak
    aracın uyardığı Goodhart tuzağı olurdu. Sınırlılık README'nin
    "Metric Definitions & Adaptations" bölümünde belgelenir.
    """

    @pytest.mark.parametrize(
        ("name", "expected"),
        [("Customer", 3), ("Product", 2), ("OrderLine", 1)],
    )
    def test_lcom4_reflects_accessor_style(self, messy_classes, name, expected):
        classes, _ = messy_classes
        assert lcom4(classes[name]) == expected

    def test_customer_components_are_per_field(self, messy_classes):
        """LCOM4=3'ün nereden geldiğinin açık kanıtı."""
        classes, _ = messy_classes
        customer = classes["Customer"]
        known = {m.name for m in class_methods(customer)}
        touched = {m.name: sorted(accessed_attributes(m, known)) for m in class_methods(customer)}
        assert touched["rename"] == ["name"]
        assert touched["promote"] == ["tier"]
        assert touched["add_note"] == ["_notes"]

    def test_clean_classes_have_low_complexity(self, messy_classes):
        """Asıl ayrım burada: god class'ın WMC'si bunların on katından fazla."""
        classes, _ = messy_classes
        assert wmc(classes["Customer"]) < 10
        assert wmc(classes["OrderManager"]) > 40

    def test_customer_nom(self, messy_classes):
        classes, _ = messy_classes
        assert nom(classes["Customer"]) == 6

    def test_orderline_has_low_coupling(self, messy_classes):
        """Yalnızca Product'a bağımlı."""
        classes, registry = messy_classes
        assert dcc(classes["OrderLine"], registry) == 1

    @pytest.mark.parametrize("name", ["Customer", "Product", "OrderLine"])
    def test_annotated_classes_have_cam(self, messy_classes, name):
        classes, _ = messy_classes
        result = cam(classes[name])
        assert result.value is not None
        assert result.annotation_coverage == 1.0


class TestGoldenGreyZone:
    """reporting.py — kısmi annotation, CAM eşiğinin altında."""

    def test_lcom4_is_2(self, messy_classes):
        classes, _ = messy_classes
        assert lcom4(classes["ReportBuilder"]) == 2

    def test_cam_skipped_for_insufficient_coverage(self, messy_classes):
        classes, _ = messy_classes
        result = cam(classes["ReportBuilder"])
        assert result.value is None
        assert result.skipped_reason == CAM_INSUFFICIENT_ANNOTATIONS
        assert 0 < result.annotation_coverage < 0.7


class TestMeasureClass:
    def test_report_is_fully_populated(self, messy_classes):
        classes, registry = messy_classes
        report = measure_class(classes["OrderManager"], module="god", project_classes=registry)
        assert report.qualified_name == "god:OrderManager"
        assert report.nom == 25
        assert report.lcom4 == 4
        assert report.dcc == 8
        assert report.cam is None
        assert report.cam_skipped_reason is not None
        assert len(report.methods) == 25

    def test_method_reports_exclude_self_from_params(self, messy_classes):
        classes, registry = messy_classes
        report = measure_class(classes["Customer"], module="models", project_classes=registry)
        rename = next(m for m in report.methods if m.name == "rename")
        assert rename.param_count == 1
