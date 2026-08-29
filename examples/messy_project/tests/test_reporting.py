"""reporting.py davranış testleri."""

import pytest
from reporting import ReportBuilder


def test_render_empty_is_blank():
    assert ReportBuilder().render() == ""


def test_add_line_then_render():
    builder = ReportBuilder()
    builder.add_line("first")
    builder.add_line("second")
    assert builder.render() == "first\nsecond"


def test_reset_clears_body_only():
    builder = ReportBuilder()
    builder.set_title("Sales")
    builder.add_line("row")
    builder.reset()
    assert builder.render() == ""
    assert "Sales" in builder.header()


def test_default_header_is_centered_to_default_width():
    header = ReportBuilder().header()
    assert len(header) == 40
    assert "Report" in header


def test_set_width_changes_header_length():
    builder = ReportBuilder()
    builder.set_width(10)
    assert len(builder.header()) == 10


def test_width_must_be_positive():
    with pytest.raises(ValueError):
        ReportBuilder().set_width(0)
