"""Patch uygulayıcısı: birebir içerik eşleşmesi (v2.4 Aşama 1).

İlk gerçek koşuda model iki denemede de hunk başlığını satır numarasız
yazdı (`@@`) ve `git apply` patch'i konumlandıramadı. Uygulayıcı her hunk'ın
kaldırılan ve korunan satırlarını dosyada birebir arar; numaralar yalnızca
birden fazla eşleşme olduğunda seçim için kullanılır. Eşleşme yoksa ya da
belirsizse reddedilir; hiçbir dosya yarım değişmez.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rlens.apply.patch import apply_to_directory, touched_paths
from rlens.apply.worktree import ApplyError

ORIGINAL = (
    "def total(items):\n    return sum(items)\n\n\ndef count(items):\n    return len(items)\n"
)


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "calc.py").write_text(ORIGINAL, encoding="utf-8", newline="")
    return tmp_path


def read(tree: Path, name: str = "app/calc.py") -> str:
    return (tree / name).read_bytes().decode("utf-8")


class TestLocating:
    def test_a_hunk_without_line_numbers(self, tree):
        patch = (
            "--- a/app/calc.py\n+++ b/app/calc.py\n@@\n"
            " def total(items):\n-    return sum(items)\n+    return sum(list(items))\n"
        )
        apply_to_directory(tree, patch)
        assert "sum(list(items))" in read(tree)

    def test_wrong_line_numbers_are_tolerated(self, tree):
        patch = (
            "--- a/app/calc.py\n+++ b/app/calc.py\n@@ -40,2 +40,2 @@\n"
            " def count(items):\n-    return len(items)\n+    return len(list(items))\n"
        )
        apply_to_directory(tree, patch)
        assert read(tree).endswith("    return len(list(items))\n")

    def test_line_numbers_pick_between_equal_blocks(self, tree):
        twice = "x = 1\n\nx = 1\n"
        (tree / "app" / "calc.py").write_text(twice, encoding="utf-8", newline="")
        patch = "--- a/app/calc.py\n+++ b/app/calc.py\n@@ -3,1 +3,1 @@\n-x = 1\n+x = 2\n"
        apply_to_directory(tree, patch)
        assert read(tree) == "x = 1\n\nx = 2\n"

    def test_an_ambiguous_hunk_is_refused(self, tree):
        (tree / "app" / "calc.py").write_text("x = 1\n\nx = 1\n", encoding="utf-8", newline="")
        patch = "--- a/app/calc.py\n+++ b/app/calc.py\n@@\n-x = 1\n+x = 2\n"
        with pytest.raises(ApplyError, match="hunk 1 .* matches 2 places"):
            apply_to_directory(tree, patch)

    def test_lines_that_are_not_there_are_refused(self, tree):
        patch = "--- a/app/calc.py\n+++ b/app/calc.py\n@@\n-    return max(items)\n+    pass\n"
        with pytest.raises(ApplyError, match="does not apply cleanly: hunk 1 of app/calc.py"):
            apply_to_directory(tree, patch)
        assert read(tree) == ORIGINAL

    def test_an_empty_context_line_without_its_space(self, tree):
        """Modeller boş bağlam satırının başındaki boşluğu sık atar."""
        patch = (
            "--- a/app/calc.py\n+++ b/app/calc.py\n@@\n"
            "     return sum(items)\n\n\n def count(items):\n"
            "-    return len(items)\n+    return 0\n"
        )
        apply_to_directory(tree, patch)
        assert read(tree).endswith("def count(items):\n    return 0\n")


class TestFiles:
    def test_crlf_files_keep_their_line_endings(self, tree):
        (tree / "app" / "calc.py").write_bytes(ORIGINAL.replace("\n", "\r\n").encode())
        patch = (
            "--- a/app/calc.py\n+++ b/app/calc.py\n@@\n"
            " def total(items):\n-    return sum(items)\n+    return sum(list(items))\n"
        )
        apply_to_directory(tree, patch)
        text = read(tree)
        assert "    return sum(list(items))\r\n" in text
        assert "\n" not in text.replace("\r\n", "")

    def test_a_new_file_is_created(self, tree):
        patch = "--- /dev/null\n+++ b/app/new.py\n@@ -0,0 +1,2 @@\n+def f():\n+    return 1\n"
        apply_to_directory(tree, patch)
        assert read(tree, "app/new.py") == "def f():\n    return 1\n"

    def test_several_hunks_apply_in_order(self, tree):
        patch = (
            "--- a/app/calc.py\n+++ b/app/calc.py\n@@\n"
            "-    return sum(items)\n+    return 1\n@@\n-    return len(items)\n+    return 2\n"
        )
        apply_to_directory(tree, patch)
        assert (
            read(tree) == "def total(items):\n    return 1\n\n\ndef count(items):\n    return 2\n"
        )

    def test_a_failing_hunk_changes_no_file(self, tree):
        (tree / "app" / "other.py").write_text("y = 1\n", encoding="utf-8", newline="")
        patch = (
            "--- a/app/other.py\n+++ b/app/other.py\n@@\n-y = 1\n+y = 2\n"
            "--- a/app/calc.py\n+++ b/app/calc.py\n@@\n-not in the file\n+x\n"
        )
        with pytest.raises(ApplyError):
            apply_to_directory(tree, patch)
        assert read(tree, "app/other.py") == "y = 1\n"

    def test_a_patch_for_a_missing_file_is_refused(self, tree):
        patch = "--- a/app/ghost.py\n+++ b/app/ghost.py\n@@\n-x\n+y\n"
        with pytest.raises(ApplyError, match="app/ghost.py does not exist"):
            apply_to_directory(tree, patch)

    def test_no_hunks_at_all(self, tree):
        with pytest.raises(ApplyError, match="no hunk"):
            apply_to_directory(tree, "--- a/app/calc.py\n+++ b/app/calc.py\n")

    def test_touched_paths_still_lists_every_file(self):
        patch = (
            "--- /dev/null\n+++ b/app/new.py\n@@\n+x\n"
            "--- a/app/calc.py\n+++ b/app/calc.py\n@@\n-a\n+b\n"
        )
        assert touched_paths(patch) == ["app/new.py", "app/calc.py"]
