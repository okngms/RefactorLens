"""`apply` uçtan uca, sahte sağlayıcıyla (v2.4 Aşama 1).

Gerçek bir git deposu, kendi testleri olan küçük bir proje ve sırayla hazır
yanıt dönen bir sağlayıcı. Her senaryoda kullanıcının HEAD'i, branch'i,
`status`'u ve dosyası değişmez (`docs/02` §2); başarıda sonuç bir branch'tir,
başarısızlıkta hiç iz kalmaz.
"""

from __future__ import annotations

import shutil

import pytest
from apply_support import (
    BROKEN_SHOP,
    DELETED_SHOP,
    IMPROVED_SHOP,
    SHOP,
    TARGET,
    FakeProvider,
    advice,
    diff_for,
    git,
    make_repo,
    reply,
    snapshot,
)

from rlens.apply.runner import BROKEN, REJECTED, SUSPICIOUS, run_apply
from rlens.apply.worktree import WORK_DIR, ApplyError
from rlens.config import load_config
from rlens.verify.diff import IMPROVED

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path)


def run(repo, provider, **kwargs):
    config = load_config(search_from=repo)
    return run_apply(repo, kwargs.pop("doc", advice()), TARGET, 1, config, provider, **kwargs)


class TestSuccess:
    def test_an_improving_patch_lands_on_a_branch(self, repo):
        before = snapshot(repo)
        result = run(repo, FakeProvider(reply(diff_for(IMPROVED_SHOP))))
        assert result.outcome == IMPROVED
        assert result.gate.passed
        assert snapshot(repo) == before
        assert not (repo / WORK_DIR / result.run_id).exists()
        branch_file = git(repo, "show", f"{result.branch}:app/shop.py")
        assert branch_file.strip() == IMPROVED_SHOP.strip()
        assert result.predictions["hits"] == 1

    def test_the_commit_holds_only_the_patched_files(self, repo):
        """Testlerin worktree'de ürettiği artıklar (`__pycache__`) commit'e girmez.

        İlk gerçek koşuda `git add -A` 15 `.pyc` dosyasını branch'e koydu;
        o depoda `__pycache__` `.gitignore`'da değildi.
        """
        result = run(repo, FakeProvider(reply(diff_for(IMPROVED_SHOP))))
        changed = git(repo, "diff", "--name-only", f"HEAD...{result.branch}").splitlines()
        assert changed == ["app/shop.py"]

    def test_a_suspicious_change_is_labelled(self, repo):
        result = run(repo, FakeProvider(reply(diff_for(DELETED_SHOP))))
        assert result.outcome == SUSPICIOUS
        assert result.branch is not None

    def test_one_repair_is_allowed(self, repo):
        provider = FakeProvider("no diff at all", reply(diff_for(IMPROVED_SHOP)))
        result = run(repo, provider)
        assert result.outcome == IMPROVED
        assert result.attempts == 2
        assert "no ```diff block" in provider.prompts[1]


class TestFailure:
    def test_a_broken_patch_leaves_no_trace(self, repo):
        before = snapshot(repo)
        result = run(repo, FakeProvider(reply(diff_for(BROKEN_SHOP))))
        assert result.outcome == BROKEN
        assert not result.gate.passed
        assert result.branch is None
        assert snapshot(repo) == before
        assert "rlens/" not in git(repo, "branch", "--list")
        assert not (repo / WORK_DIR / result.run_id).exists()

    def test_keep_failed_keeps_the_worktree(self, repo):
        (repo / "rlens.yaml").write_text(
            (repo / "rlens.yaml").read_text(encoding="utf-8") + "apply:\n  keep_failed: true\n",
            encoding="utf-8",
        )
        git(repo, "commit", "-qam", "keep failed")
        result = run(repo, FakeProvider(reply(diff_for(BROKEN_SHOP))))
        assert result.outcome == BROKEN
        assert (repo / WORK_DIR / result.run_id).exists()
        assert result.branch is not None

    def test_two_rejections_end_the_run(self, repo):
        before = snapshot(repo)
        result = run(repo, FakeProvider("nothing", "still nothing"))
        assert result.outcome == REJECTED
        assert result.attempts == 2
        assert len(result.rejections) == 2
        assert result.branch is None
        assert snapshot(repo) == before

    def test_a_forbidden_file_is_rejected(self, repo):
        sneaky = diff_for("x = 1\n", path="app/__init__.py", old="")
        result = run(repo, FakeProvider(reply(sneaky), reply(sneaky)))
        assert result.outcome == REJECTED
        assert "may not change: app/__init__.py" in result.rejections[0]


class TestPreconditions:
    def test_no_test_command_refuses(self, repo):
        (repo / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        git(repo, "commit", "-qam", "no tests")
        with pytest.raises(ApplyError, match="tests.command"):
            run(repo, FakeProvider())

    def test_unknown_target_refuses(self, repo):
        config = load_config(search_from=repo)
        with pytest.raises(ApplyError, match="no advice for app.shop:Nope"):
            run_apply(repo, advice(), "app.shop:Nope", 1, config, FakeProvider())

    def test_missing_suggestion_refuses(self, repo):
        config = load_config(search_from=repo)
        with pytest.raises(ApplyError, match="has 1 suggestion"):
            run_apply(repo, advice(), TARGET, 2, config, FakeProvider())

    def test_dirty_tree_refuses_before_any_call(self, repo):
        (repo / "app" / "shop.py").write_text(SHOP + "\n# edit\n", encoding="utf-8")
        provider = FakeProvider()
        with pytest.raises(ApplyError, match="uncommitted"):
            run(repo, provider)
        assert provider.prompts == []


class TestOutputLimit:
    def test_a_cut_off_reply_is_rejected_without_a_repair(self, repo):
        from rlens.providers.base import ProviderTruncated

        class Cutting(FakeProvider):
            def generate(self, system, user, config, temperature):
                self.prompts.append(user)
                self.limit = config.max_output_tokens
                raise ProviderTruncated("stopped at the output limit", partial="```diff\n--- a/x")

        provider = Cutting()
        before = snapshot(repo)
        result = run(repo, provider)
        assert result.outcome == REJECTED
        assert result.attempts == 1
        assert "cut off at the model's output limit" in result.rejections[0]
        assert "apply.max_output_tokens" in result.rejections[0]
        assert result.replies == ["```diff\n--- a/x"]
        assert provider.limit == 16384
        assert snapshot(repo) == before

    def test_a_failed_repair_call_keeps_the_first_attempt(self, repo):
        from rlens.providers.base import ProviderError

        class Failing(FakeProvider):
            def generate(self, system, user, config, temperature):
                self.prompts.append(user)
                if len(self.prompts) == 2:
                    raise ProviderError("HTTP 413: request too large")
                return "no diff here"

        result = run(repo, Failing())
        assert result.outcome == REJECTED
        assert result.attempts == 2
        assert result.replies == ["no diff here"]
        assert "no ```diff block" in result.rejections[0]
        assert "repair request failed: HTTP 413" in result.rejections[1]
