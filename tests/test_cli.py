"""CLI kabuğu testleri (Faz 0).

Bu fazda test edilen şey "komut doğru sonuç veriyor mu" değil, **"komut yüzeyi
doğru mu"**: argümanlar, bayraklar ve çıkış kodları. Stub'ın sessizce başarılı
olmadığını da burada garantiye alıyoruz.
"""

import pytest
from typer.testing import CliRunner

from rlens import __version__
from rlens.analysis.model import SCHEMA_VERSION
from rlens.cli import NOT_IMPLEMENTED_EXIT, app

runner = CliRunner()

USAGE_ERROR = 2  # click/typer'a ayrılmış çıkış kodu


@pytest.fixture
def project(tmp_path):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def test_help_exits_cleanly():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "scan" in result.output


def test_version_reports_package_and_schema():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
    assert f"v{SCHEMA_VERSION}" in result.output


def test_no_args_shows_usage():
    assert "Usage" in runner.invoke(app, []).output


def test_scan_fails_loudly_while_unimplemented():
    """Uygulanmamış komut sessizce başarılı olmamalı."""
    result = runner.invoke(app, ["scan", "."])
    assert result.exit_code == NOT_IMPLEMENTED_EXIT


def test_missing_path_is_a_usage_error():
    """Olmayan klasör, 'uygulanmadı' hatasından ayırt edilebilmeli."""
    result = runner.invoke(app, ["scan", "/yok/boyle/bir/yol"])
    assert result.exit_code == USAGE_ERROR


def test_file_instead_of_directory_is_rejected(tmp_path):
    target = tmp_path / "tek.py"
    target.write_text("x = 1\n", encoding="utf-8")
    assert runner.invoke(app, ["scan", str(target)]).exit_code == USAGE_ERROR


def test_output_dir_flag_is_accepted(project, tmp_path):
    result = runner.invoke(app, ["scan", str(project), "--output-dir", str(tmp_path / "out")])
    assert result.exit_code == NOT_IMPLEMENTED_EXIT


def test_explicit_config_flag_is_accepted(project, tmp_path):
    config = tmp_path / "custom.yaml"
    config.write_text("advise:\n  top_n: 2\n", encoding="utf-8")
    result = runner.invoke(app, ["scan", str(project), "--config", str(config)])
    assert result.exit_code == NOT_IMPLEMENTED_EXIT


def test_bad_config_fails_before_not_implemented(project):
    """Config hatası (exit 1), stub hatasından (exit 3) önce yakalanmalı."""
    (project / "rlens.yaml").write_text("advise:\n  top_n: 0\n", encoding="utf-8")
    result = runner.invoke(app, ["scan", str(project)])
    assert result.exit_code == 1
