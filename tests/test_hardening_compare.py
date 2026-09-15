"""Sertleştirme Blok 1 CC karşılaştırma betiğinin mantığı.

`compare_radon.py`'nin kabul kriteri "sınıflandırılmamış fark 0"dır. Bu sayı
ancak sınıflandırıcı doğruysa bir şey ifade eder: fazla açıklayan bir
sınıflandırıcı gerçek bir hatayı tanım farkı diye örtbas eder. Bu yüzden:

* **Saf testler** her kategoriyi elle hesaplanmış değerle sınar; radon
  gerektirmez, CI'da hep koşar.
* **Mutabakat testleri** radon kuruluysa aynı örneklerde
  `bizim CC + fark == radon CC` eşitliğini gerçek radon ile doğrular.
"""

import ast
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from compare_radon import (  # noqa: E402
    CATEGORIES,
    PROJECTS_FILE,
    definition_deltas,
    load_projects,
)

from rlens.analysis.func_metrics import cyclomatic_complexity  # noqa: E402


def function(source: str) -> ast.FunctionDef:
    return ast.parse(textwrap.dedent(source).strip()).body[0]


#: (ad, kaynak, beklenen farklar) — farklar elle hesaplandı.
CASES = [
    (
        "no_difference",
        """
        def f(x):
            if x and x > 1:
                return [i for i in x if i]
            return None
        """,
        {},
    ),
    (
        "try_else",
        """
        def f():
            try:
                a()
            except ValueError:
                b()
            else:
                c()
        """,
        {"try_else": 1},
    ),
    (
        "loop_else",
        """
        def f(xs):
            for x in xs:
                pass
            else:
                pass
            while xs:
                break
            else:
                pass
        """,
        {"loop_else": 2},
    ),
    (
        "assert_with_contents",
        """
        def f(x, y):
            assert x and y, "a" if x else "b"
        """,
        {"assert": 1, "assert_contents": -2},
    ),
    (
        "match_wildcard",
        """
        def f(x):
            match x:
                case 1:
                    pass
                case _:
                    pass
        """,
        {"match_wildcard": -1},
    ),
    (
        "match_capture_counts_as_radon_wildcard",
        """
        def f(x):
            match x:
                case 1:
                    pass
                case other:
                    pass
        """,
        {"match_wildcard": -1},
    ),
    (
        "match_without_wildcard",
        """
        def f(x):
            match x:
                case 1:
                    pass
                case [a, _]:
                    pass
        """,
        {},
    ),
    (
        "except_star",
        """
        def f():
            try:
                a()
            except* ValueError:
                pass
            except* TypeError:
                pass
        """,
        {"except_star": -2},
    ),
    (
        "nested_definitions_are_not_inspected",
        """
        def f():
            def inner():
                assert x
                for i in y:
                    pass
                else:
                    pass
            class C:
                def m(self):
                    try:
                        pass
                    except E:
                        pass
                    else:
                        pass
            return inner
        """,
        {},
    ),
    (
        "decorator_and_defaults",
        """
        @register(a or b)
        def f(x=c if d else e):
            return x
        """,
        {},
    ),
]


class TestDefinitionDeltas:
    @pytest.mark.parametrize(("name", "source", "expected"), CASES, ids=[c[0] for c in CASES])
    def test_categories(self, name, source, expected):
        assert definition_deltas(function(source)) == expected

    def test_every_category_is_exercised(self):
        seen = {category for _, _, expected in CASES for category in expected}
        assert seen == set(CATEGORIES)


class TestRadonAgreement:
    @pytest.mark.parametrize(("name", "source", "expected"), CASES, ids=[c[0] for c in CASES])
    def test_prediction_matches_radon(self, name, source, expected):
        complexity = pytest.importorskip("radon.complexity")
        code = textwrap.dedent(source).strip()
        node = function(source)
        blocks = [b for b in complexity.cc_visit(code) if b.name == node.name]
        assert len(blocks) == 1
        predicted = cyclomatic_complexity(node) + sum(definition_deltas(node).values())
        assert predicted == blocks[0].complexity


class TestProjectList:
    def test_reference_set_is_frozen(self):
        projects = load_projects(PROJECTS_FILE)
        assert 10 <= len(projects) <= 15
        assert len({p.name for p in projects}) == len(projects)
        assert all(len(p.commit) == 40 for p in projects)
        assert all(int(p.commit, 16) >= 0 for p in projects)

    def test_short_hash_is_rejected(self, tmp_path):
        listing = tmp_path / "projects.txt"
        listing.write_text("demo  a/b  v1  abc123  src\n")
        with pytest.raises(ValueError, match="40-char"):
            load_projects(listing)

    def test_comments_and_excludes_are_parsed(self, tmp_path):
        listing = tmp_path / "projects.txt"
        listing.write_text("# yorum\n\ndemo  a/b  v1  " + "a" * 40 + "  pkg  v1 test  # not\n")
        (project,) = load_projects(listing)
        assert project.scope == "pkg"
        assert project.excludes == ("v1", "test")
