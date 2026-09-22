"""v2.2 §3: anotasyon kapsamı ölçümü (`experiments/hardening/annotations.py`).

Ön kayıttaki çürütme koşulları (`annotation-coverage.md` §9) burada sabitlenir;
betik sonuçları görmeden önce yazıldı.
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from annotations import (  # noqa: E402
    ProjectCounts,
    has_py_typed,
    refutations,
    summarise,
)


def _project(coverage, py_typed, eligible=True, mismatches=0):
    return {
        "coverage": coverage,
        "py_typed": py_typed,
        "eligible": eligible,
        "cam_mismatches": mismatches,
    }


class TestCounts:
    def test_function_buckets(self):
        counts = ProjectCounts()
        for source in (
            "def full(a: int) -> int: pass",
            "def none(a, b): pass",
            "def half(a: int, b): pass",
            "def empty(): pass",
        ):
            counts.add_function(ast.parse(source).body[0], is_method=False)
        summary = summarise(counts)
        # Yuvalar: 1 + 2 + 2 = 5, annotation'lı 1 + 0 + 1 = 2 → 0.4
        assert summary["coverage"] == 0.4
        assert summary["with_slots"] == 3
        assert summary["fully_annotated"] == 0.3333
        assert summary["unannotated"] == 0.3333
        # Dönüş: 4 fonksiyonun 1'i
        assert summary["returns"] == 0.25
        assert summary["eligible"] is False  # 3 < MIN_FUNCTIONS


class TestRefutations:
    def test_typed_projects_clearly_higher_is_not_rejected(self):
        projects = {
            "t1": _project(0.9, True),
            "t2": _project(0.8, True),
            "u1": _project(0.1, False),
            "u2": _project(0.2, False),
            "u3": _project(0.3, False),
        }
        result = refutations(projects)
        assert result["overall_median"] == 0.3
        assert (result["a"], result["b"], result["c"]) == (False, False, False)
        assert result["rejected"] is False

    def test_a_typed_median_not_higher(self):
        projects = {"t": _project(0.2, True), "u": _project(0.5, False)}
        assert refutations(projects)["a"] is True

    def test_b_too_few_typed_projects_above_the_overall_median(self):
        # Genel medyan 0.5; py.typed 5 projeden 3'ü üstünde (%60 < %80).
        projects = {
            **{f"t{i}": _project(v, True) for i, v in enumerate([0.9, 0.8, 0.7, 0.2, 0.1])},
            **{f"u{i}": _project(v, False) for i, v in enumerate([0.5, 0.4, 0.3, 0.6])},
        }
        result = refutations(projects)
        assert result["py_typed_above_overall"] == 3
        assert result["b"] is True
        assert result["rejected"] is True

    def test_c_any_cam_mismatch_rejects(self):
        projects = {
            "t": _project(0.9, True),
            "u": _project(0.1, False, mismatches=1),
        }
        assert refutations(projects)["c"] is True

    def test_ineligible_projects_are_left_out_of_a_and_b(self):
        projects = {
            "t": _project(0.9, True),
            "u": _project(0.1, False),
            "small": _project(0.0, True, eligible=False),
        }
        result = refutations(projects)
        assert result["py_typed_projects"] == 1


class TestPyTyped:
    def test_found_outside_excluded_dirs(self, tmp_path):
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "py.typed").write_text("")
        assert has_py_typed(tmp_path, ["tests/"]) is True

    def test_only_inside_excluded_dirs(self, tmp_path):
        (tmp_path / "tests" / "fixture").mkdir(parents=True)
        (tmp_path / "tests" / "fixture" / "py.typed").write_text("")
        assert has_py_typed(tmp_path, ["tests/"]) is False

    def test_absent(self, tmp_path):
        assert has_py_typed(tmp_path, []) is False
