"""CLI testleri.

`scan` artık gerçek iş yapıyor; testler hem komut yüzeyini hem uçtan uca akışı
kapsar. Çıkış kodları sözleşmeye göre ayrılmıştır (bkz. cli.py).
"""

import json
from pathlib import Path

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


class TestAdviseCommand:
    """`advise` komut yüzeyi.

    Gerçek sağlayıcıya çıkılmaz: `--dry-run` ağ gerektirmez, diğer testler
    sağlayıcıyı sahtesiyle değiştirir.
    """

    @pytest.fixture
    def messy(self):
        return str(Path(__file__).resolve().parent.parent / "examples" / "messy_project")

    def test_advise_appears_in_help(self):
        assert "advise" in runner.invoke(app, ["--help"]).output

    def test_dry_run_needs_no_api_key(self, messy, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        result = runner.invoke(app, ["advise", messy, "--dry-run", "--top-n", "1"])
        assert result.exit_code == 0
        assert "OrderManager" in result.output

    def test_dry_run_shows_the_evidence_block(self, messy):
        result = runner.invoke(app, ["advise", messy, "--dry-run", "--top-n", "1"])
        assert "LCOM4 = 4" in result.output
        assert "[CRITICAL]" in result.output

    def test_dry_run_hides_threshold_numbers(self, messy):
        """Goodhart azaltması komut düzeyinde de korunmalı."""
        result = runner.invoke(app, ["advise", messy, "--dry-run", "--top-n", "1"])
        assert "deliberately not shown" in result.output

    def test_unknown_provider_is_rejected(self, messy):
        result = runner.invoke(app, ["advise", messy, "--provider", "openai", "--dry-run"])
        assert result.exit_code == 1
        assert "Unknown provider" in result.output

    def test_clean_project_asks_nothing(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        (tmp_path / "ok.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        result = runner.invoke(app, ["advise", str(tmp_path)])
        assert result.exit_code == 0
        assert "Nothing over threshold" in result.output

    def test_missing_model_gives_actionable_error(self, messy, monkeypatch, tmp_path):
        """Model adı koda gömülmez; hata bunu söylemeli."""
        monkeypatch.setenv("GROQ_API_KEY", "key")
        config = tmp_path / "rlens.yaml"
        config.write_text(
            "scan:\n  exclude: ['tests/']\nprovider:\n  name: groq\n", encoding="utf-8"
        )
        result = runner.invoke(
            app, ["advise", messy, "--config", str(config), "--top-n", "1", "--no-report"]
        )
        assert result.exit_code == 1
        assert "provider.model" in result.output

    def test_dry_run_preserves_subscripts_in_code(self, messy):
        """rich markup kodu bozmamalı: --dry-run gönderilenle birebir aynı olmalı."""
        result = runner.invoke(app, ["advise", messy, "--dry-run", "--top-n", "1"])
        assert "self._orders[self._next_id] = order" in result.output
        assert "self._orders = order" not in result.output

    def test_dry_run_preserves_generic_annotations(self, messy):
        result = runner.invoke(app, ["advise", messy, "--dry-run", "--top-n", "1"])
        assert "tuple[str, ...]" in result.output

    def test_top_n_limits_the_targets(self, messy):
        result = runner.invoke(app, ["advise", messy, "--dry-run", "--top-n", "1"])
        assert result.output.count("--- system ---") == 1

    def test_missing_path_is_a_usage_error(self):
        assert runner.invoke(app, ["advise", "/yok/boyle"]).exit_code == USAGE_ERROR


class TestVerifyCommand:
    """`verify` komut yüzeyi ve uçtan uca döngü."""

    @pytest.fixture
    def project(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        (tmp_path / "m.py").write_text(
            "class C:\n"
            "    def __init__(self):\n        self.a = 1\n        self.b = 2\n"
            "    def touch_a(self):\n        return self.a\n"
            "    def touch_b(self):\n        return self.b\n",
            encoding="utf-8",
        )
        return tmp_path

    def improve(self, project):
        """LCOM4'ü 2'den 1'e indiren bir değişiklik."""
        (project / "m.py").write_text(
            "class C:\n"
            "    def __init__(self):\n        self.a = 1\n        self.b = 2\n"
            "    def touch_a(self):\n        return self.a\n"
            "    def touch_both(self):\n        return self.a + self.b\n",
            encoding="utf-8",
        )

    def test_verify_appears_in_help(self):
        assert "verify" in runner.invoke(app, ["--help"]).output

    def test_without_a_baseline_it_says_what_to_do(self, project):
        result = runner.invoke(app, ["verify", str(project)])
        assert result.exit_code == 1
        assert "rlens scan" in result.output

    def test_baseline_is_picked_automatically(self, project):
        runner.invoke(app, ["scan", str(project)])
        result = runner.invoke(app, ["verify", str(project), "--no-report"])
        assert result.exit_code == 0
        assert "baseline:" in result.output

    def test_full_loop_detects_the_improvement(self, project):
        runner.invoke(app, ["scan", str(project)])
        self.improve(project)
        result = runner.invoke(app, ["verify", str(project), "--no-report"])
        assert result.exit_code == 0
        assert "improved" in result.output

    def test_no_change_is_reported(self, project):
        runner.invoke(app, ["scan", str(project)])
        result = runner.invoke(app, ["verify", str(project), "--no-report"])
        assert "No metric changed" in result.output

    def test_prediction_check_runs_with_advice(self, project, tmp_path):
        runner.invoke(app, ["scan", str(project)])
        self.improve(project)
        advice_file = tmp_path / "advice.json"
        advice_file.write_text(
            json.dumps(
                {
                    "advices": [
                        {
                            "target": "m:C",
                            "suggestions": [
                                {
                                    "title": "Share state",
                                    "expected_effect": [{"metric": "LCOM4", "direction": "down"}],
                                }
                            ],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = runner.invoke(
            app, ["verify", str(project), "--advice", str(advice_file), "--no-report"]
        )
        assert result.exit_code == 0
        assert "prediction accuracy: 1/1" in result.output

    def test_applied_filter_is_parsed(self, project, tmp_path):
        runner.invoke(app, ["scan", str(project)])
        advice_file = tmp_path / "advice.json"
        advice_file.write_text('{"advices": []}', encoding="utf-8")
        result = runner.invoke(
            app,
            [
                "verify",
                str(project),
                "--advice",
                str(advice_file),
                "--applied",
                "m:C=1",
                "--no-report",
            ],
        )
        assert result.exit_code == 0

    def test_malformed_applied_is_rejected(self, project, tmp_path):
        runner.invoke(app, ["scan", str(project)])
        advice_file = tmp_path / "advice.json"
        advice_file.write_text('{"advices": []}', encoding="utf-8")
        result = runner.invoke(
            app,
            [
                "verify",
                str(project),
                "--advice",
                str(advice_file),
                "--applied",
                "nonsense",
                "--no-report",
            ],
        )
        assert result.exit_code == 1
        assert "TARGET=INDEX" in result.output

    def test_reports_are_written(self, project):
        runner.invoke(app, ["scan", str(project)])
        runner.invoke(app, ["verify", str(project)])
        assert list((project / "reports").glob("verify-*.md"))
        assert list((project / "reports").glob("verify-*.json"))

    def test_fail_on_regression(self, project):
        runner.invoke(app, ["scan", str(project)])
        (project / "m.py").write_text(
            "class C:\n"
            "    def __init__(self):\n        self.a = 1\n        self.b = 2\n"
            "        self.c = 3\n"
            "    def touch_a(self):\n        return self.a\n"
            "    def touch_b(self):\n        return self.b\n"
            "    def touch_c(self):\n        return self.c\n",
            encoding="utf-8",
        )
        result = runner.invoke(app, ["verify", str(project), "--no-report", "--fail-on-regression"])
        assert result.exit_code == 1

    def test_fail_on_regression_passes_when_clean(self, project):
        runner.invoke(app, ["scan", str(project)])
        self.improve(project)
        result = runner.invoke(app, ["verify", str(project), "--no-report", "--fail-on-regression"])
        assert result.exit_code == 0

    def test_report_without_schema_version_is_rejected(self, project):
        reports = project / "reports"
        reports.mkdir()
        (reports / "scan-20260101-000000.json").write_text('{"modules": []}', encoding="utf-8")
        result = runner.invoke(app, ["verify", str(project), "--no-report"])
        assert result.exit_code == 1
        assert "schema_version" in result.output


class TestAdviseBudgetAndCache:
    """Aşama 0 kabul kriteri: --dry-run bütçe/önbellek özetini basar."""

    @pytest.fixture
    def messy(self):
        return str(Path(__file__).resolve().parent.parent / "examples" / "messy_project")

    def test_dry_run_prints_the_budget_summary(self, messy):
        result = runner.invoke(app, ["advise", messy, "--dry-run", "--top-n", "2"])
        assert result.exit_code == 0
        assert "budget 10 calls" in result.output
        assert "2 target(s)" in result.output

    def test_dry_run_reports_cache_state(self, messy):
        result = runner.invoke(app, ["advise", messy, "--dry-run", "--top-n", "1"])
        assert "cache" in result.output

    def test_no_cache_flag_is_accepted(self, messy):
        result = runner.invoke(app, ["advise", messy, "--dry-run", "--top-n", "1", "--no-cache"])
        assert result.exit_code == 0

    def test_oversized_prompt_is_flagged_in_dry_run(self, messy, tmp_path):
        """Çağrı başına token tavanı aşılıyorsa ağa çıkmadan önce söylenir."""
        config = tmp_path / "tight.yaml"
        config.write_text(
            "scan:\n  exclude: ['tests/']\nbudget:\n  max_tokens_per_call: 500\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["advise", messy, "--config", str(config), "--dry-run", "--top-n", "1"],
        )
        assert "exceed the per-call token ceiling" in result.output


class TestArchCommand:
    """Aşama 1b kabul kriteri: altı ihlal kodlarıyla basılır, fazlası basılmaz."""

    @pytest.fixture
    def layered(self):
        return str(Path(__file__).resolve().parent.parent / "examples" / "layered_project")

    def test_arch_appears_in_help(self):
        assert "arch" in runner.invoke(app, ["--help"]).output

    def test_six_violations_are_printed(self, layered):
        result = runner.invoke(app, ["arch", layered, "--no-report"])
        assert result.exit_code == 0
        assert "6 violation(s)" in result.output

    def test_every_code_appears(self, layered):
        output = runner.invoke(app, ["arch", layered, "--no-report"]).output
        for code in ("LV-DIR", "LV-SKIP", "LV-CYCLE", "LV-LEAK"):
            assert code in output

    def test_layer_map_is_printed(self, layered):
        output = runner.invoke(app, ["arch", layered, "--no-report"]).output
        assert "presentation" in output
        assert "declared" in output

    def test_report_is_written_by_default(self, layered, tmp_path):
        result = runner.invoke(app, ["arch", layered, "--output-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert list(tmp_path.glob("arch-*.json"))

    def test_no_report_writes_nothing(self, layered, tmp_path):
        runner.invoke(app, ["arch", layered, "--no-report", "--output-dir", str(tmp_path)])
        assert not list(tmp_path.glob("arch-*.json"))

    def test_fail_on_violation_exits_one(self, layered):
        result = runner.invoke(app, ["arch", layered, "--no-report", "--fail-on-violation"])
        assert result.exit_code == 1

    def test_clean_project_passes_the_gate(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        result = runner.invoke(app, ["arch", str(tmp_path), "--no-report", "--fail-on-violation"])
        assert result.exit_code == 0

    def test_missing_path_is_a_usage_error(self):
        assert runner.invoke(app, ["arch", "/yok/boyle"]).exit_code == USAGE_ERROR

    def test_bad_config_exits_one(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text("advise:\n  top_n: 0\n", encoding="utf-8")
        assert runner.invoke(app, ["arch", str(tmp_path)]).exit_code == 1
