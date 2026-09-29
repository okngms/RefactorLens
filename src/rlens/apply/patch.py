"""Patch doğrulama ve uygulama (`docs/02` §2, invariant 3-4).

Patch unified diff olarak gelir. Uygulanmadan önce dokunduğu dosyalar
çıkarılır ve izin kümesiyle karşılaştırılır: hedef sınıfın dosyası ve
`apply.allow_files`. Başka bir dosyaya dokunan patch reddedilir; çakışan
patch `git apply --check` ile reddedilir ve worktree değişmeden kalır.
"""

from __future__ import annotations

import tempfile
from pathlib import Path, PurePosixPath

from rlens.apply.worktree import ApplyError, Worktree, git

_NULL = "/dev/null"


def _strip_prefix(raw: str) -> str | None:
    path = raw.split("\t", 1)[0].strip()
    if path == _NULL:
        return None
    if path.startswith(("a/", "b/")):
        path = path[2:]
    return path


def touched_paths(diff: str) -> list[str]:
    """Patch'in değiştirdiği, oluşturduğu ya da sildiği dosyalar, sırasıyla ve tekrarsız."""
    found: list[str] = []
    for line in diff.splitlines():
        candidate = None
        if line.startswith(("--- ", "+++ ")):
            candidate = _strip_prefix(line[4:])
        elif line.startswith(("rename from ", "rename to ", "copy from ", "copy to ")):
            candidate = line.split(" ", 2)[2].strip()
        if candidate and candidate not in found:
            found.append(candidate)
    return found


def validate_paths(paths: list[str], allowed: set[str]) -> None:
    """Dokunulan her dosya izinli mi ve depo içinde mi (invariant 4)."""
    if not paths:
        raise ApplyError("The patch names no file; expected a unified diff.")
    escaping = [
        p for p in paths if PurePosixPath(p).is_absolute() or ".." in PurePosixPath(p).parts
    ]
    if escaping:
        raise ApplyError(f"The patch reaches outside the repository: {', '.join(escaping)}")
    forbidden = [p for p in paths if p not in allowed]
    if forbidden:
        raise ApplyError(
            f"The patch changes files it may not change: {', '.join(forbidden)}. "
            "Only the target's file and `apply.allow_files` may change."
        )


def apply_patch(work: Worktree, diff: str) -> None:
    """Patch'i worktree'ye uygular; uygulanamıyorsa hiçbir şeye dokunmadan reddeder."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".patch", delete=False, encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(diff if diff.endswith("\n") else diff + "\n")
        patch_file = Path(handle.name)
    try:
        check = git(["apply", "--check", str(patch_file)], work.path, check=False)
        if check.returncode != 0:
            reason = check.stderr.strip().splitlines()[0] if check.stderr.strip() else "unknown"
            raise ApplyError(f"The patch does not apply cleanly: {reason}")
        git(["apply", str(patch_file)], work.path)
    finally:
        patch_file.unlink(missing_ok=True)
