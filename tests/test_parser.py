"""Dosya keşfi ve ayrıştırma testleri.

Buradaki en önemli test grubu **bozuk dosya davranışıdır**: gerçek kod
tabanlarında ayrıştırılamayan dosyalar her zaman bulunur ve araç bunlar yüzünden
kullanılamaz hale gelmemelidir.
"""

import ast
from pathlib import Path

import pytest

from rlens.analysis.parser import (
    ParsedModule,
    SkippedFile,
    discover_files,
    module_name,
    parse_file,
    parse_project,
)

MESSY_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "messy_project"


@pytest.fixture
def project(tmp_path):
    """Küçük, gerçekçi bir proje ağacı kurar."""
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "pkg" / "core.py").write_text("def f():\n    pass\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_core.py").write_text("def test():\n    pass\n", encoding="utf-8")
    (tmp_path / "setup.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not python\n", encoding="utf-8")
    return tmp_path


def relative_names(paths, root):
    return sorted(p.relative_to(root).as_posix() for p in paths)


class TestDiscovery:
    def test_finds_only_python_files(self, project):
        found = relative_names(discover_files(project), project)
        assert "notes.txt" not in found
        assert "setup.py" in found

    def test_include_narrows_to_subtree(self, project):
        found = relative_names(discover_files(project, include=("src/",)), project)
        assert found == ["src/pkg/__init__.py", "src/pkg/core.py"]

    def test_exclude_removes_subtree(self, project):
        found = relative_names(discover_files(project, exclude=("tests/",)), project)
        assert "tests/test_core.py" not in found

    def test_exclude_wins_over_include(self, project):
        found = discover_files(project, include=("src/",), exclude=("src/",))
        assert found == []

    @pytest.mark.parametrize("pattern", ["src", "src/", "./src", "src\\"])
    def test_pattern_forms_are_equivalent(self, project, pattern):
        """Kullanıcı eğik çizgiyi nasıl yazarsa yazsın aynı sonucu almalı."""
        found = relative_names(discover_files(project, include=(pattern,)), project)
        assert found == ["src/pkg/__init__.py", "src/pkg/core.py"]

    def test_exclude_matches_directory_name_anywhere(self, tmp_path):
        """`tests` deseni, iç içe konumdaki tests dizinini de dışlar."""
        nested = tmp_path / "examples" / "demo" / "tests"
        nested.mkdir(parents=True)
        (nested / "test_x.py").write_text("", encoding="utf-8")
        (tmp_path / "main.py").write_text("", encoding="utf-8")
        found = relative_names(discover_files(tmp_path, exclude=("tests/",)), tmp_path)
        assert found == ["main.py"]

    def test_hidden_directories_are_skipped(self, tmp_path):
        (tmp_path / ".venv" / "lib").mkdir(parents=True)
        (tmp_path / ".venv" / "lib" / "mod.py").write_text("", encoding="utf-8")
        (tmp_path / "main.py").write_text("", encoding="utf-8")
        assert relative_names(discover_files(tmp_path), tmp_path) == ["main.py"]

    def test_pycache_is_skipped_without_config(self, tmp_path):
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "mod.py").write_text("", encoding="utf-8")
        (tmp_path / "main.py").write_text("", encoding="utf-8")
        assert relative_names(discover_files(tmp_path), tmp_path) == ["main.py"]

    def test_results_are_sorted(self, project):
        """Sıra kararlı olmalı; yoksa verify iki tarama arasında sahte fark görür."""
        first = discover_files(project)
        second = discover_files(project)
        assert first == second == sorted(first)

    def test_single_file_root(self, tmp_path):
        target = tmp_path / "one.py"
        target.write_text("x = 1\n", encoding="utf-8")
        assert discover_files(target) == [target]

    def test_empty_directory(self, tmp_path):
        assert discover_files(tmp_path) == []


class TestModuleName:
    def test_nested_module(self, project):
        path = project / "src" / "pkg" / "core.py"
        assert module_name(project, path) == "src.pkg.core"

    def test_init_resolves_to_package(self, project):
        path = project / "src" / "pkg" / "__init__.py"
        assert module_name(project, path) == "src.pkg"

    def test_top_level_module(self, project):
        assert module_name(project, project / "setup.py") == "setup"


class TestParseFile:
    def test_valid_file_returns_parsed_module(self, project):
        result = parse_file(project / "src" / "pkg" / "core.py", project)
        assert isinstance(result, ParsedModule)
        assert isinstance(result.tree, ast.Module)
        assert result.module == "src.pkg.core"
        assert result.relative_path == "src/pkg/core.py"
        assert "def f()" in result.source

    def test_syntax_error_is_skipped_not_raised(self, tmp_path):
        broken = tmp_path / "broken.py"
        broken.write_text("def f(\n", encoding="utf-8")
        result = parse_file(broken, tmp_path)
        assert isinstance(result, SkippedFile)
        assert "sözdizimi" in result.reason

    def test_skip_reason_includes_line_number(self, tmp_path):
        broken = tmp_path / "broken.py"
        broken.write_text("x = 1\ny = (\n", encoding="utf-8")
        result = parse_file(broken, tmp_path)
        assert isinstance(result, SkippedFile)
        assert "satır" in result.reason

    def test_non_utf8_file_is_skipped(self, tmp_path):
        broken = tmp_path / "latin.py"
        broken.write_bytes(b"x = '\xff\xfe'\n")
        result = parse_file(broken, tmp_path)
        assert isinstance(result, SkippedFile)
        assert "utf-8" in result.reason

    def test_empty_file_is_valid(self, tmp_path):
        empty = tmp_path / "empty.py"
        empty.write_text("", encoding="utf-8")
        assert isinstance(parse_file(empty, tmp_path), ParsedModule)

    def test_skipped_file_serializes(self, tmp_path):
        broken = tmp_path / "broken.py"
        broken.write_text("def f(\n", encoding="utf-8")
        result = parse_file(broken, tmp_path)
        assert set(result.to_dict()) == {"path", "reason"}


class TestParseProject:
    def test_broken_file_does_not_stop_the_scan(self, tmp_path):
        (tmp_path / "good.py").write_text("def f():\n    pass\n", encoding="utf-8")
        (tmp_path / "bad.py").write_text("def f(\n", encoding="utf-8")
        modules, skipped = parse_project(tmp_path)
        assert [m.relative_path for m in modules] == ["good.py"]
        assert [s.relative_path for s in skipped] == ["bad.py"]

    def test_respects_include_and_exclude(self, project):
        modules, _ = parse_project(project, include=("src/",), exclude=("**/__init__.py",))
        assert all(m.relative_path.startswith("src/") for m in modules)

    def test_messy_project_parses_completely(self):
        """Fikstür her zaman ayrıştırılabilir olmalı — bozuksa metrik testleri anlamsızdır."""
        modules, skipped = parse_project(MESSY_PROJECT, include=(".",), exclude=("tests/",))
        assert skipped == []
        names = {m.module for m in modules}
        assert names == {"models", "services", "god", "reporting", "utils"}
