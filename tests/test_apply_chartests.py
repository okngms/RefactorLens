"""`apply` testsiz projede: davranış kapısı seviye 2 (v2.4 Aşama 2).

Fikstür `examples/untested_project`'in git kopyası; `tests.command` yok.
Sahte sağlayıcı önce karakterizasyon testlerini, sonra patch'i döndürür.
Kabul ölçütü (`docs/02` §11): `apply` kapı 2 ile çalışıyor ve üretilen
testlerin mevcut kodda geçme oranı raporlanıyor.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
from apply_support import FakeProvider, diff_for, git, reply
from typer.testing import CliRunner

from rlens.apply.runner import BROKEN, NO_GATE, run_apply
from rlens.apply.worktree import WORK_DIR, ApplyError
from rlens.chartests.generator import CHARTESTS_DIR
from rlens.cli import app
from rlens.config import load_config
from rlens.verify.diff import IMPROVED

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")

FIXTURE = Path(__file__).resolve().parent.parent / "examples" / "untested_project"
TARGET = "inventory.stock:Stock"
ORIGINAL = (FIXTURE / "inventory" / "stock.py").read_text(encoding="utf-8")

CHARTESTS = """from inventory.stock import Stock
import pytest


def test_add_returns_the_new_quantity():
    stock = Stock()
    assert stock.add("bolt", 3, 0.5) == 3
    assert stock.add("bolt", 2, 0.5) == 5


def test_remove_everything_deletes_the_item():
    stock = Stock()
    stock.add("nut", 2, 1.0)
    assert stock.remove("nut", 2) == 0
    assert stock.quantity("nut") == 0


def test_low_items_are_sorted():
    stock = Stock()
    stock.add("b", 1, 1.0)
    stock.add("a", 1, 1.0)
    stock.add("c", 9, 1.0)
    assert stock.low_items(5) == ["a", "b"]


def test_report_lists_and_totals():
    stock = Stock()
    stock.add("bolt", 2, 0.5)
    assert stock.report() == "bolt: 2 x 0.50 = 1.00\\ntotal: 1.00"


def test_a_wrong_guess():
    assert Stock().report() == "nothing"
"""

#: Davranışı koruyan değişiklik: `report`'taki ölü dal (`remove` sıfırlanan
#: kaydı siler, miktar hiç 0 olmaz). CC 4→3. Kavrayışa çevirmek CC'yi
#: değiştirmezdi: kavrayıştaki `for` ve `if` de sayılır.
IMPROVED_STOCK = ORIGINAL.replace("            if qty == 0:\n                continue\n", "")
#: Davranışı bozan değişiklik: `low_items` sıralamayı kaybetti.
BROKEN_STOCK = ORIGINAL.replace("        return sorted(result)", "        return result")


def advice():
    return {
        "advices": [
            {
                "target": TARGET,
                "suggestions": [
                    {
                        "title": "Drop the dead branch in report",
                        "sketch": "Remove the qty == 0 check in report; "
                        "remove() deletes empty items.",
                        "expected_effect": [{"metric": "WMC", "direction": "down"}],
                    }
                ],
            }
        ]
    }


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "untested"
    shutil.copytree(FIXTURE, root, ignore=shutil.ignore_patterns("__pycache__", "reports"))
    config = (root / "rlens.yaml").read_text(encoding="utf-8")
    python = sys.executable.replace("\\", "/")
    (root / "rlens.yaml").write_text(config + f"  python: '{python}'\n", encoding="utf-8")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "fixture")
    return root


def run(repo, provider):
    return run_apply(repo, advice(), TARGET, 1, load_config(search_from=repo), provider)


def test_the_fixture_has_no_tests_and_its_gold_values():
    """WMC 18 = add 3 + remove 4 + quantity 2 + total_value 2 + low_items 3 + report 4."""
    from rlens.analysis.scanner import scan_project

    assert not list(FIXTURE.rglob("test_*.py"))
    report = scan_project(FIXTURE, load_config(search_from=FIXTURE))
    (stock,) = list(report.iter_classes())
    assert (stock.nom, stock.wmc, stock.lcom4) == (6, 18, 1)


class TestLevelTwo:
    def test_an_improving_patch_passes_the_characterization_gate(self, repo):
        provider = FakeProvider(
            f"```python\n{CHARTESTS}```",
            reply(diff_for(IMPROVED_STOCK, "inventory/stock.py", ORIGINAL)),
        )
        result = run(repo, provider)
        assert result.outcome == IMPROVED
        assert (result.gate.level, result.gate.passed) == (2, True)
        assert result.chartests["generated"] == 5
        assert result.chartests["kept"] == 4
        assert result.chartests["dropped"] == ["test_a_wrong_guess"]
        assert result.chartests["pass_rate"] == 0.8
        changed = git(repo, "diff", "--name-only", f"HEAD...{result.branch}").splitlines()
        assert changed == ["inventory/stock.py"]

    def test_the_tests_are_written_before_the_patch_is_asked_for(self, repo):
        provider = FakeProvider(
            f"```python\n{CHARTESTS}```",
            reply(diff_for(IMPROVED_STOCK, "inventory/stock.py", ORIGINAL)),
        )
        run(repo, provider)
        assert "Import it with: from inventory.stock import Stock" in provider.prompts[0]
        assert "## Suggestion to apply" in provider.prompts[1]

    def test_a_behaviour_change_is_caught(self, repo):
        provider = FakeProvider(
            f"```python\n{CHARTESTS}```",
            reply(diff_for(BROKEN_STOCK, "inventory/stock.py", ORIGINAL)),
        )
        result = run(repo, provider)
        assert result.outcome == BROKEN
        assert (result.gate.level, result.gate.passed) == (2, False)
        assert "test_low_items_are_sorted" in result.gate.output_tail
        assert result.branch is None
        assert not (repo / WORK_DIR / result.run_id).exists()

    def test_no_passing_test_means_no_gate_and_no_patch_request(self, repo):
        provider = FakeProvider("```python\ndef test_x():\n    assert False\n```")
        result = run(repo, provider)
        assert result.outcome == NO_GATE
        assert result.chartests["kept"] == 0
        assert len(provider.prompts) == 1
        assert result.branch is None

    def test_the_user_tree_never_sees_the_tests(self, repo):
        provider = FakeProvider(
            f"```python\n{CHARTESTS}```",
            reply(diff_for(IMPROVED_STOCK, "inventory/stock.py", ORIGINAL)),
        )
        run(repo, provider)
        assert not (repo / CHARTESTS_DIR).exists()
        assert git(repo, "status", "--porcelain") == ""

    def test_disabled_and_no_test_command_refuses(self, repo):
        text = (repo / "rlens.yaml").read_text(encoding="utf-8")
        (repo / "rlens.yaml").write_text(
            text.replace("enabled_when_no_tests: true", "enabled_when_no_tests: false"),
            encoding="utf-8",
        )
        git(repo, "commit", "-qam", "disable")
        with pytest.raises(ApplyError, match="tests.command.*chartests.enabled_when_no_tests"):
            run(repo, FakeProvider())


class TestChartestsCommand:
    def test_writes_the_kept_tests(self, repo, monkeypatch):
        provider = FakeProvider(f"```python\n{CHARTESTS}```")
        monkeypatch.setattr("rlens.cli.get_provider", lambda config: provider)
        out = repo.parent / "out"
        result = CliRunner().invoke(
            app, ["chartests", str(repo), "--target", TARGET, "-o", str(out)]
        )
        assert result.exit_code == 0, result.output
        output = " ".join(result.output.split())
        assert "4 of 5 tests pass on the current code (80%)" in output
        written = next(out.glob("chartests-*.py")).read_text(encoding="utf-8")
        assert "test_a_wrong_guess" not in written
        assert json.loads(next(out.glob("chartests-*.json")).read_text("utf-8"))["kept"] == 4
        # Yalnızca aracın kendi önbelleği; kaynak ağacı değişmez.
        status = git(repo, "status", "--porcelain").splitlines()
        assert [line for line in status if ".rlens-cache/" not in line] == []

    def test_dry_run_prints_the_request(self, repo, monkeypatch):
        def refuse(config):
            raise AssertionError("--dry-run must not build a provider")

        monkeypatch.setattr("rlens.cli.get_provider", refuse)
        result = CliRunner().invoke(app, ["chartests", str(repo), "--target", TARGET, "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "from inventory.stock import Stock" in result.output
        assert "def low_items(self, limit):" in result.output
