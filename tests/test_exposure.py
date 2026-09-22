"""v2.2: fiili açıklık (EXP) adayı (ön kayıt: `experiments/hardening/exposure.md`).

Beklenen değerler kodu yazmadan önce elle hesaplandı.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from exposure_measure import (  # noqa: E402
    attribute_index,
    exposure,
    external_attribute_names,
)

MODELS = """
class A:
    def __init__(self):
        self.x = 1
        self._y = 2
        self.shared = 0

    def f(self):
        return self._y

    @classmethod
    def make(cls):
        return cls.x


class B:
    def __init__(self):
        self.shared = 1
        self.z = 3


class Empty:
    def run(self):
        return 1


class OnlyShared:
    shared = 5
"""

USE = """
def use(a, b):
    b.z = 4
    return a.x


class Child:
    def g(self):
        return self._y
"""


def _trees():
    return [("models", ast.parse(MODELS)), ("use", ast.parse(USE))]


def _class(name):
    return next(n for n in ast.parse(MODELS).body if isinstance(n, ast.ClassDef) and n.name == name)


class TestIndex:
    def test_owners(self):
        index = attribute_index(_trees())
        assert index["x"] == {("models", "A")}
        assert index["shared"] == {("models", "A"), ("models", "B"), ("models", "OnlyShared")}
        assert index["z"] == {("models", "B")}

    def test_external_names(self):
        # a.x (okuma) ve b.z (yazma) dış erişim; self._y, cls.x ve alt sınıftaki
        # self._y iç erişim.
        assert external_attribute_names(_trees()) == {"x", "z"}


class TestExposure:
    def _value(self, name):
        trees = _trees()
        return exposure(_class(name), attribute_index(trees), external_attribute_names(trees))

    def test_partial(self):
        # A: çözülebilir x ve _y (shared üç sınıfta, çözülemez); dışarıdan yalnız x → 0.5
        assert self._value("A") == 0.5

    def test_full(self):
        # B: çözülebilir yalnız z; dışarıdan yazılıyor → 1.0
        assert self._value("B") == 1.0

    def test_no_attributes_is_null(self):
        assert self._value("Empty") is None

    def test_no_resolvable_attribute_is_null(self):
        assert self._value("OnlyShared") is None


class TestStatistics:
    def test_eta_squared_hand_computed(self):
        # Gruplar {0, 0} ve {1, 1}: bütün varyans gruplar arası → 1.0
        from exposure_measure import eta_squared

        assert eta_squared({"a": [0.0, 0.0], "b": [1.0, 1.0]}) == 1.0
        # {0, 1} ve {0, 1}: grup ortalamaları aynı → 0.0
        assert eta_squared({"a": [0.0, 1.0], "b": [0.0, 1.0]}) == 0.0
        # {0, 0, 1} ve {1}: ortalama 0.5; toplam KT 1.0; arası 3·(1/3−1/2)² + 1·(1/2)² = 1/3
        assert eta_squared({"a": [0.0, 0.0, 1.0], "b": [1.0]}) == 0.3333

    def test_eta_squared_undefined(self):
        from exposure_measure import eta_squared

        assert eta_squared({"a": [0.5, 0.5]}) is None

    def test_naming_consistency(self):
        from exposure_measure import naming_consistent

        assert naming_consistent((2, 20), (10, 20)) is True
        assert naming_consistent((10, 20), (10, 20)) is False
        assert naming_consistent((1, 19), (10, 20)) is None

    def test_verdicts_need_a_reason(self):
        from exposure_measure import verdict_problems

        sample = [{"id": "a"}, {"id": "b"}]
        verdicts = {
            "a": {"verdict": "correct", "reason": "line 12: order.total"},
            "b": {"verdict": None},
        }
        assert verdict_problems(sample, verdicts) == ["b: verdict must be correct or wrong"]
