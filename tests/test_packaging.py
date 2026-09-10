"""Yayınlanan paketin sözleşmesini koruyan testler.

Buradaki hatalar yalnızca **PyPI'da** görünür: paket kurulur, README render
edilir, kimse bir şeyin kırıldığını fark etmez. v1.0.0'da README'de bir
`<user>` placeholder'ı ve dokümanlara giden göreli linkler yayınlandı; göreli
linkler PyPI sayfasında 404 verir çünkü orada depo ağacı yoktur.

Bu yüzden yayın öncesi elle kontrol edilen şeyler burada testtir.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from rlens import __version__

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


class TestVersion:
    """Sürüm numarası tek kaynaktan gelir."""

    def test_version_is_semver(self):
        assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), __version__

    def test_pyproject_reads_the_version_from_the_package(self, pyproject):
        # İki yerde elle tutulan bir sürüm numarası er geç ayrışır ve wheel,
        # kendi raporlarının `rlens_version` alanıyla çelişir.
        assert pyproject["project"]["dynamic"] == ["version"]
        assert pyproject["tool"]["hatch"]["version"]["path"] == "src/rlens/__init__.py"


class TestReadmeSurvivesPyPI:
    """README, depo ağacı olmayan bir yerde render edilir."""

    def test_no_unfilled_placeholders(self, readme):
        assert "<user>" not in readme

    def test_every_link_is_absolute(self, readme):
        # PyPI göreli yolu çözemez: `](FINDINGS.md)` orada 404'tür.
        relative = [
            url
            for url in re.findall(r"\]\(([^)]+)\)", readme)
            if not url.startswith(("http://", "https://", "#", "mailto:"))
        ]
        assert relative == []

    def test_the_install_name_is_the_distribution_name(self, readme, pyproject):
        name = pyproject["project"]["name"]
        assert f"pipx install {name}" in readme


class TestPackagedMetadata:
    def test_the_cli_entry_point_exists(self, pyproject):
        assert pyproject["project"]["scripts"]["rlens"] == "rlens.cli:main"

    def test_readme_is_the_long_description(self, pyproject):
        # `readme` alanı düşerse PyPI sayfası boş çıkar ve bu, yayınlanana
        # kadar hiçbir yerde görünmez.
        assert pyproject["project"]["readme"] == "README.md"
