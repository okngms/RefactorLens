"""Git deposu, temiz ağaç denetimi ve izole worktree (`docs/02` §2, invariant 1-2).

Her uygulama ayrı bir worktree'de (`.rlens-work/<run-id>/`) ve ayrı bir
branch'te (`rlens/<run-id>/<hedef>`) yapılır. Kullanıcının çalışma ağacı ve
HEAD'i hiçbir adımda değişmez; testler bunu her senaryoda sabitler.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: Worktree'lerin kök dizini, depo köküne göre.
WORK_DIR = ".rlens-work"

#: Git branch adında geçersiz karakterler (`:` hedef adından gelir).
_BRANCH_UNSAFE = re.compile(r"[^A-Za-z0-9._/-]+")


class ApplyError(Exception):
    """Uygulama güvenli biçimde yapılamıyor; mesaj kullanıcıya gösterilir."""


@dataclass(frozen=True)
class Worktree:
    root: Path
    """Kullanıcının deposunun kökü."""
    path: Path
    branch: str
    run_id: str


def git(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


def repository_root(path: Path) -> Path:
    """Deponun kökü. Depo değilse reddedilir (invariant 1)."""
    done = git(["rev-parse", "--show-toplevel"], Path(path), check=False)
    if done.returncode != 0:
        raise ApplyError(
            f"{path} is not inside a git repository. `apply` works only on git "
            "repositories, so every change lands on a branch you can review or delete."
        )
    return Path(done.stdout.strip()).resolve()


def ensure_clean(root: Path, ignore: tuple[str, ...] = ()) -> None:
    """Commit'lenmemiş değişiklik ya da izlenmeyen dosya varsa reddeder (invariant 1).

    İzlenmeyen dosya da kirli sayılır: worktree HEAD'den kurulur ve o dosyayı
    görmez; kullanıcı testlerin onu kapsadığını sanabilir. `--allow-dirty` yok.

    `ignore`: aracın kendi çıktı dizinleri (raporlar, önbellek), depo köküne
    göre. Onlar `.gitignore`'da değilse ikinci `apply` aracın kendi rapor
    dosyası yüzünden reddederdi; worktree'ye girmezler, testleri etkilemezler.
    """
    done = git(["status", "--porcelain", "--untracked-files=all"], root)
    prefixes = tuple(p.strip("/") + "/" for p in ignore if p.strip("/"))
    entries = [
        line[3:]
        for line in done.stdout.splitlines()
        if line.strip() and not line[3:].strip('"').startswith(prefixes)
    ]
    if entries:
        shown = ", ".join(entries[:5]) + (
            f" (+{len(entries) - 5} more)" if len(entries) > 5 else ""
        )
        raise ApplyError(
            f"The working tree has uncommitted changes: {shown}. "
            "Commit or stash them first; `apply` starts from a clean HEAD."
        )


def branch_name(run_id: str, target: str) -> str:
    return f"rlens/{run_id}/{_BRANCH_UNSAFE.sub('-', target).strip('-')}"


def _exclude_work_dir(root: Path) -> None:
    """`.rlens-work/`'ü deponun yerel dışlama listesine ekler.

    Worktree depo kökünün altında durur; dışlanmazsa `git status` onu
    izlenmeyen dizin olarak gösterir ve sonraki `apply` ağacı kirli bulur.
    `.gitignore`'a değil `info/exclude`'a yazılır: kullanıcının dosyalarına
    dokunulmaz, kayıt yalnızca bu makinede kalır.
    """
    common = Path(git(["rev-parse", "--git-common-dir"], root).stdout.strip())
    if not common.is_absolute():
        common = root / common
    exclude = common / "info" / "exclude"
    entry = f"/{WORK_DIR}/"
    existing = exclude.read_text(encoding="utf-8").splitlines() if exclude.exists() else []
    if entry in existing:
        return
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8") as handle:
        if existing and existing[-1] != "":
            handle.write("\n")
        handle.write(entry + "\n")


def create_worktree(root: Path, run_id: str, target: str) -> Worktree:
    """HEAD'den yeni bir branch ile izole worktree kurar (invariant 2)."""
    root = Path(root).resolve()
    _exclude_work_dir(root)
    path = root / WORK_DIR / run_id
    branch = branch_name(run_id, target)
    done = git(["worktree", "add", "-q", "-b", branch, str(path), "HEAD"], root, check=False)
    if done.returncode != 0:
        raise ApplyError(f"Could not create a worktree for {target}: {done.stderr.strip()}")
    return Worktree(root=root, path=path, branch=branch, run_id=run_id)


def discard(work: Worktree) -> None:
    """Worktree'yi ve branch'ini siler (invariant 5: kapı geçmezse iz kalmaz)."""
    release(work)
    git(["branch", "-D", work.branch], work.root, check=False)


def release(work: Worktree) -> None:
    """Worktree dizinini kaldırır, branch'i bırakır (invariant 7).

    Başarılı uygulamanın sonucu branch'tir; kullanıcı onu inceler ve merge
    eder. Dizin kalsaydı `.rlens-work/` her koşuda büyürdü.
    """
    git(["worktree", "remove", "--force", str(work.path)], work.root, check=False)
    git(["worktree", "prune"], work.root, check=False)


def commit_paths(work: Worktree, paths: list[str], message: str) -> str:
    """Yalnızca verilen dosyaları branch'e commit'ler; commit kimliğini döndürür.

    `git add -A` değil: testler worktree'de artık üretir (`__pycache__`,
    `.pytest_cache`) ve kullanıcının `.gitignore`'u onları kapsamıyorsa commit'e
    girerdi. İlk gerçek koşuda 15 `.pyc` dosyası böyle branch'e girdi. Patch
    yalnızca izinli dosyalara dokunur (invariant 4); commit de yalnızca onları
    taşır.

    Kullanıcının git kimliği kullanılır. Tanımlı değilse commit RefactorLens
    adıyla atılır: kimlik eksikliği yüzünden geçmiş bir kapıyı kaybetmek,
    commit'in yazarını belirsiz bırakmaktan kötüdür.
    """
    git(["add", "-A", "--", *paths], work.path)
    done = git(["commit", "-q", "-m", message], work.path, check=False)
    if done.returncode != 0:
        fallback = ["-c", "user.name=RefactorLens", "-c", "user.email=rlens@localhost"]
        git([*fallback, "commit", "-q", "-m", message], work.path)
    return git(["rev-parse", "HEAD"], work.path).stdout.strip()
