"""v2.2 §3/§5b: raporun görmediği kod (`experiments/hardening/unreported.py`).

Beklenen değerler elle hesaplandı.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from corpus import line_coverage, logic_sets  # noqa: E402
from unreported import conditional_units, duplicate_names, reported_duplicates  # noqa: E402

MODULE = """
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from x import Y

    class Proxy:
        pass
else:
    Proxy = object

try:
    import ujson as json
except ImportError:
    def loads(text):
        return text

if sys.version_info >= (3, 11):
    def compat():
        return 1
else:
    def compat():
        return 0

if DEBUG:
    class Tracer:
        pass

with lock:
    def locked():
        pass

def top():
    if True:
        def inner():
            pass
    return 1

class Top:
    pass
"""


class TestConditionalUnits:
    def test_kinds_and_names(self):
        units = conditional_units(ast.parse(MODULE))
        assert [(u.name, u.kind, u.condition) for u in units] == [
            ("Proxy", "class", "type_checking"),
            ("loads", "function", "import_fallback"),
            ("compat", "function", "version_platform"),
            ("compat", "function", "version_platform"),
            ("Tracer", "class", "other_if"),
            ("locked", "function", "other"),
        ]

    def test_nested_definitions_inside_functions_are_not_module_level(self):
        names = {u.name for u in conditional_units(ast.parse(MODULE))}
        assert "inner" not in names

    def test_duplicates(self):
        # `compat` iki dalda tanımlı; `Proxy` bir dalda sınıf, diğerinde atama —
        # atama birim değildir, kimlik çakışması sayılmaz.
        tree = ast.parse(MODULE)
        assert duplicate_names(tree) == {"compat"}

    def test_top_level_and_conditional_same_name(self):
        tree = ast.parse("def f():\n    pass\nif X:\n    def f():\n        pass\n")
        assert duplicate_names(tree) == {"f"}


class TestLogicSets:
    def test_counts_match_line_coverage(self):
        tree = ast.parse(MODULE)
        logic, measured = logic_sets(tree)
        assert (len(logic), len(logic & measured)) == line_coverage(tree)

    def test_measured_is_only_top_level_units(self):
        tree = ast.parse(MODULE)
        _, measured = logic_sets(tree)
        # `top` 34-38, `Top` 40-41 (kaynak baştaki boş satırla başlar)
        assert measured == set(range(34, 39)) | {40, 41}


class TestReportedDuplicates:
    def test_overload_stubs_are_not_units(self):
        source = (
            "from typing import overload\n"
            "@overload\ndef f(x: int) -> int: ...\n"
            "@overload\ndef f(x: str) -> str: ...\n"
            "def f(x):\n    return x\n"
        )
        tree = ast.parse(source)
        assert reported_duplicates(tree) == set()
        assert duplicate_names(tree) == set()

    def test_registered_underscore_functions_collide_today(self):
        source = "@f.register\ndef _(x: int):\n    pass\n@f.register\ndef _(x: str):\n    pass\n"
        assert reported_duplicates(ast.parse(source)) == {"_"}
