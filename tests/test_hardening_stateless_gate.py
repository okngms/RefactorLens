"""v2.2 §5b: durumsuz metotlar ve `god_class` (`experiments/hardening/stateless_gate.py`).

Beklenen değerler kodu yazmadan önce elle hesaplandı (ön kayıt:
`experiments/hardening/stateless-gate.md`).
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from stateless_gate import (  # noqa: E402
    ClassFacts,
    candidate_fires,
    class_facts,
    exclusion_share,
    lcom3_stateful,
    lcom4_stateful,
    rejections,
)

from rlens.analysis.class_metrics import lcom4  # noqa: E402


def _class(source: str) -> ast.ClassDef:
    return next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef))


# Durumlu adlar: a{x}, b{x}, c{y}, e{z}. Durumsuz: d (helper'ı çağırır), helper.
# LCOM4 (tam): {a,b} x ile, {c,e} e→c çağrısıyla, {d,helper} çağrıyla → 3.
# R3 (durumlu, çağrılar dahil): {a,b}, {c,e} → 2.
# R4 (durumlu, yalnız attribute): {a,b}, {c}, {e} → 3.
MIXED = """
class G:
    def a(self):
        return self.x

    def b(self):
        self.x = 1

    def c(self):
        return self.y

    def d(self):
        return self.helper()

    def helper(self):
        return 1

    def e(self):
        self.z = self.c()
"""

# 3 taslak + 1 durumlu → taslak payı 3/4.
INTERFACE = """
class Visitor:
    def visit_a(self, node):
        pass

    def visit_b(self, node):
        raise NotImplementedError

    def visit_c(self, node):
        ...

    def reset(self):
        self.seen = set()
"""

# 2 alıcısız + 1 durumlu → alıcısız payı 2/3.
STATIC = """
class Type:
    @staticmethod
    def resolve_a(root, info):
        return root.a

    @staticmethod
    def resolve_b(root, info):
        return root.b

    def cache(self):
        return self.store
"""


class TestStatefulGraphs:
    def test_full_lcom4_for_reference(self):
        assert lcom4(_class(MIXED)) == 3

    def test_r3_drops_stateless_names(self):
        assert lcom4_stateful(_class(MIXED)) == 2

    def test_r4_drops_calls_too(self):
        assert lcom3_stateful(_class(MIXED)) == 3

    def test_no_stateful_method_is_null(self):
        node = _class("class S:\n    def f(self):\n        return 1\n")
        assert lcom4_stateful(node) is None
        assert lcom3_stateful(node) is None


class TestExclusionShares:
    def test_stub_share(self):
        assert exclusion_share(_class(INTERFACE), "stub") == 0.75

    def test_receiverless_share(self):
        assert exclusion_share(_class(STATIC), "no_receiver") == 0.6667

    def test_no_methods(self):
        assert exclusion_share(_class("class E:\n    x = 1\n"), "stub") is None


class TestFacts:
    def test_class_facts(self):
        facts = class_facts(_class(MIXED), name="p:G", nom=6, lcom4_value=3)
        assert facts.stateful == 4
        assert facts.lcom4_stateful == 2
        assert facts.lcom3_stateful == 3
        assert facts.stub_share == 0.0
        assert facts.stateless_share == 0.3333


def _facts(name, lcom4=3, l4s=3, l3s=3, stub=0.0, static=0.0, stateless=0.0):
    return ClassFacts(
        name=name,
        nom=20,
        lcom4=lcom4,
        stateful=10,
        lcom4_stateful=l4s,
        lcom3_stateful=l3s,
        stub_share=stub,
        receiverless_share=static,
        stateless_share=stateless,
    )


class TestCandidates:
    def test_r1_removes_interfaces_from_the_current_gate(self):
        assert candidate_fires(_facts("i", stub=0.5), "R1", None) is False
        assert candidate_fires(_facts("k", stub=0.4), "R1", None) is True
        assert candidate_fires(_facts("low", lcom4=2), "R1", None) is False

    def test_r2_removes_static_namespaces(self):
        assert candidate_fires(_facts("s", static=0.5), "R2", None) is False

    def test_r3_and_r4_use_their_threshold_and_null_never_fires(self):
        assert candidate_fires(_facts("a", l4s=4), "R3", 4) is True
        assert candidate_fires(_facts("b", l4s=3), "R3", 4) is False
        assert candidate_fires(_facts("c", l3s=None), "R4", 2) is False


class TestRejections:
    def test_fires_almost_everywhere(self):
        classes = [_facts(str(i)) for i in range(10)]
        reasons = rejections(classes, lambda c: True, "R4", p75=2, p90=3, p95=4)
        assert "a" in reasons

    def test_firing_on_an_interface(self):
        classes = [_facts("iface", stub=0.6)] + [_facts(str(i), l3s=1) for i in range(9)]
        reasons = rejections(classes, lambda c: c.name == "iface", "R4", 2, 3, 4)
        assert "b" in reasons

    def test_flat_percentiles(self):
        reasons = rejections([_facts("x", l3s=1)], lambda c: False, "R4", 3, 3, 3)
        assert "c" in reasons

    def test_losing_the_uncontroversial_half(self):
        # Bugünkü kapı dördünde ateşliyor, hepsi durumlu; aday yalnız birinde.
        classes = [_facts(str(i), lcom4=5) for i in range(4)]
        reasons = rejections(classes, lambda c: c.name == "0", "R4", 2, 3, 4)
        assert "d" in reasons

    def test_narrow_rule_limit(self):
        # R1 bugünkü 10 kokunun 2'sini kaldırıyor: %20 > %10.
        classes = [_facts(str(i), stub=0.9 if i < 2 else 0.0) for i in range(10)]
        reasons = rejections(
            classes, lambda c: candidate_fires(c, "R1", None), "R1", None, None, None
        )
        assert "narrow" in reasons

    def test_a_clean_candidate_has_no_reasons(self):
        classes = [_facts(str(i), l3s=5 if i < 5 else 1) for i in range(10)]
        reasons = rejections(classes, lambda c: c.lcom3_stateful >= 3, "R4", 2, 3, 5)
        assert reasons == []
