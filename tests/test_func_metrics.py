"""Fonksiyon metrikleri testleri.

İki katman:

1. **Sentetik testler** — her kuralı tek başına, en küçük örnekle sınar.
   Bir test kırıldığında hangi kuralın bozulduğu doğrudan görünür.
2. **Altın değer testleri** — `examples/messy_project` üzerinde elle
   hesaplanmış değerlerle karşılaştırır. Bunlar kuralların birlikte doğru
   çalıştığını kanıtlar.

Altın değerler önce elle hesaplanmış, sonra koda bakılmıştır. Ters sırada
yapılsaydı test, kodun hatasını da birlikte onaylardı.
"""

import ast
from pathlib import Path

import pytest

from rlens.analysis.func_metrics import (
    cyclomatic_complexity,
    function_loc,
    iter_module_functions,
    max_nesting,
    measure_function,
    param_count,
)

MESSY_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "messy_project"


def parse_function(source: str) -> ast.FunctionDef:
    """Tek fonksiyonluk kaynak metni ayrıştırıp düğümü döndürür."""
    tree = ast.parse(source.strip())
    return tree.body[0]


# --------------------------------------------------------------------------- #
# Cyclomatic complexity
# --------------------------------------------------------------------------- #


class TestCyclomaticComplexity:
    def test_straight_line_function_is_one(self):
        assert cyclomatic_complexity(parse_function("def f():\n    return 1")) == 1

    def test_single_if_adds_one(self):
        assert cyclomatic_complexity(parse_function("def f(x):\n    if x:\n        return 1")) == 2

    def test_else_adds_nothing(self):
        source = "def f(x):\n    if x:\n        return 1\n    else:\n        return 2"
        assert cyclomatic_complexity(parse_function(source)) == 2

    def test_each_elif_counts(self):
        source = (
            "def f(x):\n"
            "    if x == 1:\n        return 1\n"
            "    elif x == 2:\n        return 2\n"
            "    elif x == 3:\n        return 3\n"
        )
        assert cyclomatic_complexity(parse_function(source)) == 4

    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ("for i in x:\n        pass", 2),
            ("while x:\n        pass", 2),
            ("return 1 if x else 2", 2),
        ],
    )
    def test_loops_and_ternary(self, body, expected):
        assert cyclomatic_complexity(parse_function(f"def f(x):\n    {body}")) == expected

    def test_boolean_operators_count_extra_operands(self):
        source = "def f(a, b, c):\n    if a and b and c:\n        return 1"
        # 1 (taban) + 1 (if) + 2 (üç operand → iki kısa devre)
        assert cyclomatic_complexity(parse_function(source)) == 4

    def test_each_except_handler_counts(self):
        source = (
            "def f():\n"
            "    try:\n        g()\n"
            "    except ValueError:\n        pass\n"
            "    except KeyError:\n        pass\n"
        )
        assert cyclomatic_complexity(parse_function(source)) == 3

    def test_try_without_except_adds_nothing(self):
        source = "def f():\n    try:\n        g()\n    finally:\n        h()"
        assert cyclomatic_complexity(parse_function(source)) == 1

    def test_with_adds_nothing(self):
        source = "def f():\n    with open('x') as fh:\n        return fh.read()"
        assert cyclomatic_complexity(parse_function(source)) == 1

    def test_comprehension_for_and_if(self):
        source = "def f(xs):\n    return [x for x in xs if x > 0]"
        assert cyclomatic_complexity(parse_function(source)) == 3

    def test_match_cases_count(self):
        source = (
            "def f(x):\n"
            "    match x:\n"
            "        case 1:\n            return 'a'\n"
            "        case _:\n            return 'b'\n"
        )
        assert cyclomatic_complexity(parse_function(source)) == 3

    def test_nested_function_is_excluded(self):
        """İç içe fonksiyonun karmaşıklığı dıştakine yazılmaz."""
        source = (
            "def outer():\n"
            "    def inner(x):\n"
            "        if x:\n            return 1\n"
            "        return 2\n"
            "    return inner\n"
        )
        assert cyclomatic_complexity(parse_function(source)) == 1


# --------------------------------------------------------------------------- #
# LOC
# --------------------------------------------------------------------------- #


class TestFunctionLoc:
    def test_single_line_body(self):
        assert function_loc(parse_function("def f():\n    return 1")) == 2

    def test_blank_lines_are_counted(self):
        assert function_loc(parse_function("def f():\n    x = 1\n\n    return x")) == 4

    def test_decorator_is_excluded(self):
        source = "@decorator\ndef f():\n    return 1"
        assert function_loc(parse_function(source)) == 2


# --------------------------------------------------------------------------- #
# Parametre sayısı
# --------------------------------------------------------------------------- #


class TestParamCount:
    def test_no_params(self):
        assert param_count(parse_function("def f():\n    pass")) == 0

    def test_positional_params(self):
        assert param_count(parse_function("def f(a, b, c):\n    pass")) == 3

    def test_varargs_and_kwargs_count(self):
        assert param_count(parse_function("def f(a, *args, **kwargs):\n    pass")) == 3

    def test_keyword_only_params_count(self):
        assert param_count(parse_function("def f(a, *, b, c):\n    pass")) == 3

    def test_positional_only_params_count(self):
        assert param_count(parse_function("def f(a, /, b):\n    pass")) == 2

    def test_self_excluded_for_methods(self):
        node = parse_function("def method(self, a, b):\n    pass")
        assert param_count(node, is_method=True) == 2

    def test_cls_excluded_for_methods(self):
        node = parse_function("def method(cls, a):\n    pass")
        assert param_count(node, is_method=True) == 1

    def test_self_counted_when_not_a_method(self):
        node = parse_function("def free(self, a):\n    pass")
        assert param_count(node, is_method=False) == 2

    def test_staticmethod_keeps_first_param(self):
        node = parse_function("@staticmethod\ndef m(a, b):\n    pass")
        assert param_count(node, is_method=True) == 2


# --------------------------------------------------------------------------- #
# İç içelik
# --------------------------------------------------------------------------- #


class TestMaxNesting:
    def test_flat_body_is_zero(self):
        assert max_nesting(parse_function("def f():\n    return 1")) == 0

    def test_single_if_is_one(self):
        assert max_nesting(parse_function("def f(x):\n    if x:\n        return 1")) == 1

    def test_nested_blocks_accumulate(self):
        source = (
            "def f(xs):\n"
            "    for x in xs:\n"
            "        if x:\n"
            "            while x:\n"
            "                x -= 1\n"
        )
        assert max_nesting(parse_function(source)) == 3

    def test_elif_chain_stays_flat(self):
        """On dallı bir elif zinciri on seviye derin değildir."""
        source = (
            "def f(x):\n"
            "    if x == 1:\n        pass\n"
            "    elif x == 2:\n        pass\n"
            "    elif x == 3:\n        pass\n"
            "    elif x == 4:\n        pass\n"
        )
        assert max_nesting(parse_function(source)) == 1

    def test_else_block_counts_as_same_level(self):
        source = "def f(x):\n    if x:\n        pass\n    else:\n        pass"
        assert max_nesting(parse_function(source)) == 1

    def test_nested_else_if_adds_depth(self):
        """`else:` içindeki girintili `if`, `elif`'ten farklıdır."""
        source = "def f(x):\n    if x:\n        pass\n    else:\n        if x:\n            pass"
        assert max_nesting(parse_function(source)) == 2

    def test_nested_definition_counts_but_is_not_entered(self):
        source = (
            "def outer():\n"
            "    def inner():\n"
            "        for i in range(3):\n"
            "            if i:\n                pass\n"
        )
        assert max_nesting(parse_function(source)) == 1

    def test_try_except_nesting(self):
        source = "def f():\n    try:\n        g()\n    except ValueError:\n        h()"
        assert max_nesting(parse_function(source)) == 1


# --------------------------------------------------------------------------- #
# Altın değerler — examples/messy_project/utils.py
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def utils_functions():
    source = (MESSY_PROJECT / "utils.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    return {node.name: node for node in iter_module_functions(tree)}


class TestGoldenValues:
    """Elle hesaplanmış değerler (bkz. examples/messy_project/SMELLS.md)."""

    def test_all_three_functions_are_found(self, utils_functions):
        assert set(utils_functions) == {
            "deep_transform",
            "build_shipping_label",
            "classify_order",
        }

    def test_classify_order_complexity(self, utils_functions):
        # 1 (taban) + 11 (if) + 3 (and) = 15
        assert cyclomatic_complexity(utils_functions["classify_order"]) == 15

    def test_classify_order_params(self, utils_functions):
        assert param_count(utils_functions["classify_order"]) == 7

    def test_classify_order_is_flat(self, utils_functions):
        """Yüksek karmaşıklık, derin iç içelik anlamına gelmez."""
        assert max_nesting(utils_functions["classify_order"]) == 1

    def test_deep_transform_complexity(self, utils_functions):
        # 1 (taban) + 4 (if) + 3 (for) = 8
        assert cyclomatic_complexity(utils_functions["deep_transform"]) == 8

    def test_deep_transform_nesting(self, utils_functions):
        # for > if > for > if > for > if > if
        assert max_nesting(utils_functions["deep_transform"]) == 7

    def test_deep_transform_params(self, utils_functions):
        assert param_count(utils_functions["deep_transform"]) == 1

    def test_build_shipping_label_complexity(self, utils_functions):
        # 1 (taban) + 1 (üçlü ifade) = 2
        assert cyclomatic_complexity(utils_functions["build_shipping_label"]) == 2

    def test_build_shipping_label_params(self, utils_functions):
        assert param_count(utils_functions["build_shipping_label"]) == 7

    def test_build_shipping_label_is_flat(self, utils_functions):
        assert max_nesting(utils_functions["build_shipping_label"]) == 0


def test_measure_function_fills_every_field(utils_functions):
    report = measure_function(utils_functions["classify_order"])
    assert report.name == "classify_order"
    assert report.cyclomatic_complexity == 15
    assert report.param_count == 7
    assert report.max_nesting == 1
    assert report.loc is not None and report.loc > 0
