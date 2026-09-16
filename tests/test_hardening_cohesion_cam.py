"""Sertleştirme Blok 1: CAM kapsamı ve kohezyon karşılaştırma betikleri.

İki betiğin sonucu, doğrulamadığı bir varsayıma yaslanmamalı:

* `cam_coverage.parameter_counts`, `cam`'in parametre kuralını tekrar eder.
  İkisi ayrışırsa "sıfır annotation" ile "parametre yok" ayrımı sessizce
  yanlışlanır; tutarlılık burada sınanır.
* `compare_cohesion.explain`'in ilk sürümü ölçmeden "attribute varsa hub"
  diyordu ve sapmaların çoğunu yanlış etiketledi. `call_edges` ile
  `hub_attributes` ayrımı artık çağrısız grafik ölçülerek yapılır; iki durumun
  ayrı sınıflara düştüğü burada sınanır.

`cohesion` paketi gerekmez; o yalnızca `collect` içinde import edilir.
"""

import ast
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from cam_coverage import (  # noqa: E402
    BELOW_THRESHOLD,
    COMPUTED,
    NO_PARAMETERS,
    ZERO_ANNOTATIONS,
    classify,
    parameter_counts,
    quantile,
)
from compare_cohesion import (  # noqa: E402
    CALL_EDGES,
    HUB_ATTRIBUTES,
    ISOLATED_METHODS,
    Pair,
    attribute_components,
    average_ranks,
    deviations,
    explain,
    god_class_gate,
    spearman,
)

from rlens.analysis.class_metrics import cam, lcom4  # noqa: E402


def klass(source: str) -> ast.ClassDef:
    return ast.parse(textwrap.dedent(source).strip()).body[0]


# --------------------------------------------------------------------------- #
# CAM kapsamı
# --------------------------------------------------------------------------- #


class TestCamClassification:
    def test_no_parameters(self):
        node = klass(
            """
            class C:
                def a(self): return 1
                def b(self): return 2
            """
        )
        item = classify(node)
        assert item.status == NO_PARAMETERS
        assert item.coverage is None

    def test_zero_annotations_is_not_no_parameters(self):
        """`cam` ikisini aynı sebep altında döndürür; betik ayırmalı."""
        node = klass(
            """
            class C:
                def a(self, x): return x
            """
        )
        assert cam(node).skipped_reason == "no_annotated_parameters"
        assert classify(node).status == ZERO_ANNOTATIONS

    def test_below_threshold(self):
        node = klass(
            """
            class C:
                def a(self, x: int, y, z): return x
            """
        )
        item = classify(node)
        assert item.status == BELOW_THRESHOLD
        assert item.coverage == pytest.approx(0.3333)

    def test_single_parameterised_method_is_computed_but_not_informative(self):
        """Tek metodun tipleri birleşimin tamamıdır: CAM tanım gereği 1.0."""
        node = klass(
            """
            class C:
                def a(self, x: int): return x
                def b(self): return 1
            """
        )
        item = classify(node)
        assert (item.status, item.value, item.informative) == (COMPUTED, 1.0, False)

    def test_two_parameterised_methods_are_informative(self):
        node = klass(
            """
            class C:
                def a(self, x: int): return x
                def b(self, y: str): return y
            """
        )
        item = classify(node)
        assert (item.value, item.informative) == (0.5, True)

    @pytest.mark.parametrize(
        "source",
        [
            "class C:\n    def a(self, x, *args, **kw): pass",
            "class C:\n    @staticmethod\n    def a(x, y): pass",
            "class C:\n    @classmethod\n    def a(cls, x: int): pass",
            "class C:\n    def a(self, x: int, /, y: int, *, z): pass",
            "class C:\n    def __init__(self, x): pass\n    def a(self): pass",
        ],
    )
    def test_parameter_counts_agree_with_cam(self, source):
        """Tekrarlanan kural `cam` ile aynı kalmalı: parametresizlik tanıları örtüşür."""
        node = klass(source)
        _, total = parameter_counts(node)
        result = cam(node)
        if total == 0:
            assert result.annotation_coverage == 0.0
            assert classify(node).status == NO_PARAMETERS
        else:
            assert classify(node).status != NO_PARAMETERS

    def test_quantile(self):
        assert quantile([], 0.5) is None
        assert quantile([0.0, 1.0], 0.5) == 0.5
        assert quantile([1.0, 0.0, 0.5, 0.25], 0.5) == 0.375


# --------------------------------------------------------------------------- #
# Spearman
# --------------------------------------------------------------------------- #


class TestSpearman:
    def test_average_ranks_with_ties(self):
        assert average_ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]

    def test_perfect_monotonic(self):
        assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
        assert spearman([1, 2, 3, 4], [9, 5, 2, 1]) == -1.0

    def test_nonlinear_monotonic_is_still_perfect(self):
        """Spearman değeri değil sırayı ölçer."""
        assert spearman([1, 2, 3, 4], [1, 8, 27, 1000]) == 1.0

    def test_known_value_with_ties(self):
        # Elle: sıralar x=[1,2.5,2.5,4], y=[1,2,3,4] → ρ = 0.9487
        assert spearman([1, 2, 2, 3], [1, 2, 3, 4]) == pytest.approx(0.9487, abs=1e-4)

    def test_degenerate_inputs(self):
        assert spearman([1, 2], [2, 1]) is None
        assert spearman([1, 1, 1], [1, 2, 3]) is None
        with pytest.raises(ValueError):
            spearman([1, 2, 3], [1, 2])

    def test_deviations_rank_disagreement_first(self):
        def pair(name, value, coh):
            return Pair("p", "m.py", name, 1, value, coh)

        pairs = [pair("agree_bad", 5, 0.0), pair("agree_good", 1, 90.0), pair("disagree", 1, 0.0)]
        # Kötülük sıraları: lcom4 [3, 1.5, 1.5], -cohesion [2.5, 1, 2.5]
        # Farklar /3: agree_bad 0.167, agree_good 0.167, disagree 0.333
        scored = deviations(pairs)
        assert scored[0] == (0.3333, pairs[2])
        assert {p.name for _, p in scored[1:]} == {"agree_bad", "agree_good"}
        assert deviations([]) == []


# --------------------------------------------------------------------------- #
# Sapma kategorileri
# --------------------------------------------------------------------------- #

CALL_HUB = """
class Visitor:
    def add(self, item):
        self.items.append(item)
    def visit_a(self, node):
        self.add(node)
    def visit_b(self, node):
        self.add(node.child)
    def visit_c(self, node):
        self.add(node.other)
"""

ATTRIBUTE_HUB = """
class Service:
    def a(self):
        return self.config.x
    def b(self):
        return self.config.y
    def c(self):
        return self.config.z
"""

ISOLATED = """
class Visitor:
    def visit_a(self, t):
        return self.s
    def visit_b(self, t):
        return self.s
    def visit_c(self, t):
        return None
"""


class TestDeviationCategories:
    def test_call_hub_falls_apart_without_calls(self):
        """Ortak yardımcı metot sınıfı bağlar; çağrılar çıkınca parçalanır."""
        node = klass(CALL_HUB)
        assert lcom4(node) == 1
        assert attribute_components(node) == 4
        assert explain(node, lcom4(node), 5.0) == CALL_EDGES

    def test_attribute_hub_stays_connected_without_calls(self):
        node = klass(ATTRIBUTE_HUB)
        assert lcom4(node) == 1
        assert attribute_components(node) == 1
        assert explain(node, lcom4(node), 5.0) == HUB_ATTRIBUTES

    def test_isolated_methods(self):
        node = klass(ISOLATED)
        assert lcom4(node) == 2
        assert explain(node, lcom4(node), 66.0) == ISOLATED_METHODS

    def test_high_density_single_component_is_unexplained(self):
        node = klass(ATTRIBUTE_HUB)
        assert explain(node, 1, 90.0) == "unexplained"


class TestGodClassGate:
    def test_counts_classes_gated_only_by_call_edges(self):
        body = "    def m{i}(self, x):\n        if x:\n            return self.helper()\n"
        methods = "\n".join(body.format(i=i) + f"        return self.a{i}" for i in range(4))
        source = f"class Big:\n    def helper(self):\n        return 1\n{methods}\n"
        module = type("M", (), {"tree": ast.parse(source), "relative_path": "big.py"})()
        rules = {"nom": 5, "wmc": 9, "lcom4": 3}
        gate = god_class_gate([module], rules)
        assert gate["size_qualified"] == 1
        assert gate["fired"] == 0
        assert gate["gated_by_lcom4"] == 1
        assert gate["gated_only_because_of_call_edges"] == 1
        assert gate["examples"] == ["big.py:Big nom=5 lcom4=1"]
