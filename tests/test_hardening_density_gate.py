"""v2.2 §5b: `god_class` kapısı adayları (`experiments/hardening/density_gate.py`).

Beklenen değerler kodu çalıştırmadan elle hesaplandı. Burada sabitlenenler:

* **LCOM3-HM** LCOM4'ün grafiğinden çağrı kenarlarını çıkarır; her zaman
  LCOM3-HM ≥ LCOM4.
* **TCC** yalnızca **doğrudan** ortak attribute'u sayar; ortak yardımcıyı
  çağırmak iki metodu bağlamaz.
* **Durumsuz metot türleri** öncelik sırasıyla atanır: taslak, alıcısız,
  devreden, `self`'i kullanmayan.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from density_gate import (  # noqa: E402
    LargeClass,
    attribute_sets,
    gate_summary,
    is_stub_body,
    lcom3_hm,
    stateless_kinds,
    stateless_share,
    tcc_direct,
)

from rlens.analysis.class_metrics import lcom4  # noqa: E402


def _class(source: str) -> ast.ClassDef:
    return next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef))


def _function(source: str):
    return ast.parse(source).body[0]


# Ortak yardımcı: `fail` tek başına `self.errors`'a dokunuyor, diğer üçü onu
# çağırıyor. LCOM4: çağrı kenarları dördünü bağlar → 1. LCOM3-HM: `fail` ile
# `report` `errors`'ı paylaşır, `check_a` ve `check_b` hiçbir attribute'a
# dokunmaz → {fail, report}, {check_a}, {check_b} = 3.
# TCC: 4 ad, 6 çift; yalnız (fail, report) doğrudan paylaşır → 1/6 = 0.1667.
HUB = """
class Checker:
    def fail(self, msg):
        self.errors.append(msg)

    def report(self):
        return list(self.errors)

    def check_a(self, x):
        if x:
            self.fail("a")

    def check_b(self, y):
        if y:
            self.fail("b")
"""

# İki ayrı küme: (a, b) `x`'i, (c, d) `y`'yi paylaşır; çağrı yok.
# LCOM4 = LCOM3-HM = 2. TCC: 6 çiftin 2'si → 0.3333.
TWO_GROUPS = """
class Split:
    def a(self):
        return self.x

    def b(self):
        self.x = 1

    def c(self):
        return self.y

    def d(self):
        self.y = 2
"""

KINDS = """
class Mixed:
    def stub(self):
        '''Belge.'''
        raise NotImplementedError

    @staticmethod
    def static(value):
        return value + 1

    def delegate(self):
        return self.stateful()

    def unused(self, value):
        return value * 2

    def stateful(self):
        return self.state
"""


class TestHubClass:
    def test_lcom4_joins_everything_through_calls(self):
        assert lcom4(_class(HUB)) == 1

    def test_lcom3_ignores_calls(self):
        assert lcom3_hm(attribute_sets(_class(HUB))) == 3

    def test_tcc_counts_only_direct_sharing(self):
        assert tcc_direct(attribute_sets(_class(HUB))) == 0.1667

    def test_stateless_share(self):
        assert stateless_share(attribute_sets(_class(HUB))) == 0.5


class TestTwoGroups:
    def test_lcom3_equals_lcom4_without_calls(self):
        node = _class(TWO_GROUPS)
        assert lcom3_hm(attribute_sets(node)) == lcom4(node) == 2

    def test_tcc(self):
        assert tcc_direct(attribute_sets(_class(TWO_GROUPS))) == 0.3333


class TestUndefined:
    def test_no_methods(self):
        node = _class("class Empty:\n    x = 1\n")
        assert lcom3_hm(attribute_sets(node)) is None
        assert stateless_share(attribute_sets(node)) is None

    def test_tcc_needs_two_method_names(self):
        """Property getter/setter tek addır: tek ad, çift yok."""
        source = """
class P:
    @property
    def v(self):
        return self._v

    @v.setter
    def v(self, value):
        self._v = value
"""
        sets = attribute_sets(_class(source))
        assert list(sets) == ["v"]
        assert tcc_direct(sets) is None


class TestStubBody:
    def test_forms(self):
        for body in (
            "pass",
            "...",
            "return",
            "return None",
            "raise NotImplementedError",
            "raise NotImplementedError('x')",
            "'''Doc.'''",
        ):
            assert is_stub_body(_function(f"def f(self):\n    {body}\n")), body

    def test_real_bodies(self):
        for body in ("return 1", "raise ValueError('x')", "x = 1\n    pass"):
            assert not is_stub_body(_function(f"def f(self):\n    {body}\n")), body


class TestStatelessKinds:
    def test_each_kind_once(self):
        assert stateless_kinds(_class(KINDS)) == {
            "stub": 1,
            "no_receiver": 1,
            "delegates": 1,
            "self_unused": 1,
        }

    def test_stateful_methods_are_not_counted(self):
        assert sum(stateless_kinds(_class(TWO_GROUPS)).values()) == 0


class TestGateSummary:
    def _large(self, name, lcom4, lcom3, tcc, stateless=0.0):
        return LargeClass(name=name, nom=20, lcom4=lcom4, lcom3=lcom3, tcc=tcc, stateless=stateless)

    def test_new_and_lost_are_relative_to_the_current_gate(self):
        classes = [
            self._large("kept", lcom4=4, lcom3=6, tcc=0.1),
            self._large("new", lcom4=1, lcom3=8, tcc=0.05, stateless=0.7),
            self._large("lost", lcom4=3, lcom3=3, tcc=0.5),
            self._large("never", lcom4=1, lcom3=1, tcc=0.9),
        ]
        summary = gate_summary(classes, "lcom3", 5, current=3)
        assert summary["fired"] == 2
        assert summary["new"] == 1
        assert summary["lost"] == 1
        assert summary["new_stateless"] == 1
        assert summary["new_examples"] == ["new"]
        assert summary["lost_examples"] == ["lost"]

    def test_tcc_gate_fires_below_the_threshold(self):
        classes = [self._large("low", 1, 1, 0.1), self._large("none", 1, 1, None)]
        assert gate_summary(classes, "tcc", 0.2, current=3)["fired"] == 1
