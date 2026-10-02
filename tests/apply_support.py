"""`apply` testlerinin ortak projesi ve yardımcıları.

Pytest fikstürü değil, düz fonksiyonlar: test dosyaları `repo` fikstürünü
kendileri `make_repo` ile tanımlar (başka bir test modülünden fikstür içe
aktarmak ruff F811 üretir).
"""

from __future__ import annotations

import difflib
import subprocess
import sys
from pathlib import Path

SHOP = """class Pricing:
    def price(self, kind, amount):
        if kind == "a":
            return amount * 2
        if kind == "b":
            return amount * 3
        if kind == "c":
            return amount * 4
        return amount

    def label(self):
        return "pricing"
"""

TESTS = """from app.shop import Pricing


def test_price():
    pricing = Pricing()
    assert [pricing.price(k, 1) for k in "abcz"] == [2, 3, 4, 1]
"""

TARGET = "app.shop:Pricing"


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def make_repo(tmp_path: Path) -> Path:
    """Kendi testleri ve `tests.command`'ı olan, tek commit'lik küçük bir depo."""
    root = tmp_path / "shop"
    (root / "app").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "shop.py").write_text(SHOP, encoding="utf-8")
    (root / "tests" / "test_shop.py").write_text(TESTS, encoding="utf-8")
    command = f'"{sys.executable}" -m pytest -q -p no:cacheprovider tests'
    (root / "rlens.yaml").write_text(
        "scan:\n  include: ['.']\n  exclude: ['tests/']\n"
        f"tests:\n  command: '{command}'\n  timeout: 120\n",
        encoding="utf-8",
    )
    git(root, "init", "-q", "-b", "main")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "initial")
    return root


#: Aracın kendi çıktısı (`advise` ve `scan` de yazar); patch'in dokunduğu şey değildir.
TOOL_OUTPUT = ("reports/", ".rlens-cache/")


def snapshot(root: Path):
    """Kullanıcının durumu: HEAD, branch, `status` (aracın çıktı dizinleri hariç), dosya."""
    status = [
        line
        for line in git(root, "status", "--porcelain", "--untracked-files=all").splitlines()
        if not line[3:].startswith(TOOL_OUTPUT)
    ]
    return (
        git(root, "rev-parse", "HEAD"),
        git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        status,
        (root / "app" / "shop.py").read_text(encoding="utf-8"),
    )


def diff_for(new: str, path: str = "app/shop.py", old: str = SHOP) -> str:
    lines = difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True), f"a/{path}", f"b/{path}"
    )
    return "".join(lines)


def reply(patch: str) -> str:
    return f"Here is the patch.\n```diff\n{patch}```\n"


class FakeProvider:
    name = "fake"

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def generate(self, system, user, config, temperature):
        self.prompts.append(user)
        return self.replies.pop(0)


def advice(effect=None):
    return {
        "advices": [
            {
                "target": TARGET,
                "suggestions": [
                    {
                        "title": "Replace the branches with a lookup table",
                        "sketch": "Turn the if chain in price into a dict lookup.",
                        "expected_effect": effect or [{"metric": "WMC", "direction": "down"}],
                    }
                ],
            }
        ]
    }


IMPROVED_SHOP = SHOP.replace(
    """        if kind == "a":
            return amount * 2
        if kind == "b":
            return amount * 3
        if kind == "c":
            return amount * 4
        return amount
""",
    """        return amount * {"a": 2, "b": 3, "c": 4}.get(kind, 1)
""",
)
BROKEN_SHOP = SHOP.replace("return amount * 4", "return amount * 5")
DELETED_SHOP = SHOP.replace('\n    def label(self):\n        return "pricing"\n', "")
