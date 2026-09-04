"""`rlens arch` çıktısı ve raporu."""

import json
from pathlib import Path

import pytest
from rich.console import Console

from rlens.analysis.architecture import analyse_project
from rlens.analysis.model import ARCH_SCHEMA_VERSION, SCHEMA_VERSION
from rlens.config import load_config
from rlens.report.architecture import common_prefix, render_architecture
from rlens.report.files import latest_arch, write_arch

LAYERED = Path(__file__).resolve().parent.parent / "examples" / "layered_project"


@pytest.fixture(scope="module")
def result():
    return analyse_project(LAYERED, load_config(search_from=LAYERED))


def render(result) -> str:
    console = Console(width=140, no_color=True, record=True)
    render_architecture(result, console)
    return console.export_text()


class TestCommonPrefix:
    """Ortak paket öneki tabloyu sardırmasın diye kırpılır."""

    def test_shared_prefix_is_found(self):
        assert common_prefix(["src.api.view", "src.domain.model"]) == "src."

    def test_deeper_shared_prefix(self):
        assert common_prefix(["a.b.one", "a.b.two"]) == "a.b."

    def test_no_shared_prefix(self):
        assert common_prefix(["api.view", "domain.model"]) == ""

    def test_single_module_is_not_trimmed(self):
        """Kırpılacak bir tekrar yok."""
        assert common_prefix(["src.api.view"]) == ""

    def test_last_segment_is_never_consumed(self):
        assert common_prefix(["pkg.a", "pkg.b"]) == "pkg."


class TestTerminalOutput:
    def test_header_counts(self, result):
        text = render(result)
        assert "10 modules" in text
        assert "8 with a layer" in text
        assert "11 internal imports" in text

    def test_layer_table_lists_every_module(self, result):
        text = render(result)
        for module in ("api.order_controller", "domain.entities", "shared.helpers"):
            assert module in text

    def test_declared_source_is_shown(self, result):
        assert "declared" in render(result)

    def test_unknown_modules_have_no_confidence(self, result):
        """Katmanı bilinmeyen modüle güven skoru uydurulmaz."""
        text = render(result)
        line = next(line for line in text.splitlines() if "shared.helpers" in line)
        assert "unknown" in line
        assert "—" in line

    def test_all_six_violations_are_listed(self, result):
        text = render(result)
        assert text.count("LV-SKIP") == 3
        for code in ("LV-DIR", "LV-CYCLE", "LV-LEAK"):
            assert code in text

    def test_aliases_are_shown(self, result):
        text = render(result)
        for alias in ("back-call", "skip-call", "cyclic", "leak"):
            assert alias in text

    def test_cycle_uses_a_bidirectional_arrow(self, result):
        assert "↔" in render(result)

    def test_module_coupling_table(self, result):
        text = render(result)
        assert "Module coupling" in text
        assert "Ca" in text and "Ce" in text

    def test_notes_are_printed(self, result):
        assert "stay unknown" in render(result)

    def test_blocking_count_is_returned(self, result):
        console = Console(width=140, no_color=True, record=True)
        assert render_architecture(result, console) == 6

    def test_clean_project_says_so(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        clean = analyse_project(tmp_path, load_config(search_from=tmp_path))
        assert "No architecture violations" in render(clean)

    def test_empty_project(self, tmp_path):
        empty = analyse_project(tmp_path, load_config(search_from=tmp_path))
        assert "No Python files found" in render(empty)


class TestJsonReport:
    def test_schema_version_is_separate_from_scan(self, result, tmp_path):
        """Mimari şeması tarama şemasından bağımsız sürümlenir."""
        payload = json.loads(write_arch(result, tmp_path).read_text(encoding="utf-8"))
        assert payload["schema_version"] == ARCH_SCHEMA_VERSION
        assert ARCH_SCHEMA_VERSION == 1 and SCHEMA_VERSION == 1

    def test_violations_carry_their_alias(self, result, tmp_path):
        payload = json.loads(write_arch(result, tmp_path).read_text(encoding="utf-8"))
        codes = {v["code"]: v["alias"] for v in payload["violations"]}
        assert codes["LV-DIR"] == "back-call"

    def test_modules_merge_metrics_and_layer(self, result, tmp_path):
        payload = json.loads(write_arch(result, tmp_path).read_text(encoding="utf-8"))
        entry = next(m for m in payload["modules"] if m["module"].endswith("entities"))
        assert entry["layer"] == "domain"
        assert entry["ce"] == 0
        assert entry["source"] == "declared"

    def test_scheme_is_recorded(self, result, tmp_path):
        """Rapor hangi kurallara göre üretildiğini taşımalı."""
        payload = json.loads(write_arch(result, tmp_path).read_text(encoding="utf-8"))
        assert payload["scheme"]["layers"][0] == "presentation"
        assert payload["scheme"]["allow_skip"] is False

    def test_graph_is_included(self, result, tmp_path):
        payload = json.loads(write_arch(result, tmp_path).read_text(encoding="utf-8"))
        assert len(payload["graph"]["edges"]) == 11

    def test_latest_arch_finds_the_newest(self, tmp_path):
        for name in ("arch-20260101-000000.json", "arch-20260301-000000.json"):
            (tmp_path / name).write_text("{}", encoding="utf-8")
        assert latest_arch(tmp_path).name == "arch-20260301-000000.json"

    def test_latest_arch_ignores_scan_reports(self, tmp_path):
        (tmp_path / "scan-20260101-000000.json").write_text("{}", encoding="utf-8")
        assert latest_arch(tmp_path) is None


class TestImportLinterIntegration:
    def test_contracts_are_used_when_nothing_is_declared(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            "[tool.importlinter]\n"
            "[[tool.importlinter.contracts]]\n"
            'name = "L"\ntype = "layers"\n'
            'layers = ["myapp.api", "myapp.domain"]\n',
            encoding="utf-8",
        )
        for name in ("myapp/api/view.py", "myapp/domain/model.py"):
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x = 1\n", encoding="utf-8")

        result = analyse_project(tmp_path, load_config(search_from=tmp_path))
        assert result.scheme.layers == ("api", "domain")
        assert result.report.layer_of("myapp.api.view") == "api"
        assert any("layers read from" in note for note in result.report.notes)

    def test_upward_import_is_a_violation(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            "[tool.importlinter]\n"
            "[[tool.importlinter.contracts]]\n"
            'name = "L"\ntype = "layers"\n'
            'layers = ["myapp.api", "myapp.domain"]\n',
            encoding="utf-8",
        )
        (tmp_path / "myapp" / "api").mkdir(parents=True)
        (tmp_path / "myapp" / "domain").mkdir(parents=True)
        (tmp_path / "myapp" / "api" / "view.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "myapp" / "domain" / "model.py").write_text(
            "from myapp.api.view import x\n", encoding="utf-8"
        )
        result = analyse_project(tmp_path, load_config(search_from=tmp_path))
        assert len(result.report.violations) == 1
