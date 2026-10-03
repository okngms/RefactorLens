"""GitHub Action (`action/action.yml`, v2.4 Aşama 5).

Action GitHub dışında koşulamaz; ama karşılaştırma adımının betiği girdileri
yalnızca env'den aldığı için yerelde aynen çalıştırılır: gerçek bir git
deposunda yorum dosyası üretilir, `GITHUB_OUTPUT`'a çıkış kodu yazılır ve
ratchet yeni bulguda 1 döndürür.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from apply_support import SHOP, git, make_repo

ROOT = Path(__file__).resolve().parent.parent
ACTION = yaml.safe_load((ROOT / "action" / "action.yml").read_text(encoding="utf-8"))


def step(step_id: str) -> dict:
    return next(s for s in ACTION["runs"]["steps"] if s.get("id") == step_id)


class TestDefinition:
    def test_inputs(self):
        assert set(ACTION["inputs"]) >= {"path", "base", "fail-on", "comment", "version"}
        assert ACTION["inputs"]["fail-on"]["default"] == "none"

    def test_the_diff_script_reads_only_its_environment(self):
        assert "${{" not in step("diff")["run"]

    def test_the_options_it_uses_exist(self):
        from typer.testing import CliRunner

        from rlens.cli import app

        help_text = CliRunner().invoke(app, ["diff", "--help"]).output
        for option in ("--path", "--format", "--fail-on"):
            assert option in help_text

    def test_the_gate_runs_after_the_comment(self):
        names = [s.get("name") for s in ACTION["runs"]["steps"]]
        assert names.index("Comment on the pull request") < names.index("Apply the gate")


@pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None, reason="needs git and bash"
)
class TestDiffScript:
    @pytest.fixture
    def repo(self, tmp_path):
        root = make_repo(tmp_path)
        git(root, "tag", "base")
        (root / "app" / "shop.py").write_text(
            SHOP + "\n\ndef ship(a, b, c, d, e, f, g):\n    return a\n", encoding="utf-8"
        )
        git(root, "commit", "-qam", "new finding")
        return root

    def run(self, repo, tmp_path, fail_on):
        script = tmp_path / "diff.sh"
        script.write_text(step("diff")["run"], encoding="utf-8", newline="\n")
        output = tmp_path / "output.txt"
        scripts = Path(sys.executable).parent
        env = {
            **os.environ,
            "PATH": str(scripts) + os.pathsep + os.environ["PATH"],
            "RLENS_BASE": "base",
            "RLENS_PATH": ".",
            "RLENS_FAIL_ON": fail_on,
            "RUNNER_TEMP": str(tmp_path),
            "GITHUB_OUTPUT": str(output),
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
            "PYTHONIOENCODING": "utf-8",
        }
        subprocess.run(
            [shutil.which("bash"), str(script)], cwd=repo, env=env, check=True, capture_output=True
        )
        values = dict(line.split("=", 1) for line in output.read_text().splitlines())
        return values, Path(values["comment"]).read_text(encoding="utf-8")

    def test_comment_and_ratchet(self, repo, tmp_path):
        values, comment = self.run(repo, tmp_path, "new-violation")
        assert values["exit-code"] == "1"
        assert comment.startswith("## RefactorLens")
        assert "`smell too_many_params @ app.shop.ship`" in comment

    def test_fail_on_none_passes(self, repo, tmp_path):
        values, _ = self.run(repo, tmp_path, "none")
        assert values["exit-code"] == "0"
