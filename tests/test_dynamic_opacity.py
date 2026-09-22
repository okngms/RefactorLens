"""v2.2 §3, K13: dinamik opaklık (ön kayıt: `experiments/hardening/dynamic-opacity.md`).

Beklenen değerler kodu yazmadan önce elle hesaplandı.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from rlens.analysis.class_metrics import has_attribute_hooks  # noqa: E402
from rlens.analysis.func_metrics import dynamic_sites  # noqa: E402

EVERY_KIND = """
def f(obj, name, code, **kwargs):
    a = getattr(obj, "x")
    b = getattr(obj, name)
    setattr(obj, "k" + name, 1)
    hasattr(obj, "y")
    delattr(obj, name)
    eval("1 + 1")
    exec(code)
    g(**kwargs)
    g(**other)
    importlib.import_module(name)
    importlib.import_module("os")
    __import__(name)
    __import__("sys")

    def inner():
        getattr(obj, name)
        eval(code)

    return b
"""


def _fn(source: str):
    return ast.parse(source).body[0]


class TestSites:
    def test_every_kind_once_and_constants_skipped(self):
        # Sayılanlar (satır, tür):
        #  4 getattr(obj, name)            getattr
        #  5 setattr(obj, "k" + name, 1)   setattr (birleştirilmiş string sabit değil)
        #  7 delattr(obj, name)            delattr
        #  8 eval("1 + 1")                 eval (sabit de olsa: çalıştırılan kod)
        #  9 exec(code)                    exec
        # 10 g(**kwargs)                   kwargs (kendi **kwargs'ı)
        # 12 importlib.import_module(name) import
        # 14 __import__(name)              import
        # Sayılmayanlar: getattr/hasattr sabitle, g(**other), sabit importlar,
        # iç içe `inner`.
        sites = dynamic_sites(_fn(EVERY_KIND))
        assert sites == [
            (4, "getattr"),
            (5, "setattr"),
            (7, "delattr"),
            (8, "eval"),
            (9, "exec"),
            (10, "kwargs"),
            (12, "import"),
            (14, "import"),
        ]

    def test_kwargs_forwarding_uses_the_functions_own_name(self):
        source = "class A:\n    def m(self, **opts):\n        return super().m(**opts)\n"
        method = ast.parse(source).body[0].body[0]
        assert dynamic_sites(method) == [(3, "kwargs")]

    def test_no_kwargs_parameter_means_no_forwarding(self):
        assert dynamic_sites(_fn("def f(d):\n    return g(**d)\n")) == []

    def test_clean_function(self):
        assert dynamic_sites(_fn("def f(x):\n    return x.a + x.b\n")) == []

    def test_decorators_and_defaults_are_not_the_body(self):
        source = "@register(getattr(m, n))\ndef f(x=getattr(m, n)):\n    return x\n"
        assert dynamic_sites(_fn(source)) == []


class TestHooks:
    def test_getattr_hook(self):
        source = "class Proxy:\n    def __getattr__(self, name):\n        return 1\n"
        assert has_attribute_hooks(ast.parse(source).body[0]) is True

    def test_setattr_and_getattribute(self):
        for hook in ("__setattr__", "__getattribute__"):
            source = f"class P:\n    def {hook}(self, *a):\n        pass\n"
            assert has_attribute_hooks(ast.parse(source).body[0]) is True

    def test_plain_class(self):
        source = "class P:\n    def get(self, name):\n        return getattr(self, name)\n"
        assert has_attribute_hooks(ast.parse(source).body[0]) is False


class TestRules:
    def test_concentration_needs_two_of_three(self):
        from dynamic_opacity import concentration

        rates = {"attrs": 5.0, "pydantic": 1.0, "sqlalchemy": 9.0, "black": 0.5}
        assert concentration(rates, median=2.0) == {
            "above": ["attrs", "sqlalchemy"],
            "refuted": False,
        }
        assert concentration(rates, median=6.0)["refuted"] is True

    def test_verdicts_need_a_reason(self):
        from dynamic_opacity import verdict_problems

        sample = [{"id": "a"}, {"id": "b"}]
        verdicts = {"a": {"verdict": "opaque", "reason": "x.py:3: name is a parameter"}, "b": {}}
        assert verdict_problems(sample, verdicts) == ["b: verdict must be opaque or resolvable"]


# --------------------------------------------------------------------------- #
# Altın değerler — examples/messy_project (elle, alanlar rapora bağlanmadan önce)
# --------------------------------------------------------------------------- #


class TestGoldenMessyProject:
    """Fikstürün kodunda `getattr`/`setattr`/`eval`/`**kwargs` aktarımı ya da
    `__getattr__` yok (yalnızca docstring'lerde markdown `**`): her fonksiyon 0,
    her sınıf kancasız."""

    def test_every_function_is_zero_and_no_class_is_hooked(self):
        from rlens.analysis.scanner import scan_project
        from rlens.config import load_config

        project = REPO_ROOT / "examples" / "messy_project"
        report = scan_project(project, load_config(search_from=project))
        functions = [f for m in report.modules for f in m.functions]
        functions += [f for c in report.iter_classes() for f in c.methods]
        assert len(functions) == 55
        assert {f.dynamic_sites for f in functions} == {0}
        assert {c.dynamic_attribute_hooks for c in report.iter_classes()} == {False}
