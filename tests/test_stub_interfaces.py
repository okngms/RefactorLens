"""K10: taslak arayüzlerde `god_class` verilmez.

Metot adlarının en az yarısının gövdesi taslaksa (`pass`, `...`, `return` /
`return None`, `raise NotImplementedError`) sınıf davranış taşımayan bir
arayüzdür; "bölünebilir sınıf" iddiası ona uygulanamaz. Kural yalnızca kokuyu
etkiler: NOM, WMC, LCOM4 ve `god_class` kanıt alanları değişmez (K6 deseni).
Ön kayıt ve ölçüm: `experiments/hardening/stateless-gate.md`.

Beklenen değerler elle hesaplandı.
"""

import ast

import pytest

from rlens.analysis.class_metrics import (
    is_stub_body,
    measure_class,
    stub_method_names,
    stub_method_share,
)
from rlens.analysis.model import ClassReport
from rlens.analysis.smells import INTERFACE_STUB_SHARE, detect_class_smells, detect_god_class
from rlens.config import load_config


def _class(source: str) -> ast.ClassDef:
    return next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef))


def _function(source: str):
    return ast.parse(source).body[0]


def _interface(stubs: int, real: int) -> str:
    """`stubs` taslak ve `real` gerçek metotlu büyük sınıf.

    Gerçek metotların her biri kendi attribute'una dokunur ve iki dallıdır:
    CC 3. Taslakların CC'si 1. Her metot ayrı LCOM4 bileşeni.
    """
    lines = ["class Big:"]
    for i in range(stubs):
        lines += [f"    def stub_{i}(self, node):", "        pass", ""]
    for i in range(real):
        lines += [
            f"    def real_{i}(self, x):",
            "        if x:",
            f"            self.a{i} = 1",
            "        elif x is None:",
            f"            self.a{i} = 2",
            "",
        ]
    return "\n".join(lines)


class TestStubBody:
    @pytest.mark.parametrize(
        "body",
        [
            "pass",
            "...",
            "return",
            "return None",
            "raise NotImplementedError",
            "raise NotImplementedError('override me')",
            "'''Only a docstring.'''",
            "'''Doc.'''\n    pass",
        ],
    )
    def test_stub_forms(self, body):
        assert is_stub_body(_function(f"def f(self):\n    {body}\n"))

    @pytest.mark.parametrize(
        "body",
        ["return 1", "raise ValueError('x')", "x = 1\n    pass", "return self.x", "yield"],
    )
    def test_real_bodies(self, body):
        assert not is_stub_body(_function(f"def f(self):\n    {body}\n"))


class TestStubNames:
    def test_counts_names_not_definitions(self):
        """Getter ve setter'ı taslak olan property tek addır."""
        source = """
class P:
    @property
    def v(self):
        pass

    @v.setter
    def v(self, value):
        pass

    def real(self):
        return 1
"""
        node = _class(source)
        assert stub_method_names(node) == {"v"}
        assert stub_method_share(node) == 0.5

    def test_a_name_with_one_real_definition_is_not_a_stub(self):
        source = """
class P:
    @property
    def v(self):
        pass

    @v.setter
    def v(self, value):
        self._v = value
"""
        assert stub_method_names(_class(source)) == set()

    def test_dunders_are_not_counted(self):
        source = (
            "class P:\n    def __init__(self):\n        pass\n    def f(self):\n        return 1\n"
        )
        assert stub_method_share(_class(source)) == 0.0

    def test_no_methods(self):
        assert stub_method_share(_class("class E:\n    x = 1\n")) is None

    def test_report_field(self):
        report = measure_class(_class(_interface(3, 1)), module="m", code_lines=frozenset())
        assert report.stub_methods == 3


class TestGodClassRule:
    @pytest.fixture
    def config(self, tmp_path):
        return load_config(search_from=tmp_path)

    def _report(self, node) -> ClassReport:
        return measure_class(node, module="m", code_lines=frozenset())

    def test_share_constant(self):
        assert INTERFACE_STUB_SHARE == 0.5

    def test_interface_gets_no_god_class(self, config):
        # 30 taslak + 10 gerçek: NOM 40, WMC 30·1 + 10·3 = 60, LCOM4 40, taslak payı 0.75.
        node = _class(_interface(30, 10))
        report = self._report(node)
        assert (report.nom, report.wmc, report.lcom4) == (40, 60, 40)
        assert detect_god_class(report, config.smells) is not None
        labels = [smell.label for smell in detect_class_smells(node, report, config)]
        assert "god_class" not in labels

    def test_exactly_half_is_an_interface(self, config):
        # 20 taslak + 20 gerçek: NOM 40, WMC 20 + 60 = 80, pay 0.5.
        node = _class(_interface(20, 20))
        labels = [s.label for s in detect_class_smells(node, self._report(node), config)]
        assert "god_class" not in labels

    def test_below_half_keeps_the_smell(self, config):
        # 19 taslak + 21 gerçek: NOM 40, WMC 19 + 63 = 82, pay 0.475.
        node = _class(_interface(19, 21))
        report = self._report(node)
        smells = [s for s in detect_class_smells(node, report, config) if s.label == "god_class"]
        assert len(smells) == 1
        assert set(smells[0].evidence) == {"nom", "wmc", "lcom4", "thresholds"}

    def test_metrics_are_untouched(self, config):
        """Metrik gerçeği söyler, koku yorumlar: sayılar taslaklarla birlikte."""
        report = self._report(_class(_interface(30, 10)))
        assert report.nom == 40
        assert report.lcom4 == 40
