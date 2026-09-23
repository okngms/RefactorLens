"""v2.2 §3: modül düzeyi kohezyon adayı (ön kayıt: `experiments/hardening/module-cohesion.md`).

Beklenen değerler kodu yazmadan önce elle hesaplandı.
"""

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from module_cohesion import (  # noqa: E402
    components,
    expected_touched,
    module_globals,
    touched,
)

MODULE = """
import os
from x import helper

CACHE = {}
LIMIT = 10
counter = 0


def load(key):
    return CACHE.get(key)


def save(key, value):
    CACHE[key] = value


def limit():
    return LIMIT


def bump():
    global counter
    counter += 1


def uses_load():
    return load("a") + os.sep + helper()


class Store:
    def put(self):
        save("k", 1)


def lonely():
    return 1
"""


def _tree():
    return ast.parse(MODULE)


class TestGlobals:
    def test_assigned_names_only(self):
        # İmportlar (os, helper) ve birim adları global değil.
        assert module_globals(_tree()) == {"CACHE", "LIMIT", "counter"}


class TestComponents:
    def test_state_only(self):
        # Durum kenarı yalnız load–save (CACHE). limit (LIMIT) ve bump (counter)
        # tek başına; uses_load, Store, lonely hiçbir global'e dokunmuyor.
        groups = components(_tree(), with_usage=False)
        assert sorted(sorted(g) for g in groups) == [
            ["Store"],
            ["bump"],
            ["limit"],
            ["load", "save"],
            ["lonely"],
            ["uses_load"],
        ]

    def test_with_usage(self):
        # Kullanım kenarı: uses_load → load, Store → save.
        groups = components(_tree(), with_usage=True)
        assert sorted(sorted(g) for g in groups) == [
            ["Store", "load", "save", "uses_load"],
            ["bump"],
            ["limit"],
            ["lonely"],
        ]

    def test_fewer_than_two_units_is_null(self):
        assert components(ast.parse("def f():\n    pass\n"), with_usage=True) is None

    def test_overload_stubs_are_not_units(self):
        source = (
            "from typing import overload\n"
            "@overload\ndef f(x: int) -> int: ...\n"
            "def f(x):\n    return x\n"
        )
        assert components(ast.parse(source), with_usage=True) is None


class TestExpectation:
    def test_hand_computed(self):
        # N=4, bileşen büyüklükleri 2, 1, 1; n=2 seçim. C(4,2)=6.
        # 2'lik bileşen: 1 − C(2,2)/6 = 5/6; her 1'lik: 1 − C(3,2)/6 = 1/2.
        # Toplam 5/6 + 1 = 11/6.
        assert expected_touched([2, 1, 1], 2) == pytest.approx(11 / 6)

    def test_all_chosen_touches_everything(self):
        assert expected_touched([3, 2], 5) == pytest.approx(2.0)

    def test_touched(self):
        groups = [{"a", "b"}, {"c"}, {"d"}]
        assert touched(groups, {"a", "b"}) == 1
        assert touched(groups, {"a", "c", "d"}) == 3
