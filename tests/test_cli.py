"""CLI testleri.

`scan` artık gerçek iş yapıyor; testler hem komut yüzeyini hem uçtan uca akışı
kapsar. Çıkış kodları sözleşmeye göre ayrılmıştır (bkz. cli.py).
"""

import json

import pytest
from typer.testing import CliRunner

from rlens import __version__
from rlens.analysis.model import SCHEMA_VERSION
from rlens.cli import app

runner = CliRunner()

USAGE_ERROR = 2  # click/typer'a ayrılmış


@pytest.fixture
def project(tmp_path):
    """Tek eşik ihlali içeren küçük bir proje."""
    (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
    (tmp_path / "mod.py").write_text(
        "class Widget:\n"
        "    def __init__(self):\n        self.a = 1\n        self.b = 2\n"
        "    def touch_a(self):\n        return self.a\n"
        "    def touch_b(self):\n        return self.b\n",
        encoding="utf-8",
    )
    return tmp_path


class TestSurface:
    def test_help_lists_scan(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "scan" in result.output

    def test_version_reports_package_and_schema(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output
        assert f"v{SCHEMA_VERSION}" in result.output

    def test_no_args_shows_usage(self):
        assert "Usage" in runner.invoke(app, []).output

    def test_missing_path_is_a_usage_error(self):
        assert runner.invoke(app, ["scan", "/yok/boyle"]).exit_code == USAGE_ERROR

    def test_file_instead_of_directory_is_rejected(self, tmp_path):
        target = tmp_path / "tek.py"
        target.write_text("x = 1\n", encoding="utf-8")
        assert runner.invoke(app, ["scan", str(target)]).exit_code == USAGE_ERROR


class TestScanRun:
    def test_scan_succeeds_and_prints_table(self, project):
        result = runner.invoke(app, ["scan", str(project), "--no-report"])
        assert result.exit_code == 0
        assert "Widget" in result.output

    def test_report_is_written_by_default(self, project):
        result = runner.invoke(app, ["scan", str(project)])
        assert result.exit_code == 0
        reports = list((project / "reports").glob("scan-*.json"))
        assert len(reports) == 1
        payload = json.loads(reports[0].read_text(encoding="utf-8"))
        assert payload["schema_version"] == SCHEMA_VERSION

    def test_no_report_flag_writes_nothing(self, project):
        runner.invoke(app, ["scan", str(project), "--no-report"])
        assert not (project / "reports").exists()

    def test_output_dir_overrides_config(self, project, tmp_path):
        target = tmp_path / "elsewhere"
        result = runner.invoke(app, ["scan", str(project), "--output-dir", str(target)])
        assert result.exit_code == 0
        assert list(target.glob("scan-*.json"))

    def test_explicit_config_is_used(self, project, tmp_path):
        config = tmp_path / "custom.yaml"
        config.write_text("scan:\n  include: ['.']\n  exclude: ['mod.py']\n", encoding="utf-8")
        result = runner.invoke(app, ["scan", str(project), "--config", str(config), "--no-report"])
        assert result.exit_code == 0
        assert "Widget" not in result.output

    def test_bad_config_exits_one(self, project):
        (project / "rlens.yaml").write_text("advise:\n  top_n: 0\n", encoding="utf-8")
        result = runner.invoke(app, ["scan", str(project)])
        assert result.exit_code == 1

    def test_empty_project_still_succeeds(self, tmp_path):
        result = runner.invoke(app, ["scan", str(tmp_path), "--no-report"])
        assert result.exit_code == 0
        assert "No Python files found" in result.output

    def test_broken_file_does_not_crash_the_command(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        (tmp_path / "bad.py").write_text("def f(\n", encoding="utf-8")
        result = runner.invoke(app, ["scan", str(tmp_path), "--no-report"])
        assert result.exit_code == 0
        assert "bad.py" in result.output


class TestFailOnViolation:
    def test_exits_one_when_violations_exist(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        (tmp_path / "bad.py").write_text(
            "def many(a, b, c, d, e, f, g):\n    return 1\n", encoding="utf-8"
        )
        result = runner.invoke(app, ["scan", str(tmp_path), "--no-report", "--fail-on-violation"])
        assert result.exit_code == 1

    def test_exits_zero_when_clean(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        (tmp_path / "ok.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        result = runner.invoke(app, ["scan", str(tmp_path), "--no-report", "--fail-on-violation"])
        assert result.exit_code == 0

    def test_without_flag_violations_do_not_fail(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        (tmp_path / "bad.py").write_text(
            "def many(a, b, c, d, e, f, g):\n    return 1\n", encoding="utf-8"
        )
        result = runner.invoke(app, ["scan", str(tmp_path), "--no-report"])
        assert result.exit_code == 0
