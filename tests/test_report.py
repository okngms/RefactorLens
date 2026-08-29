"""Rapor çıktısı testleri: JSON dosyaları ve terminal biçimlendirme."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from rich.console import Console

from rlens.analysis.model import SCHEMA_VERSION, ClassReport, FunctionReport, ProjectReport
from rlens.analysis.scanner import scan_project
from rlens.config import load_config
from rlens.report.files import (
    ReportError,
    latest_report,
    list_reports,
    read_report,
    report_filename,
    write_report,
)
from rlens.report.terminal import (
    NULL_DISPLAY,
    class_violations,
    function_violations,
    render_report,
)

MESSY_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "messy_project"


@pytest.fixture
def config(tmp_path):
    return load_config(search_from=tmp_path)


@pytest.fixture
def report():
    return ProjectReport(
        root="/tmp/demo",
        generated_at="2026-08-29T12:00:00+00:00",
        rlens_version="0.1.0",
    )


# --------------------------------------------------------------------------- #
# Dosya çıktısı
# --------------------------------------------------------------------------- #


class TestReportFilename:
    def test_uses_timestamp(self):
        moment = datetime(2026, 8, 29, 14, 15, 30, tzinfo=UTC)
        assert report_filename(moment) == "scan-20260829-141530.json"

    def test_sorts_chronologically(self):
        """Ad sabit uzunlukta olduğu için alfabetik sıra = kronolojik sıra."""
        early = report_filename(datetime(2026, 1, 2, tzinfo=UTC))
        late = report_filename(datetime(2026, 11, 2, tzinfo=UTC))
        assert early < late


class TestWriteReport:
    def test_creates_missing_directory(self, report, tmp_path):
        target = tmp_path / "deep" / "reports"
        written = write_report(report, target)
        assert written.is_file()
        assert written.parent == target

    def test_written_json_has_schema_version_at_root(self, report, tmp_path):
        written = write_report(report, tmp_path)
        payload = json.loads(written.read_text(encoding="utf-8"))
        assert payload["schema_version"] == SCHEMA_VERSION
        assert payload["rlens_version"] == "0.1.0"

    def test_unicode_is_preserved(self, tmp_path):
        report = ProjectReport(
            root="/tmp/ölçüm",
            generated_at="2026-08-29T12:00:00+00:00",
            rlens_version="0.1.0",
        )
        written = write_report(report, tmp_path)
        assert "ölçüm" in written.read_text(encoding="utf-8")


class TestListAndLatest:
    def test_empty_directory(self, tmp_path):
        assert list_reports(tmp_path) == []
        assert latest_report(tmp_path) is None

    def test_missing_directory_is_not_an_error(self, tmp_path):
        assert list_reports(tmp_path / "yok") == []

    def test_latest_is_the_newest(self, tmp_path):
        for name in ("scan-20260101-000000.json", "scan-20260301-000000.json"):
            (tmp_path / name).write_text("{}", encoding="utf-8")
        assert latest_report(tmp_path).name == "scan-20260301-000000.json"

    def test_unrelated_files_are_ignored(self, tmp_path):
        (tmp_path / "notes.json").write_text("{}", encoding="utf-8")
        (tmp_path / "scan-20260101-000000.json").write_text("{}", encoding="utf-8")
        assert [p.name for p in list_reports(tmp_path)] == ["scan-20260101-000000.json"]


class TestReadReport:
    def test_round_trip(self, report, tmp_path):
        written = write_report(report, tmp_path)
        assert read_report(written)["root"] == "/tmp/demo"

    def test_missing_file(self, tmp_path):
        with pytest.raises(ReportError, match="Could not read report"):
            read_report(tmp_path / "yok.json")

    def test_invalid_json(self, tmp_path):
        broken = tmp_path / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        with pytest.raises(ReportError, match="Could not read report"):
            read_report(broken)

    def test_missing_schema_version_is_rejected(self, tmp_path):
        """Şema sürümü olmayan rapor sessizce kabul edilirse verify yanılır."""
        path = tmp_path / "old.json"
        path.write_text('{"root": "/tmp"}', encoding="utf-8")
        with pytest.raises(ReportError, match="schema_version"):
            read_report(path)

    def test_future_schema_version_is_rejected(self, tmp_path):
        path = tmp_path / "future.json"
        path.write_text(f'{{"schema_version": {SCHEMA_VERSION + 1}}}', encoding="utf-8")
        with pytest.raises(ReportError, match="schema version"):
            read_report(path)

    def test_non_object_payload_is_rejected(self, tmp_path):
        path = tmp_path / "list.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ReportError, match="not a JSON object"):
            read_report(path)


# --------------------------------------------------------------------------- #
# Eşik değerlendirmesi
# --------------------------------------------------------------------------- #


class TestViolations:
    def test_class_below_threshold_is_clean(self, config):
        cls = ClassReport(name="C", module="m", lineno=1, nom=2, wmc=3, lcom4=1, dcc=1)
        assert class_violations(cls, config) == {}

    def test_lcom4_warn_and_critical(self, config):
        warn = ClassReport(name="C", module="m", lineno=1, lcom4=2)
        critical = ClassReport(name="C", module="m", lineno=1, lcom4=5)
        assert class_violations(warn, config)["lcom4"] == "warn"
        assert class_violations(critical, config)["lcom4"] == "critical"

    def test_none_metric_never_violates(self, config):
        """Hesaplanamayan metrik ihlal üretmemeli."""
        cls = ClassReport(name="C", module="m", lineno=1, lcom4=None, dcc=None)
        assert class_violations(cls, config) == {}

    def test_function_complexity_violation(self, config):
        fn = FunctionReport(name="f", lineno=1, cyclomatic_complexity=15, param_count=2)
        assert function_violations(fn, config)["cyclomatic_complexity"] == "warn"

    def test_function_param_violation(self, config):
        fn = FunctionReport(name="f", lineno=1, cyclomatic_complexity=1, param_count=7)
        assert function_violations(fn, config)["param_count"] == "warn"

    def test_clean_function(self, config):
        fn = FunctionReport(
            name="f", lineno=1, cyclomatic_complexity=2, param_count=1, max_nesting=1
        )
        assert function_violations(fn, config) == {}


# --------------------------------------------------------------------------- #
# Terminal çıktısı
# --------------------------------------------------------------------------- #


def render_to_text(report, config) -> str:
    console = Console(width=120, no_color=True, record=True)
    render_report(report, config, console)
    return console.export_text()


@pytest.fixture(scope="module")
def messy():
    cfg = load_config(search_from=MESSY_PROJECT)
    return scan_project(MESSY_PROJECT, cfg), cfg


class TestTerminalOutput:
    def test_class_table_lists_every_class(self, messy):
        report, cfg = messy
        text = render_to_text(report, cfg)
        for name in ("OrderManager", "Customer", "ReportBuilder"):
            assert name in text

    def test_worst_class_is_listed_first(self, messy):
        report, cfg = messy
        text = render_to_text(report, cfg)
        assert text.index("OrderManager") < text.index("Invoice")

    def test_null_cam_is_not_shown_as_zero(self, messy):
        report, cfg = messy
        text = render_to_text(report, cfg)
        assert NULL_DISPLAY in text

    def test_cam_footnote_explains_the_reason(self, messy):
        report, cfg = messy
        text = render_to_text(report, cfg)
        assert "CAM not computed" in text

    def test_violating_functions_are_listed(self, messy):
        report, cfg = messy
        text = render_to_text(report, cfg)
        assert "classify_order" in text

    def test_clean_functions_are_not_listed(self, messy):
        """Tabloda yalnızca ihlaller olmalı; yüzlerce satır basılmamalı."""
        report, cfg = messy
        text = render_to_text(report, cfg)
        assert "is_premium" not in text

    def test_violation_count_is_reported(self, messy):
        report, cfg = messy
        assert "over threshold" in render_to_text(report, cfg)

    def test_empty_project_gives_guidance(self, tmp_path, config):
        report = scan_project(tmp_path, config)
        text = render_to_text(report, config)
        assert "No Python files found" in text

    def test_skipped_files_are_surfaced(self, tmp_path):
        (tmp_path / "bad.py").write_text("def f(\n", encoding="utf-8")
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        cfg = load_config(search_from=tmp_path)
        report = scan_project(tmp_path, cfg)
        text = render_to_text(report, cfg)
        assert "skipped" in text
        assert "bad.py" in text

    def test_partially_skipped_project_shows_both(self, tmp_path):
        (tmp_path / "good.py").write_text("class A:\n    pass\n", encoding="utf-8")
        (tmp_path / "bad.py").write_text("def f(\n", encoding="utf-8")
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        cfg = load_config(search_from=tmp_path)
        text = render_to_text(scan_project(tmp_path, cfg), cfg)
        assert "A" in text
        assert "bad.py" in text

    def test_clean_project_says_so(self, tmp_path):
        (tmp_path / "clean.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        cfg = load_config(search_from=tmp_path)
        report = scan_project(tmp_path, cfg)
        assert "Nothing over threshold" in render_to_text(report, cfg)


class TestPluralisation:
    """Yayınlanan bir araçta çoğul eki göze batar."""

    def test_singular_counts(self, tmp_path, config):
        (tmp_path / "one.py").write_text("x = 1\n", encoding="utf-8")
        text = render_to_text(scan_project(tmp_path, config), config)
        assert "1 module," in text
        assert "1 modules" not in text

    def test_plural_counts(self, tmp_path, config):
        for name in ("a.py", "b.py"):
            (tmp_path / name).write_text("x = 1\n", encoding="utf-8")
        assert "2 modules," in render_to_text(scan_project(tmp_path, config), config)

    def test_class_plural_is_not_classs(self, tmp_path, config):
        (tmp_path / "m.py").write_text("class A:\n    pass\n", encoding="utf-8")
        text = render_to_text(scan_project(tmp_path, config), config)
        assert "1 class," in text
        assert "classs" not in text
