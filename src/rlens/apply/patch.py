"""Patch doğrulama ve uygulama (`docs/02` §2, invariant 3-4).

Patch unified diff olarak gelir. Uygulanmadan önce dokunduğu dosyalar
çıkarılır ve izin kümesiyle karşılaştırılır: hedef sınıfın dosyası ve
`apply.allow_files`. Başka bir dosyaya dokunan patch reddedilir.

**Uygulama birebir içerik eşleşmesiyle yapılır, `git apply` ile değil.** İlk
gerçek koşuda model iki denemede de hunk başlığını satır numarasız yazdı
(`@@`) ve `git apply` patch'i konumlandıramadı; Windows'ta CRLF'li dosyaya LF
patch de uymazdı. Burada her hunk'ın kaldırılan ve korunan satırları dosyada
birebir aranır (satır sonu boşlukları hariç). Satır numaraları yalnızca aynı
blok birden fazla yerde geçiyorsa seçim için kullanılır. Eşleşme yoksa ya da
belirsizse patch reddedilir. Önce bütün dosyaların yeni içeriği hesaplanır,
sonra yazılır: bir hunk başarısızsa hiçbir dosya değişmez. Dosyanın satır
sonu (CRLF/LF) korunur.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from rlens.apply.worktree import ApplyError, Worktree

_NULL = "/dev/null"
_HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@")
_PREFIX = "The patch does not apply cleanly"


@dataclass
class _Hunk:
    old_start: int | None
    """Başlıktaki eski satır numarası; numarasız `@@`'da `None`."""
    lines: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class _FilePatch:
    old: str | None
    new: str | None
    hunks: list[_Hunk] = field(default_factory=list)

    @property
    def path(self) -> str:
        return self.new or self.old or ""


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


def _parse(diff: str) -> list[_FilePatch]:
    files: list[_FilePatch] = []
    hunk: _Hunk | None = None
    lines = diff.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if (
            line.startswith("--- ")
            and index + 1 < len(lines)
            and lines[index + 1].startswith("+++ ")
        ):
            files.append(_FilePatch(_strip_prefix(line[4:]), _strip_prefix(lines[index + 1][4:])))
            hunk = None
            index += 2
            continue
        if line.startswith("@@"):
            if not files:
                raise ApplyError(f"{_PREFIX}: a hunk comes before any file header.")
            match = _HUNK.match(line)
            hunk = _Hunk(int(match.group(1)) if match else None)
            files[-1].hunks.append(hunk)
        elif hunk is not None:
            if line.startswith("\\"):
                pass  # "\ No newline at end of file"
            elif line == "":
                # Modeller boş bağlam satırının başındaki boşluğu sık atar.
                hunk.lines.append((" ", ""))
            elif line[0] in " +-":
                hunk.lines.append((line[0], line[1:]))
            else:
                hunk = None  # `diff --git`, `index` ya da düz metin hunk'ı bitirir
        index += 1
    for file in files:
        for item in file.hunks:
            while item.lines and item.lines[-1] == (" ", ""):
                item.lines.pop()  # sondaki boş satırlar bağlam değil, biçimlendirme
    return files


def _locate(lines: list[str], old: list[str], hunk: _Hunk, cursor: int, label: str) -> int:
    if not old:
        if hunk.old_start is None:
            raise ApplyError(
                f"{_PREFIX}: {label} adds lines but shows no context and no line number."
            )
        return min(hunk.old_start, len(lines))
    key = [text.rstrip() for text in old]
    width = len(old)
    matches = [
        start
        for start in range(cursor, len(lines) - width + 1)
        if [text.rstrip() for text in lines[start : start + width]] == key
    ]
    if not matches:
        raise ApplyError(f"{_PREFIX}: {label}: the lines to replace were not found in the file.")
    if len(matches) == 1:
        return matches[0]
    if hunk.old_start is not None and hunk.old_start - 1 in matches:
        return hunk.old_start - 1
    raise ApplyError(
        f"{_PREFIX}: {label} matches {len(matches)} places; include more context lines."
    )


def _patched(text: str, file: _FilePatch) -> str:
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    cursor = 0
    for number, hunk in enumerate(file.hunks, start=1):
        old = [content for tag, content in hunk.lines if tag in " -"]
        new = [content.rstrip("\r") for tag, content in hunk.lines if tag in " +"]
        at = _locate(lines, old, hunk, cursor, f"hunk {number} of {file.path}")
        lines[at : at + len(old)] = new
        cursor = at + len(new)
    if not lines:
        return ""
    return eol.join(lines) + eol


def apply_to_directory(base: Path, diff: str) -> None:
    """Patch'i `base` altındaki dosyalara uygular; başarısızsa hiçbir şeye dokunmaz."""
    files = _parse(diff)
    if not files:
        raise ApplyError("The patch names no file; expected a unified diff.")
    results: dict[Path, str | None] = {}
    for file in files:
        target = Path(base) / file.path
        if file.old is None:
            if target.exists():
                raise ApplyError(f"{_PREFIX}: {file.path} already exists.")
            added = [content.rstrip("\r") for tag, content in _all_lines(file) if tag == "+"]
            results[target] = "\n".join(added) + "\n" if added else ""
            continue
        if not target.is_file():
            raise ApplyError(f"{_PREFIX}: {file.path} does not exist.")
        if file.new is None:
            results[target] = None
            continue
        if not file.hunks:
            raise ApplyError(f"{_PREFIX}: the patch has no hunk for {file.path}.")
        text = target.read_bytes().decode("utf-8")
        results[target] = _patched(text, file)
    for target, content in results.items():
        if content is None:
            target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))


def _all_lines(file: _FilePatch) -> list[tuple[str, str]]:
    return [line for hunk in file.hunks for line in hunk.lines]


def apply_patch(work: Worktree, diff: str) -> None:
    """Patch'i worktree'ye uygular (bkz. `apply_to_directory`)."""
    apply_to_directory(work.path, diff)
