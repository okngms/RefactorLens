"""Sertleştirme Blok 1b, madde 3: kapsama tablosu (`experiments/hardening/coverage.py`).

"Ayrım yapmayan metrik düşürülür ya da gerekçesiyle tutulur" kararı bu tabloya
dayanır. Burada sabitlenenler:

* **`null`, tanım gereği belli ve bilgi taşıyan** üç ayrı sayımdır; toplamları
  birim sayısıdır.
* **Tanım gereği belli** kuralları metriğin kendisiyle uyuşur: tek adlı metotta
  LCOM4 1, parametreli tek metotta CAM 1.0, tek attribute'ta DAM 0 ya da 1.
* **Yayılım** yalnızca yeterli bilgi taşıyan değeri olan projede sorulur.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from coverage import (  # noqa: E402
    Coverage,
    aggregate_coverage,
    cam_is_trivial,
    collect,
    dam_is_trivial,
    lcom4_is_trivial,
    logic_coverage,
    render_tables,
    summarise_coverage,
    trivial_value_violations,
)
from distribution import MIN_VALUES  # noqa: E402

from rlens.analysis.class_metrics import cam, dam, lcom4  # noqa: E402


def _class(source: str) -> ast.ClassDef:
    return next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef))


SINGLE_METHOD = """
class A:
    def __init__(self):
        self.x = 1
        self.y = 2

    def run(self):
        return self.x
"""

PROPERTY_PAIR = """
class A:
    @property
    def value(self):
        return self._v

    @value.setter
    def value(self, v):
        self._v = v
"""

TWO_METHODS = """
class A:
    def a(self):
        return self.x

    def b(self):
        return self.y
"""

ONE_TYPED_METHOD = """
class A:
    def a(self, x: int, y: str) -> None:
        pass

    def b(self):
        pass
"""

TWO_TYPED_METHODS = """
class A:
    def a(self, x: int) -> None:
        pass

    def b(self, y: str) -> None:
        pass
"""

ONE_ATTRIBUTE = """
class A:
    def __init__(self):
        self._x = 1
"""


class TestTrivialRules:
    def test_single_method_lcom4_is_trivial_and_one(self):
        node = _class(SINGLE_METHOD)
        assert lcom4_is_trivial(node)
        assert lcom4(node) == 1

    def test_property_pair_is_one_node(self):
        """`lcom4` metotları adla düğüm yapar: getter/setter tek düğüm, değer 1."""
        node = _class(PROPERTY_PAIR)
        assert lcom4_is_trivial(node)
        assert lcom4(node) == 1

    def test_two_methods_are_not_trivial(self):
        node = _class(TWO_METHODS)
        assert not lcom4_is_trivial(node)
        assert lcom4(node) == 2

    def test_cam_with_one_parameterised_method_is_trivial(self):
        node = _class(ONE_TYPED_METHOD)
        assert cam(node).value == 1.0
        assert cam_is_trivial(node)

    def test_cam_with_two_parameterised_methods_is_not_trivial(self):
        node = _class(TWO_TYPED_METHODS)
        assert cam(node).value == 0.5
        assert not cam_is_trivial(node)

    def test_uncomputed_cam_is_not_trivial(self):
        """`null` ayrı sayılır; tanım gereği belli yalnızca hesaplanmış değerdir."""
        node = _class(TWO_METHODS)
        assert cam(node).value is None
        assert not cam_is_trivial(node)

    def test_single_attribute_dam_is_binary(self):
        node = _class(ONE_ATTRIBUTE)
        assert dam_is_trivial(node)
        assert dam(node)[0] == 1.0

    def test_two_attributes_are_not_trivial(self):
        assert not dam_is_trivial(_class(TWO_METHODS))


class TestCoverageCounts:
    def test_three_buckets_add_up_to_units(self):
        coverage = Coverage()
        for value, trivial in [(None, False), (1, True), (3, False), (2, False)]:
            coverage.add(value, trivial)
        assert coverage.units == 4
        assert coverage.nulls == 1
        assert coverage.trivial == 1
        assert coverage.informative == [3, 2]
        assert coverage.computed == 3

    def test_null_is_never_trivial(self):
        coverage = Coverage()
        coverage.add(None, trivial=True)
        assert coverage.nulls == 1
        assert coverage.trivial == 0


class TestSummary:
    def test_constant_metric_has_no_spread(self):
        coverage = Coverage(units=MIN_VALUES, informative=[0.0] * MIN_VALUES)
        summary = summarise_coverage(coverage)
        assert summary["spread"] is False
        assert summary["mode"] == 0.0
        assert summary["mode_share"] == 1.0

    def test_varied_metric_has_spread(self):
        values = list(range(MIN_VALUES))
        summary = summarise_coverage(Coverage(units=MIN_VALUES, informative=values))
        assert summary["spread"] is True

    def test_spread_is_not_asked_on_small_samples(self):
        values = list(range(MIN_VALUES - 1))
        summary = summarise_coverage(Coverage(units=100, informative=values))
        assert summary["eligible"] is False
        assert summary["spread"] is None

    def test_shares_use_all_units(self):
        coverage = Coverage(units=10, nulls=4, trivial=2, informative=[1, 2, 3, 4])
        summary = summarise_coverage(coverage)
        assert summary["computed_share"] == 0.6
        assert summary["trivial_share"] == 0.2
        assert summary["informative_share"] == 0.4

    def test_mode_tie_takes_the_smaller_value(self):
        summary = summarise_coverage(Coverage(units=4, informative=[2, 1, 2, 1]))
        assert summary["mode"] == 1
        assert summary["mode_share"] == 0.5

    def test_empty(self):
        summary = summarise_coverage(Coverage())
        assert summary["computed_share"] is None
        assert summary["mode"] is None
        assert summary["spread"] is None


class TestAggregate:
    def _entry(self, share, eligible=True, spread=True, mode=0.0, units=100):
        return {
            "units": units,
            "computed_share": share,
            "trivial_share": 0.0,
            "informative_share": share,
            "eligible": eligible,
            "spread": spread if eligible else None,
            "mode": mode,
            "mode_share": 0.5,
        }

    def test_shares_are_median_over_projects_with_units(self):
        result = aggregate_coverage(
            [self._entry(0.2), self._entry(0.4), self._entry(0.9), self._entry(None, units=0)]
        )
        assert result["projects"] == 3
        assert result["computed_share"] == 0.4

    def test_spread_counts_only_eligible_projects(self):
        result = aggregate_coverage(
            [
                self._entry(0.5, spread=True),
                self._entry(0.5, spread=False),
                self._entry(0.5, eligible=False),
            ]
        )
        assert result["eligible_projects"] == 2
        assert result["spread_projects"] == 1

    def test_mode_is_most_common_project_mode(self):
        result = aggregate_coverage(
            [self._entry(0.5, mode=0.0), self._entry(0.5, mode=0.0), self._entry(0.5, mode=1.0)]
        )
        assert result["mode"] == 0.0


def _scan(tmp_path, source):
    from rlens.analysis.scanner import scan_project_with_sources
    from rlens.config import load_config

    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "mod.py").write_text(source)
    config_path = tmp_path / "rlens.yaml"
    config_path.write_text("scan:\n  include: ['.']\n")
    return scan_project_with_sources(tmp_path, load_config(config_path))


class TestCollect:
    def test_counts_match_the_scan(self, tmp_path):
        source = (
            SINGLE_METHOD + TWO_METHODS.replace("class A", "class B") + "\ndef f(a, b):\n    pass\n"
        )
        result = _scan(tmp_path, source)
        collected = collect(result)
        assert collected["lcom4"].units == 2
        assert collected["lcom4"].trivial == 1
        assert collected["lcom4"].informative == [2]
        # Birim sayısı raporun kendi fonksiyon + metot sayısına eşit olmalı
        functions = sum(len(c.methods) for m in result.report.modules for c in m.classes)
        functions += sum(len(m.functions) for m in result.report.modules)
        assert collected["cyclomatic_complexity"].units == functions

    def test_trivial_rules_agree_with_the_metrics(self, tmp_path):
        source = "\n".join(
            text.replace("class A", f"class C{i}")
            for i, text in enumerate(
                [SINGLE_METHOD, PROPERTY_PAIR, ONE_TYPED_METHOD, ONE_ATTRIBUTE, TWO_METHODS]
            )
        )
        result = _scan(tmp_path, source)
        assert trivial_value_violations(result) == {"lcom4": 0, "cam": 0, "dam": 0}


class TestLogicCoverage:
    def test_median_and_lowest(self):
        inventory = {
            "projects": {
                "a": {"type": "library", "measured_logic_share": 0.9},
                "b": {"type": "library", "measured_logic_share": 0.5},
                "c": {"type": "cli", "measured_logic_share": 0.8},
                "d": {"type": "ml_research", "measured_logic_share": 0.4},
            }
        }
        result = logic_coverage(inventory)
        assert result["median"] == 0.65
        assert result["by_type"]["library"] == 0.7
        assert result["by_type"]["web_app"] is None
        assert list(result["lowest"]) == ["d", "b", "c"]


class TestTables:
    def test_render(self):
        entry = {
            "projects": 2,
            "computed_share": 0.5,
            "trivial_share": 0.1,
            "informative_share": 0.4,
            "eligible_projects": 2,
            "spread_projects": 1,
            "mode": 0.0,
            "mode_share": 0.75,
        }
        summary = {
            "schema_version": 3,
            "min_values": MIN_VALUES,
            "metrics": {
                "dam": {
                    "label": "DAM",
                    "unit": "class",
                    "all": entry,
                    "by_type": dict.fromkeys(("library", "cli", "web_app", "ml_research"), entry),
                }
            },
            "logic": {
                "median": 0.95,
                "by_type": dict.fromkeys(("library", "cli", "web_app", "ml_research"), 0.9),
                "lowest": {"nanogpt": 0.44},
            },
        }
        text = render_tables(summary)
        assert "| DAM | class | 2 | %50.0 | %10.0 | %40.0 | 1/2 | 0 | %75.0 |" in text
        assert "nanogpt %44.0" in text
