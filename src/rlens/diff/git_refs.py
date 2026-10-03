"""Git ref'lerini geçici, ayrık (detached) worktree'lerde açmak.

Worktree'ler deponun **dışında**, geçici bir dizinde açılır ve iş bitince
kaldırılır: kullanıcının çalışma ağacı, HEAD'i ve `.gitignore`'u değişmez.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from rlens.apply.worktree import ApplyError, git


def parse_range(spec: str) -> tuple[str, str]:
    """`base..head`; `base..` HEAD demektir (git'in kendi kısaltması gibi)."""
    base, separator, head = spec.partition("..")
    if not separator or not base or head.startswith("."):
        raise ApplyError(f"Expected a range like origin/main..HEAD (base..head), got {spec!r}.")
    return base, head or "HEAD"


def resolve(root: Path, ref: str) -> str:
    done = git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], root, check=False)
    if done.returncode != 0:
        raise ApplyError(f"{ref!r} is not a commit in this repository.")
    return done.stdout.strip()


@contextmanager
def checkout(root: Path, ref: str) -> Iterator[Path]:
    """`ref`'i geçici bir worktree'de açar; çıkışta kaldırır."""
    commit = resolve(root, ref)
    scratch = Path(tempfile.mkdtemp(prefix="rlens-diff-"))
    path = scratch / commit[:12]
    done = git(["worktree", "add", "-q", "--detach", str(path), commit], root, check=False)
    if done.returncode != 0:
        shutil.rmtree(scratch, ignore_errors=True)
        raise ApplyError(f"Could not check out {ref}: {done.stderr.strip()}")
    try:
        yield path
    finally:
        git(["worktree", "remove", "--force", str(path)], root, check=False)
        git(["worktree", "prune"], root, check=False)
        shutil.rmtree(scratch, ignore_errors=True)


def changed_python_files(root: Path, base: str, head: str) -> list[str]:
    done = git(
        ["diff", "--name-only", resolve(root, base), resolve(root, head), "--", "*.py"], root
    )
    return sorted(line for line in done.stdout.splitlines() if line.strip())
