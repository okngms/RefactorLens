"""Karakterizasyon testleri: istem, ayrıştırma, ön doğrulama (v2.4 Aşama 2).

Sabitlenenler (`docs/02` §3, seviye 2):

* Testler değişmemiş kodda koşulur; geçmeyen test fonksiyonu atılır, kalanlar
  yeniden koşulur ve ikinci koşuda da geçmek zorundadır (kararsız test kapı
  olamaz). Geçme oranı raporlanır.
* Dosya derlenemiyor ya da hiçbir test geçmiyorsa kapı yoktur (`kept == 0`).
* Testler `chartests.python` ile koşar; rlens'in kendi yorumlayıcısı değil.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from rlens.apply.worktree import ApplyError
from rlens.chartests.generator import (
    CHARTESTS_DIR,
    SYSTEM_INSTRUCTION,
    ChartestsFormatError,
    build_chartests_prompt,
    parse_tests,
    run_chartests,
    validate,
)

SOURCE = """class Counter:
    def __init__(self):
        self.value = 0

    def bump(self, by=1):
        if by <= 0:
            raise ValueError("by must be positive")
        self.value += by
        return self.value
"""


@pytest.fixture
def project(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "counter.py").write_text(SOURCE, encoding="utf-8")
    return tmp_path


def check(project, code, *, timeout=120):
    return validate(code, project, python=sys.executable, timeout=timeout)


GOOD = """from pkg.counter import Counter


def test_bump_default():
    assert Counter().bump() == 1


def test_bump_rejects_zero():
    import pytest

    with pytest.raises(ValueError):
        Counter().bump(0)
"""


class TestPrompt:
    @pytest.fixture
    def prompt(self):
        return build_chartests_prompt("pkg.counter:Counter", "pkg/counter.py", SOURCE, 3)

    def test_carries_the_import_and_the_source(self, prompt):
        assert "from pkg.counter import Counter" in prompt
        assert "def bump(self, by=1):" in prompt
        assert "up to 3" in prompt

    def test_asks_for_todays_behaviour_not_correctness(self):
        assert "what the code does today" in SYSTEM_INSTRUCTION
        assert "even if it looks wrong" in SYSTEM_INSTRUCTION
        assert "```python" in SYSTEM_INSTRUCTION

    def test_carries_no_measurement(self, prompt):
        for word in ("threshold", "LCOM4", "WMC", "[WARN]", "expected_effect"):
            assert word not in SYSTEM_INSTRUCTION + prompt


class TestParse:
    def test_one_python_block(self):
        assert parse_tests(f"Here.\n```python\n{GOOD}```\n") == GOOD

    def test_no_block(self):
        with pytest.raises(ChartestsFormatError, match="no ```python block"):
            parse_tests(GOOD)

    def test_two_blocks(self):
        with pytest.raises(ChartestsFormatError, match="2 ```python blocks"):
            parse_tests(f"```python\n{GOOD}```\n```python\n{GOOD}```")


class TestValidate:
    def test_all_passing_tests_are_kept(self, project):
        result = check(project, GOOD)
        assert (result.generated, result.kept, result.dropped) == (2, 2, [])
        assert result.pass_rate == 1.0
        assert (project / CHARTESTS_DIR / "test_characterization.py").is_file()

    def test_a_failing_test_is_dropped_and_the_rest_kept(self, project):
        code = GOOD + "\n\ndef test_wrong_guess():\n    assert Counter().bump(2) == 3\n"
        result = check(project, code)
        assert (result.generated, result.kept, result.dropped) == (3, 2, ["test_wrong_guess"])
        assert "test_wrong_guess" not in result.code
        assert "def test_bump_default" in result.code
        assert result.pass_rate == 0.6667

    def test_one_failing_parameter_drops_the_whole_function(self, project):
        code = GOOD + (
            "\n\nimport pytest\n\n\n@pytest.mark.parametrize('by, out', [(1, 1), (2, 3)])\n"
            "def test_param(by, out):\n    assert Counter().bump(by) == out\n"
        )
        result = check(project, code)
        assert result.dropped == ["test_param"]
        assert "parametrize" not in result.code

    def test_a_test_that_passes_only_once_is_dropped(self, project):
        """Kararsız test kapı olamaz: ikinci koşuda düşen test de atılır."""
        code = GOOD + (
            "\n\ndef test_only_once():\n"
            "    from pathlib import Path\n"
            "    marker = Path(__file__).with_name('marker')\n"
            "    assert not marker.exists()\n"
            "    marker.write_text('x')\n"
        )
        result = check(project, code)
        assert result.dropped == ["test_only_once"]
        assert result.kept == 2

    def test_an_import_error_keeps_nothing(self, project):
        result = check(project, "from pkg.nothing import X\n\n\ndef test_x():\n    assert X\n")
        assert (result.generated, result.kept) == (1, 0)

    def test_a_syntax_error_keeps_nothing(self, project):
        result = check(project, "def test_x(:\n    pass\n")
        assert result.kept == 0
        assert "does not parse" in result.reason

    def test_no_test_function_keeps_nothing(self, project):
        result = check(project, "x = 1\n")
        assert (result.generated, result.kept) == (0, 0)

    def test_a_python_that_cannot_run_is_reported(self, project):
        with pytest.raises(ApplyError, match="chartests.python"):
            validate(GOOD, project, python=str(project / "no-python.exe"), timeout=30)


class TestGate:
    def test_level_two_passes_then_fails_after_a_behaviour_change(self, project):
        result = check(project, GOOD)
        assert run_chartests(project, python=sys.executable, timeout=120).passed
        changed = SOURCE.replace("return self.value", "return self.value + 1")
        (project / "pkg" / "counter.py").write_text(changed, encoding="utf-8")
        gate = run_chartests(project, python=sys.executable, timeout=120)
        assert (gate.level, gate.passed) == (2, False)
        assert result.kept == 2

    def test_the_file_lives_where_the_scanner_does_not_look(self):
        assert CHARTESTS_DIR.startswith(".")
        assert Path(CHARTESTS_DIR).name == CHARTESTS_DIR
