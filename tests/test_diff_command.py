"""`rlens diff` ve baseline/ratchet (v2.4 Aşama 5, `docs/02` §8).

Gerçek bir git deposu, iki commit. İkinci commit bir Extract Method yapar ve
yeni bir bulgu ekler (yedi parametreli fonksiyon: `too_many_params` kokusu ve
PARAMS eşik aşımı). Sabitlenenler:

* Kullanıcının ağacı ve HEAD'i değişmez; geçici worktree'ler kalmaz.
* Ratchet: kabul edilmiş bulgular (baseline, yoksa base tarafı) CI'ı kırmaz;
  yalnızca yeni olanlar kırar.
* LLM yok.
"""

from __future__ import annotations

import json
import shutil

import pytest
from apply_support import SHOP, git, make_repo
from typer.testing import CliRunner

from rlens.apply.worktree import ApplyError
from rlens.cli import app
from rlens.config import load_config
from rlens.diff.baseline import BASELINE_FILE, findings, write_baseline
from rlens.diff.compare import run_diff
from rlens.diff.git_refs import parse_range
from rlens.diff.pr_comment import pr_comment

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
runner = CliRunner()

SECOND = (
    SHOP.replace(
        """    def label(self):
        return "pricing"
""",
        """    def label(self):
        return self._name()

    def _name(self):
        return "pricing"
""",
    )
    + """

def ship(a, b, c, d, e, f, g):
    return a
"""
)


@pytest.fixture
def repo(tmp_path):
    root = make_repo(tmp_path)
    git(root, "tag", "v1")
    (root / "app" / "shop.py").write_text(SECOND, encoding="utf-8")
    git(root, "commit", "-qam", "second")
    return root


def diff(repo, spec="v1..HEAD", baseline=None):
    base, head = parse_range(spec)
    return run_diff(repo, base, head, load_config(search_from=repo), baseline=baseline)


class TestRange:
    def test_forms(self):
        assert parse_range("origin/main..HEAD") == ("origin/main", "HEAD")
        assert parse_range("v1..") == ("v1", "HEAD")

    def test_a_single_ref_is_refused(self):
        with pytest.raises(ApplyError, match="base..head"):
            parse_range("main")


class TestDiff:
    def test_metric_and_finding_deltas(self, repo):
        result = diff(repo)
        statuses = {e.qualified_name: e.status for e in result.delta.entities}
        assert statuses["app.shop:ship"] == "added"
        assert "smell too_many_params @ app.shop.ship" in result.new_findings
        assert "threshold app.shop:ship PARAMS" in result.new_findings
        assert result.accepted_from == "base"

    def test_refactorings_between_refs(self, repo):
        kinds = [(r.kind, r.target) for r in diff(repo).refactorings]
        assert ("extract_method", "Pricing._name") in kinds

    def test_the_user_tree_is_untouched_and_no_worktree_is_left(self, repo):
        head = git(repo, "rev-parse", "HEAD")
        diff(repo)
        assert git(repo, "rev-parse", "HEAD") == head
        assert git(repo, "status", "--porcelain") == ""
        assert len(git(repo, "worktree", "list").splitlines()) == 1

    def test_an_unknown_ref_is_an_error(self, repo):
        with pytest.raises(ApplyError, match="nope"):
            diff(repo, "nope..HEAD")


class TestRatchet:
    def test_a_baseline_accepts_existing_findings(self, repo):
        config = load_config(search_from=repo)
        from rlens.analysis.scanner import scan_project

        current = findings(scan_project(repo, config).to_dict(), config)
        path = write_baseline(repo, current)
        assert path.name == BASELINE_FILE
        result = diff(repo, baseline=path)
        assert result.accepted_from == "baseline"
        assert result.new_findings == []

    def test_a_fixed_finding_is_reported(self, repo):
        result = diff(repo, "HEAD..v1")
        assert "smell too_many_params @ app.shop.ship" in result.fixed_findings
        assert result.new_findings == []


class TestPrComment:
    def test_lists_what_a_reviewer_needs(self, repo):
        text = pr_comment(diff(repo))
        assert text.startswith("## RefactorLens")
        assert "New findings (2)" in text
        assert "`threshold app.shop:ship PARAMS`" in text
        assert "extract_method Pricing.label → Pricing._name" in text
        assert "behaviour tests" in text


class TestCli:
    def test_json(self, repo):
        result = runner.invoke(app, ["diff", "v1..HEAD", "--path", str(repo), "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["accepted_from"] == "base"
        assert len(payload["new_findings"]) == 2

    def test_fail_on_new_violation(self, repo):
        args = ["diff", "v1..HEAD", "--path", str(repo), "--fail-on", "new-violation"]
        assert runner.invoke(app, args).exit_code == 1
        assert runner.invoke(app, [*args[:4], "--fail-on", "none"]).exit_code == 0

    def test_baseline_update_then_the_ratchet_passes(self, repo):
        result = runner.invoke(app, ["baseline", "update", str(repo)])
        assert result.exit_code == 0, result.output
        payload = json.loads((repo / BASELINE_FILE).read_text(encoding="utf-8"))
        assert payload["schema_version"] == 1
        args = ["diff", "v1..HEAD", "--path", str(repo), "--fail-on", "new-violation"]
        assert runner.invoke(app, args).exit_code == 0

    def test_pr_comment_format(self, repo):
        result = runner.invoke(
            app, ["diff", "v1..HEAD", "--path", str(repo), "--format", "pr-comment"]
        )
        assert result.exit_code == 0, result.output
        assert result.stdout.startswith("## RefactorLens")
