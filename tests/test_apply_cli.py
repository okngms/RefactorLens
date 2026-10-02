"""`rlens apply` komut yüzeyi (v2.4 Aşama 1).

Sağlayıcı sahtesiyle değiştirilir; depo ve proje `apply_support` ile kurulur.
"""

from __future__ import annotations

import json
import shutil

import pytest
from apply_support import (
    BROKEN_SHOP,
    IMPROVED_SHOP,
    TARGET,
    FakeProvider,
    advice,
    diff_for,
    git,
    make_repo,
    reply,
    snapshot,
)
from typer.testing import CliRunner

from rlens.cli import app

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
runner = CliRunner()


def flat(text: str) -> str:
    return " ".join(text.split())


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path)


@pytest.fixture
def advice_file(tmp_path):
    path = tmp_path / "advice.json"
    path.write_text(json.dumps(advice()), encoding="utf-8")
    return path


def invoke(repo, advice_file, monkeypatch, provider, *extra):
    monkeypatch.setattr("rlens.cli.get_provider", lambda config: provider)
    out = repo.parent / "reports"
    return runner.invoke(
        app,
        ["apply", str(repo), "--advice", str(advice_file), "-o", str(out), *extra],
    ), out


class TestApplyCommand:
    def test_success_prints_the_branch_and_writes_a_report(self, repo, advice_file, monkeypatch):
        before = snapshot(repo)
        result, out = invoke(
            repo, advice_file, monkeypatch, FakeProvider(reply(diff_for(IMPROVED_SHOP)))
        )
        assert result.exit_code == 0, result.output
        output = flat(result.output)
        assert "outcome: improved" in output
        assert "rlens/" in output
        assert "never merges" in output
        payload = json.loads(next(out.glob("apply-*.json")).read_text(encoding="utf-8"))
        assert payload["schema_version"] == 1
        assert payload["outcome"] == "improved"
        assert payload["branch"].startswith("rlens/")
        assert list(out.glob("apply-*.md"))
        assert snapshot(repo) == before

    def test_a_broken_patch_says_so(self, repo, advice_file, monkeypatch):
        result, _ = invoke(
            repo, advice_file, monkeypatch, FakeProvider(reply(diff_for(BROKEN_SHOP)))
        )
        assert result.exit_code == 0, result.output
        output = flat(result.output)
        assert "outcome: broken" in output
        assert "no branch was kept" in output

    def test_dry_run_calls_nothing_and_opens_no_worktree(self, repo, advice_file, monkeypatch):
        def refuse(config):
            raise AssertionError("--dry-run must not build a provider")

        monkeypatch.setattr("rlens.cli.get_provider", refuse)
        result = runner.invoke(app, ["apply", str(repo), "--advice", str(advice_file), "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "Replace the branches with a lookup table" in result.output
        assert "class Pricing:" in result.output
        assert "rlens/" not in git(repo, "branch", "--list")

    def test_target_is_required_when_the_advice_has_several(self, repo, tmp_path, monkeypatch):
        doc = advice()
        doc["advices"].append({"target": "app.shop:Other", "suggestions": []})
        path = tmp_path / "two.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        result, _ = invoke(repo, path, monkeypatch, FakeProvider())
        assert result.exit_code == 1
        assert f"--target ({TARGET}, app.shop:Other)" in flat(result.output)

    def test_precondition_errors_exit_one(self, repo, advice_file, monkeypatch):
        (repo / "app" / "shop.py").write_text("x = 1\n", encoding="utf-8")
        result, _ = invoke(repo, advice_file, monkeypatch, FakeProvider())
        assert result.exit_code == 1
        assert "uncommitted changes" in flat(result.output)
