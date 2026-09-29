"""`apply` altyapısı: worktree, patch doğrulama, davranış kapısı (v2.4 Aşama 0).

`docs/02` §2'nin güvenlik invariant'ları burada sabitlenir. En önemlisi:
**hiçbir testte kullanıcının branch'i, HEAD'i ya da çalışma ağacı değişmez.**
Her test gerçek bir git deposu kurar; git yoksa atlanır.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from rlens.apply.gate import run_gate
from rlens.apply.patch import apply_patch, touched_paths, validate_paths
from rlens.apply.worktree import (
    WORK_DIR,
    ApplyError,
    branch_name,
    create_worktree,
    discard,
    ensure_clean,
    repository_root,
)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")

ORIGINAL = "def total(items):\n    return sum(items)\n"
PATCHED = "def total(items):\n    return sum(list(items))\n"

GOOD_PATCH = """\
--- a/app/calc.py
+++ b/app/calc.py
@@ -1,2 +1,2 @@
 def total(items):
-    return sum(items)
+    return sum(list(items))
"""


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "app").mkdir(parents=True)
    (root / "app" / "calc.py").write_text(ORIGINAL, encoding="utf-8")
    (root / "app" / "other.py").write_text("x = 1\n", encoding="utf-8")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "initial")
    return root


def snapshot(root: Path) -> tuple[str, str, str, str]:
    """Kullanıcının durumu: HEAD, branch, `status`, hedef dosyanın içeriği."""
    return (
        git(root, "rev-parse", "HEAD"),
        git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        git(root, "status", "--porcelain"),
        (root / "app" / "calc.py").read_text(encoding="utf-8"),
    )


class TestRepository:
    def test_outside_a_repository_is_refused(self, tmp_path):
        with pytest.raises(ApplyError, match="not inside a git repository"):
            repository_root(tmp_path)

    def test_root_is_found_from_a_subdirectory(self, repo):
        assert repository_root(repo / "app") == repo.resolve()

    def test_modified_tracked_file_is_dirty(self, repo):
        (repo / "app" / "other.py").write_text("x = 2\n", encoding="utf-8")
        with pytest.raises(ApplyError, match="uncommitted changes.*app/other.py"):
            ensure_clean(repo)

    def test_untracked_file_is_dirty(self, repo):
        (repo / "notes.txt").write_text("todo\n", encoding="utf-8")
        with pytest.raises(ApplyError, match="notes.txt"):
            ensure_clean(repo)

    def test_clean_tree_passes(self, repo):
        ensure_clean(repo)


class TestWorktree:
    def test_branch_name_is_valid_for_git(self):
        name = branch_name("20260929-120000", "src.app.orders:Widget")
        assert name == "rlens/20260929-120000/src.app.orders-Widget"

    def test_worktree_is_isolated_and_removable(self, repo):
        before = snapshot(repo)
        work = create_worktree(repo, "r1", "app.calc:total")
        assert work.path == repo.resolve() / WORK_DIR / "r1"
        assert (work.path / "app" / "calc.py").read_text(encoding="utf-8") == ORIGINAL
        assert snapshot(repo) == before
        # İkinci koşu kirli ağaç görmemeli: çalışma dizini yerel olarak dışlanır.
        ensure_clean(repo)
        discard(work)
        assert not work.path.exists()
        assert work.branch not in git(repo, "branch", "--list")
        assert snapshot(repo) == before

    def test_the_exclude_entry_is_written_once(self, repo):
        discard(create_worktree(repo, "r1", "t"))
        discard(create_worktree(repo, "r2", "t"))
        exclude = Path(git(repo, "rev-parse", "--git-common-dir"))
        if not exclude.is_absolute():
            exclude = repo / exclude
        lines = (exclude / "info" / "exclude").read_text(encoding="utf-8").splitlines()
        assert lines.count(f"/{WORK_DIR}/") == 1


class TestPatch:
    def test_touched_paths(self):
        assert touched_paths(GOOD_PATCH) == ["app/calc.py"]

    def test_new_file_is_a_touched_path(self):
        patch = "--- /dev/null\n+++ b/app/new.py\n@@ -0,0 +1 @@\n+y = 2\n"
        assert touched_paths(patch) == ["app/new.py"]

    def test_a_patch_with_no_file_is_refused(self):
        with pytest.raises(ApplyError, match="no file"):
            validate_paths(touched_paths("just prose, no diff\n"), {"app/calc.py"})

    def test_a_file_outside_the_allowed_set_is_refused(self):
        with pytest.raises(ApplyError, match="may not change: app/other.py"):
            validate_paths(["app/calc.py", "app/other.py"], {"app/calc.py"})

    def test_path_escape_is_refused(self):
        with pytest.raises(ApplyError, match="outside the repository"):
            validate_paths(["../evil.py"], {"../evil.py"})

    def test_patch_applies_in_the_worktree_only(self, repo):
        before = snapshot(repo)
        work = create_worktree(repo, "r1", "t")
        apply_patch(work, GOOD_PATCH)
        assert (work.path / "app" / "calc.py").read_text(encoding="utf-8") == PATCHED
        assert snapshot(repo) == before
        discard(work)

    def test_a_patch_that_does_not_apply_is_refused(self, repo):
        stale = GOOD_PATCH.replace("return sum(items)", "return sum(values)")
        work = create_worktree(repo, "r1", "t")
        with pytest.raises(ApplyError, match="does not apply"):
            apply_patch(work, stale)
        assert (work.path / "app" / "calc.py").read_text(encoding="utf-8") == ORIGINAL
        discard(work)


def python(code: str) -> str:
    return f'"{sys.executable}" -c "{code}"'


class TestGate:
    def test_a_passing_command(self, repo):
        result = run_gate(python("import sys; sys.exit(0)"), repo, timeout=60)
        assert (result.level, result.passed, result.exit_code) == (1, True, 0)

    def test_a_failing_command_keeps_its_output(self, repo):
        result = run_gate(python("print('boom'); raise SystemExit(3)"), repo, timeout=60)
        assert (result.passed, result.exit_code) == (False, 3)
        assert "boom" in result.output_tail

    def test_a_timeout_fails_the_gate(self, repo):
        result = run_gate(python("import time; time.sleep(30)"), repo, timeout=1)
        assert (result.passed, result.timed_out) == (False, True)

    def test_the_command_runs_in_the_given_directory(self, repo):
        work = create_worktree(repo, "r1", "t")
        apply_patch(work, GOOD_PATCH)
        check = python(
            "import pathlib, sys; "
            "sys.exit(0 if 'list(items)' in pathlib.Path('app/calc.py').read_text() else 1)"
        )
        assert run_gate(check, work.path, timeout=60).passed
        assert not run_gate(check, repo, timeout=60).passed
        discard(work)
