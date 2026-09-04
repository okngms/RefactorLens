"""Koku kuralları testleri.

Kurallar tamamen kural tabanlıdır; hiçbir test ağa çıkmaz.
"""

import ast
from pathlib import Path

import pytest

from rlens.analysis.class_metrics import (
    collect_class_names,
    iter_module_classes,
    measure_class,
)
from rlens.analysis.model import ClassReport, FunctionReport
from rlens.analysis.parser import parse_project
from rlens.analysis.smells import (
    DATA_CLASS,
    FEATURE_ENVY,
    GOD_CLASS,
    LAYER_MISFIT,
    LONG_METHOD,
    TOO_MANY_PARAMS,
    detect_class_smells,
    detect_data_class,
    detect_feature_envy,
    detect_function_smells,
    detect_god_class,
    detect_layer_misfit,
)
from rlens.config import load_config

LAYERED = Path(__file__).resolve().parent.parent / "examples" / "layered_project"
MESSY = Path(__file__).resolve().parent.parent / "examples" / "messy_project"


@pytest.fixture
def config(tmp_path):
    return load_config(search_from=tmp_path)


def parse(source: str) -> ast.ClassDef:
    return ast.parse(source.strip()).body[0]


def cls(**metrics) -> ClassReport:
    base = {"name": "C", "module": "m", "lineno": 1}
    base.update(metrics)
    return ClassReport(**base)


class TestGodClass:
    """Üç koşul birden aranır."""

    def test_all_three_conditions(self, config):
        smell = detect_god_class(cls(nom=25, wmc=60, lcom4=4), config.smells)
        assert smell is not None and smell.label == GOD_CLASS

    def test_high_nom_alone_is_not_enough(self, config):
        """Büyük ama düzenli bir sınıf god class değildir."""
        assert detect_god_class(cls(nom=30, wmc=30, lcom4=1), config.smells) is None

    def test_high_lcom4_alone_is_not_enough(self, config):
        """Tek başına LCOM4 veri taşıyıcısını yakalardı."""
        assert detect_god_class(cls(nom=5, wmc=5, lcom4=5), config.smells) is None

    def test_boundary_values_count(self, config):
        assert detect_god_class(cls(nom=20, wmc=50, lcom4=3), config.smells) is not None

    def test_just_below_the_boundary(self, config):
        assert detect_god_class(cls(nom=20, wmc=49, lcom4=3), config.smells) is None

    def test_uncomputed_metric_never_qualifies(self, config):
        assert detect_god_class(cls(nom=25, wmc=60, lcom4=None), config.smells) is None

    def test_evidence_names_the_thresholds(self, config):
        smell = detect_god_class(cls(nom=25, wmc=60, lcom4=4), config.smells)
        assert smell.evidence["thresholds"]["nom"] == 20
        assert smell.evidence["nom"] == 25


class TestDataClass:
    """v1'de belgelenen LCOM4 yanlış pozitifini bağlama oturtur."""

    # Dört erişimci, bir hesaplayıcı → oran 0.8, eşik 0.7.
    # Fikstürdeki `Customer` ile aynı şekil.
    ACCESSORS = (
        "class C:\n"
        "    def __init__(self):\n"
        "        self._a = 1\n        self._b = 2\n"
        "        self._c = 3\n        self._d = 4\n"
        "    def a(self):\n        return self._a\n"
        "    def b(self):\n        return self._b\n"
        "    def c(self):\n        return self._c\n"
        "    def d(self):\n        return self._d\n"
        "    def is_set(self):\n        return self._a is not None"
    )

    def test_accessor_heavy_class_is_a_data_class(self, config):
        smell = detect_data_class(
            parse(self.ACCESSORS), cls(nom=5, wmc=5, dam=1.0, lcom4=4), config.smells
        )
        assert smell is not None and smell.label == DATA_CLASS

    def test_note_explains_the_lcom4_reading(self, config):
        smell = detect_data_class(
            parse(self.ACCESSORS), cls(nom=5, wmc=5, dam=1.0, lcom4=4), config.smells
        )
        assert "LCOM4" in smell.note
        assert smell.evidence["lcom4"] == 4

    def test_too_many_methods(self, config):
        assert (
            detect_data_class(parse(self.ACCESSORS), cls(nom=9, wmc=9, dam=1.0), config.smells)
            is None
        )

    def test_public_attributes_fail_the_dam_test(self, config):
        assert (
            detect_data_class(parse(self.ACCESSORS), cls(nom=5, wmc=5, dam=0.0), config.smells)
            is None
        )

    def test_computation_heavy_class_is_not_a_data_class(self, config):
        node = parse(
            "class C:\n"
            "    def __init__(self):\n        self._a = 1\n"
            "    def total(self):\n        return self._a * 2\n"
            "    def label(self):\n        return str(self._a)"
        )
        assert detect_data_class(node, cls(nom=2, wmc=2, dam=1.0), config.smells) is None


class TestFeatureEnvy:
    def test_method_touching_another_object_more(self, config):
        node = parse(
            "class C:\n"
            "    def summarise(self, order):\n"
            "        return (order.total, order.tier, order.country, self._width)"
        )
        found = detect_feature_envy(node, "m", config.smells)
        assert len(found) == 1
        assert found[0].evidence["envied"] == "order"

    def test_two_accesses_are_not_enough(self, config):
        """Oran tek başına yetmez; beş satırlık her metot testi geçerdi."""
        node = parse(
            "class C:\n"
            "    def m(self, order):\n"
            "        order.close()\n        return order.status or self._x"
        )
        assert detect_feature_envy(node, "m", config.smells) == []

    def test_balanced_method_is_not_envious(self, config):
        node = parse(
            "class C:\n"
            "    def m(self, o):\n"
            "        return (o.a, o.b, o.c, self._x, self._y, self._z)"
        )
        assert detect_feature_envy(node, "m", config.smells) == []

    def test_touching_three_objects_once_each_is_coordination(self, config):
        node = parse("class C:\n    def m(self, a, b, c):\n        return (a.x, b.y, c.z, self._w)")
        assert detect_feature_envy(node, "m", config.smells) == []

    def test_label_says_it_is_a_candidate(self, config):
        node = parse("class C:\n    def m(self, o):\n        return (o.a, o.b, o.c, self._x)")
        found = detect_feature_envy(node, "m", config.smells)
        assert found[0].label == FEATURE_ENVY
        assert "candidate" in found[0].note

    def test_threshold_is_configurable(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text(
            "smells:\n  feature_envy: {min_accesses: 2}\n", encoding="utf-8"
        )
        config = load_config(search_from=tmp_path)
        node = parse("class C:\n    def m(self, o):\n        return (o.a, o.b, self._x)")
        assert len(detect_feature_envy(node, "m", config.smells)) == 1


class TestFunctionSmells:
    def test_long_and_branching(self, config):
        report = FunctionReport(name="f", lineno=1, cyclomatic_complexity=12, loc=60)
        labels = [s.label for s in detect_function_smells(report, "m", config)]
        assert LONG_METHOD in labels

    def test_long_but_flat_is_not_a_smell(self, config):
        """Uzun bir eşleme tablosu sorun değildir."""
        report = FunctionReport(name="f", lineno=1, cyclomatic_complexity=1, loc=200)
        assert [s.label for s in detect_function_smells(report, "m", config)] == []

    def test_branching_but_short_is_not_a_long_method(self, config):
        report = FunctionReport(name="f", lineno=1, cyclomatic_complexity=15, loc=20)
        labels = [s.label for s in detect_function_smells(report, "m", config)]
        assert LONG_METHOD not in labels

    def test_too_many_params(self, config):
        report = FunctionReport(name="f", lineno=1, param_count=7)
        labels = [s.label for s in detect_function_smells(report, "m", config)]
        assert TOO_MANY_PARAMS in labels

    def test_target_is_qualified(self, config):
        report = FunctionReport(name="f", lineno=1, param_count=7)
        assert detect_function_smells(report, "m:C", config)[0].target == "m:C.f"


class TestLayerMisfit:
    """İki koşul birden: ihlal kaynağı olmak ve kuplajı eşik üstü olmak."""

    def test_both_conditions(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text(
            "thresholds:\n  by_layer:\n    domain: {dcc: {warn: 2}}\n", encoding="utf-8"
        )
        config = load_config(search_from=tmp_path)
        smell = detect_layer_misfit(cls(module="m", dcc=5), "domain", 1.0, {"m"}, config)
        assert smell is not None and smell.label == LAYER_MISFIT

    def test_violation_without_high_coupling(self, config):
        assert detect_layer_misfit(cls(module="m", dcc=1), "domain", 1.0, {"m"}, config) is None

    def test_high_coupling_without_a_violation(self, config):
        """Bazı katmanlarda yüksek kuplaj tasarım gereğidir."""
        assert detect_layer_misfit(cls(module="m", dcc=20), "domain", 1.0, set(), config) is None

    def test_low_confidence_produces_nothing(self, config):
        """Tahmin üstüne tahmin kurulmaz."""
        assert detect_layer_misfit(cls(module="m", dcc=20), "domain", 0.5, {"m"}, config) is None

    def test_unknown_layer_produces_nothing(self, config):
        assert detect_layer_misfit(cls(module="m", dcc=20), "unknown", 1.0, {"m"}, config) is None


def smells_of(project: Path) -> list:
    config = load_config(search_from=project)
    modules, _ = parse_project(project, config.scan.include, config.scan.exclude)
    registry = collect_class_names([m.tree for m in modules])
    found = []
    for module in modules:
        for node in iter_module_classes(module.tree):
            report = measure_class(
                node,
                module=module.module,
                project_classes=registry,
                cam_min_annotation_coverage=config.metrics.cam_min_annotation_coverage,
            )
            found.extend(detect_class_smells(node, report, config))
    return found


@pytest.fixture(scope="module")
def found():
    return smells_of(LAYERED)


class TestLayeredFixture:
    """ARCH_SMELLS.md sözleşmesi."""

    def test_one_god_class(self, found):
        targets = [s.target for s in found if s.label == GOD_CLASS]
        assert targets == ["src.services.order_service:OrderService"]

    def test_one_data_class(self, found):
        targets = [s.target for s in found if s.label == DATA_CLASS]
        assert targets == ["src.domain.entities:Customer"]

    def test_the_data_class_carries_its_lcom4(self, found):
        """Etiketin asıl işi bu sayıyı bağlama oturtmak."""
        smell = next(s for s in found if s.label == DATA_CLASS)
        assert smell.evidence["lcom4"] == 4

    def test_two_feature_envy_candidates(self, found):
        targets = sorted(s.target for s in found if s.label == FEATURE_ENVY)
        assert targets == [
            "src.api.report_view:ReportView.describe_customer",
            "src.services.order_service:OrderService.close",
        ]

    def test_total_count(self, found):
        assert len(found) == 4

    def test_no_layer_misfit_without_layer_information(self, found):
        assert [s for s in found if s.label == LAYER_MISFIT] == []


class TestMessyFixture:
    def test_the_god_class_is_not_labelled(self):
        """WMC 49, eşik 50 — kural kıl payı ateşlemiyor ve bu doğru."""
        found = smells_of(MESSY)
        assert [s for s in found if s.label == GOD_CLASS] == []

    def test_one_feature_envy_candidate(self):
        found = smells_of(MESSY)
        targets = [s.target for s in found if s.label == FEATURE_ENVY]
        assert targets == ["god:OrderManager.mark_paid"]
