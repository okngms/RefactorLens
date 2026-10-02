"""`apply` patch prompt'u ve yanıt ayrıştırıcısı (`docs/02` §2.3).

`advise/prompts.py` deney protokolü gereği donmuş kalır; patch istemi ayrı bir
sözleşmedir ve burada yaşar.

**Prompt modelin kendi tahminini taşımaz.** Öneri metni (başlık ve `sketch`)
gönderilir, `expected_effect` gönderilmez. Model patch'i kendi tahminini
tutturacak biçimde yazabilseydi, v2.4'ün ölçtüğü şey — tahmin doğruluğu —
uygulama adımında şişerdi. Aynı gerekçeyle ölçümler ve eşikler de girmez.

**En dar yorum.** Faz 5 protokolündeki kural modele de verilir: önerinin
açıkça söylemediği hiçbir şey iyileştirilmez.
"""

from __future__ import annotations

import re

SYSTEM_INSTRUCTION = """\
You apply one refactoring suggestion to Python code by writing a patch.

Rules you must follow:

1. Implement exactly what the suggestion says, and nothing the suggestion does \
not say. Do not tidy, rename, reformat or fix anything else.
2. Change only the files listed as allowed. A file marked as not existing yet \
may be created.
3. Keep the program's behaviour: callers outside these files must keep working.
4. Reply with a single unified diff inside one ```diff fenced block. Paths are \
relative to the repository root and use the a/ and b/ prefixes, for example \
--- a/app/orders.py and +++ b/app/orders.py.
5. Show only the regions that change, each with about three unchanged lines of \
context. Do not repeat code that stays the same. The lines you keep and remove \
must match the file exactly; line numbers in hunk headers may be approximate.
"""

_FENCE = re.compile(r"```(?:diff|patch)[ \t]*\n(.*?)```", re.DOTALL)


class PatchFormatError(ValueError):
    """Yanıt sözleşmeye uymuyor; mesaj onarım prompt'una ve rapora girer."""


def build_patch_prompt(target: str, suggestion: dict, files: dict[str, str | None]) -> str:
    """Patch istemi. `files`: izinli yol → içerik; `None` henüz olmayan dosya."""
    lines = [
        f"Target: {target}",
        "",
        "## Suggestion to apply",
        f"Title: {suggestion.get('title') or '(untitled)'}",
        "",
        str(suggestion.get("sketch") or "").strip(),
        "",
        "## Files you may change",
    ]
    for path, content in files.items():
        state = "" if content is not None else " (does not exist yet; you may create it)"
        lines.append(f"- {path}{state}")
    for path, content in files.items():
        if content is None:
            continue
        lines += ["", f"### {path}", "```python", content.rstrip("\n"), "```"]
    return "\n".join(lines) + "\n"


#: Onarım istemine eklenen reddedilmiş patch'in üst sınırı (karakter).
REPAIR_PATCH_LIMIT = 2000


def build_repair_prompt(original: str, rejected: str | None, reason: str) -> str:
    """Tek onarım denemesi: özgün istem, reddin nedeni ve kısaysa reddedilen patch.

    Uzun patch eklenmez: ilk gerçek koşuda onarım istemi bütün dosyayı yeniden
    yazan bir patch taşıdı ve sağlayıcının dakikalık token sınırını aştı. Model
    özgün kodu ve öneriyi zaten yeniden görür; neden yeterlidir.
    """
    lines = [original.rstrip("\n"), "", "## Your previous reply was rejected", reason]
    if rejected and len(rejected) <= REPAIR_PATCH_LIMIT:
        lines += ["", "Rejected patch:", "```diff", rejected.rstrip("\n"), "```"]
    elif rejected:
        lines += ["", "(The rejected patch is too long to repeat here.)"]
    lines += ["", "Send one corrected unified diff in a ```diff block."]
    return "\n".join(lines) + "\n"


def parse_patch(reply: str) -> str:
    """Yanıttaki tek ```diff bloğu. Yoksa, birden fazlaysa ya da boşsa reddedilir."""
    blocks = _FENCE.findall(reply)
    if not blocks:
        raise PatchFormatError("The reply contains no ```diff block.")
    if len(blocks) > 1:
        raise PatchFormatError(f"The reply contains {len(blocks)} ```diff blocks; expected one.")
    patch = blocks[0]
    if not patch.strip():
        raise PatchFormatError("The ```diff block is empty.")
    return patch
