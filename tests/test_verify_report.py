"""Doğrulama raporunun sunumu."""

import json

import pytest
from rich.console import Console

from rlens.analysis.model import SCHEMA_VERSION
from rlens.report.files import write_verify
from rlens.report.verify import BEHAVIOUR_REMINDER, render_verify, verify_markdown
from rlens.verify.diff import diff_reports
from rlens.verify.prediction import check_predictions


def report(*classes, schema=SCHEMA_VERSION, at="2026-01-01T00:00:00+00:00"):
    return {
        "schema_version": schema,
        "generated_at": at,
        "modules": [{"module": "m", "path": "m.py", "classes": list(classes), "functions": []}],
    }


def cls(name="C", **metrics):
    base = {"name": name, "nom": 5, "wmc": 10, "lcom4": 4, "dam": 0.5, "dcc": 3, "cam": 0.5}
    base.update(metrics)
    return base


def advice(*effects, target="m:C"):
    return {
        "advices": [
            {
                "target": target,
                "suggestions": [
                    {
                        "title": "Split it",
                        "expected_effect": [{"metric": m, "direction": d} for m, d in effects],
                    }
                ],
            }
        ]
    }


def render_to_text(delta, predictions=None) -> str:
    console = Console(width=120, no_color=True, record=True)
    render_verify(delta, console, predictions)
    return console.export_text()


@pytest.fixture
def improved():
    return diff_reports(report(cls(lcom4=4)), report(cls(lcom4=1)))


class TestTerminal:
    def test_timestamps_are_shown(self, improved):
        assert "before" in render_to_text(improved)

    def test_changed_entity_and_verdict(self, improved):
        text = render_to_text(improved)
        assert "m:C" in text
        assert "improved" in text

    def test_before_and_after_values_are_shown(self, improved):
        assert "LCOM4 4→1" in render_to_text(improved)

    def test_no_change_says_so(self):
        delta = diff_reports(report(cls()), report(cls()))
        assert "No metric changed" in render_to_text(delta)

    def test_mixed_verdict_is_not_hidden(self):
        delta = diff_reports(report(cls(lcom4=4, dcc=3)), report(cls(lcom4=1, dcc=9)))
        assert "mixed" in render_to_text(delta)

    def test_added_classes_are_listed(self):
        delta = diff_reports(report(cls("A")), report(cls("A"), cls("B")))
        assert "new:" in render_to_text(delta)

    def test_removed_classes_are_listed(self):
        delta = diff_reports(report(cls("A"), cls("B")), report(cls("A")))
        assert "gone:" in render_to_text(delta)

    def test_incompatibility_is_prominent(self):
        """Şema uyumsuzluğu görülmeden geçilememeli."""
        delta = diff_reports(report(cls(), schema=1), report(cls(), schema=2))
        text = render_to_text(delta)
        assert "Not comparable" in text
        assert "do not draw conclusions" in text

    def test_behaviour_reminder_is_always_present(self, improved):
        assert BEHAVIOUR_REMINDER.split(".")[0] in render_to_text(improved)


class TestPredictionOutput:
    def test_hit_and_miss_are_shown(self):
        delta = diff_reports(report(cls(lcom4=4, dcc=3)), report(cls(lcom4=1, dcc=9)))
        predictions = check_predictions(advice(("LCOM4", "down"), ("DCC", "down")), delta)
        text = render_to_text(delta, predictions)
        assert "LCOM4" in text and "DCC" in text
        assert "50%" in text

    def test_accuracy_line(self):
        delta = diff_reports(report(cls(lcom4=4)), report(cls(lcom4=1)))
        predictions = check_predictions(advice(("LCOM4", "down")), delta)
        assert "prediction accuracy: 1/1 (100%)" in render_to_text(delta, predictions)

    def test_unverifiable_count_is_disclosed(self):
        delta = diff_reports(report(cls(cam=None)), report(cls(cam=None)))
        predictions = check_predictions(advice(("CAM", "up")), delta)
        text = render_to_text(delta, predictions)
        assert "could not be verified" in text

    def test_no_verifiable_prediction_does_not_print_zero_percent(self):
        delta = diff_reports(report(cls(cam=None)), report(cls(cam=None)))
        predictions = check_predictions(advice(("CAM", "up")), delta)
        text = render_to_text(delta, predictions)
        assert "0%" not in text

    def test_unfiltered_run_warns_about_bias(self):
        """Uygulanmamış öneriler puanlandıysa kullanıcı bilmeli."""
        delta = diff_reports(report(cls(lcom4=4)), report(cls(lcom4=1)))
        predictions = check_predictions(advice(("LCOM4", "down")), delta)
        assert "--applied" in render_to_text(delta, predictions)

    def test_filtered_run_does_not_warn(self):
        delta = diff_reports(report(cls(lcom4=4)), report(cls(lcom4=1)))
        predictions = check_predictions(advice(("LCOM4", "down")), delta, applied={"m:C": [1]})
        assert "--applied" not in render_to_text(delta, predictions)


class TestMarkdown:
    def test_title_and_timestamps(self, improved):
        markdown = verify_markdown(improved)
        assert markdown.startswith("# RefactorLens verification")
        assert "**Before:**" in markdown

    def test_delta_table(self, improved):
        assert "| `m:C` | improved |" in verify_markdown(improved)

    def test_prediction_table_with_reasons(self):
        delta = diff_reports(report(cls(cam=None)), report(cls(cam=None)))
        predictions = check_predictions(advice(("CAM", "up")), delta)
        markdown = verify_markdown(delta, predictions)
        assert "unverifiable" in markdown
        assert "could not be computed" in markdown

    def test_overall_section(self):
        delta = diff_reports(report(cls(lcom4=4)), report(cls(lcom4=1)))
        predictions = check_predictions(advice(("LCOM4", "down")), delta)
        markdown = verify_markdown(delta, predictions)
        assert "**Accuracy: 100%**" in markdown
        assert "excluded from the ratio" in markdown

    def test_incompatibility_block(self):
        delta = diff_reports(report(cls(), schema=1), report(cls(), schema=2))
        assert "**Not comparable.**" in verify_markdown(delta)

    def test_behaviour_reminder(self, improved):
        assert BEHAVIOUR_REMINDER.split(".")[0] in verify_markdown(improved)

    def test_ends_with_newline(self, improved):
        assert verify_markdown(improved).endswith("\n")


class TestFiles:
    def test_writes_both_formats(self, improved, tmp_path):
        json_path, markdown_path = write_verify(improved, None, tmp_path)
        assert json_path.is_file() and markdown_path.is_file()
        assert json_path.stem == markdown_path.stem

    def test_json_contains_delta_and_predictions(self, tmp_path):
        delta = diff_reports(report(cls(lcom4=4)), report(cls(lcom4=1)))
        predictions = check_predictions(advice(("LCOM4", "down")), delta)
        json_path, _ = write_verify(delta, predictions, tmp_path)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["delta"]["entities"][0]["verdict"] == "improved"
        assert payload["predictions"]["accuracy"] == 1.0

    def test_predictions_may_be_absent(self, improved, tmp_path):
        json_path, _ = write_verify(improved, None, tmp_path)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["predictions"] is None


def with_interface(name="C", members=("a", "b"), **metrics):
    payload = cls(name=name, **metrics)
    payload["public_interface"] = {
        "methods": list(members),
        "attributes": [],
        "accessors": [],
        "size": len(members),
    }
    return payload


class TestSuspiciousOutput:
    """FINDINGS-1'in vakası rapora nasıl yansıyor."""

    @pytest.fixture
    def suspicious(self):
        from rlens.verify import goodhart

        before = report(with_interface(lcom4=4, members=("place", "get", "log")))
        after = report(with_interface(lcom4=1, members=("place",)))
        delta = diff_reports(before, after)
        return delta, goodhart.detect(before, after, delta.entities)

    def test_it_is_announced(self, suspicious):
        delta, checks = suspicious
        console = Console(width=120, no_color=True, record=True)
        render_verify(delta, console, None, checks)
        output = console.export_text()
        assert "1 suspicious improvement(s)" in output
        assert "public interface shrank" in output

    def test_the_lost_members_are_named(self, suspicious):
        delta, checks = suspicious
        console = Console(width=120, no_color=True, record=True)
        render_verify(delta, console, None, checks)
        assert "get" in console.export_text()

    def test_it_is_framed_as_a_question(self, suspicious):
        """Ölü kod silmek de arayüzü küçültür; suçlama değil soru."""
        delta, checks = suspicious
        console = Console(width=120, no_color=True, record=True)
        render_verify(delta, console, None, checks)
        assert "question, not a verdict" in console.export_text()

    def test_markdown_section(self, suspicious):
        delta, checks = suspicious
        markdown = verify_markdown(delta, None, checks)
        assert "## Suspicious improvements" in markdown

    def test_nothing_shown_when_clean(self):
        from rlens.verify import goodhart

        before = report(with_interface(lcom4=4))
        after = report(with_interface(lcom4=1))
        delta = diff_reports(before, after)
        checks = goodhart.detect(before, after, delta.entities)
        console = Console(width=120, no_color=True, record=True)
        render_verify(delta, console, None, checks)
        assert "suspicious" not in console.export_text()


class TestCalibrationOutput:
    @pytest.fixture
    def calibration(self):
        from rlens.verify.calibration import CalibrationPoint, calibrate

        return calibrate(
            [CalibrationPoint(0.9, False), CalibrationPoint(0.9, True)],
            without_confidence=2,
        )

    def test_scores_are_printed(self, calibration, improved):
        console = Console(width=120, no_color=True, record=True)
        render_verify(improved, console, None, None, calibration)
        output = console.export_text()
        assert "Brier" in output and "ECE" in output

    def test_bucket_table(self, calibration, improved):
        console = Console(width=120, no_color=True, record=True)
        render_verify(improved, console, None, None, calibration)
        assert "Confidence calibration" in console.export_text()

    def test_predictions_without_confidence_are_disclosed(self, calibration, improved):
        console = Console(width=120, no_color=True, record=True)
        render_verify(improved, console, None, None, calibration)
        assert "without a confidence" in console.export_text()

    def test_markdown_includes_the_table(self, calibration, improved):
        markdown = verify_markdown(improved, None, None, calibration)
        assert "## Confidence calibration" in markdown
        assert "coin flip" in markdown

    def test_nothing_shown_without_confidences(self, improved):
        from rlens.verify.calibration import calibrate

        console = Console(width=120, no_color=True, record=True)
        render_verify(improved, console, None, None, calibrate([]))
        assert "Brier" not in console.export_text()


class TestSetDeltaOutput:
    def test_resolved_violation_is_shown(self):
        before = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": "2026-01-01T00:00:00+00:00",
            "violations": [{"code": "LV-DIR", "source": "a", "target": "b"}],
            "modules": [{"module": "m", "path": "m.py", "classes": [cls()], "functions": []}],
        }
        after = dict(before, violations=[])
        delta = diff_reports(before, after)
        console = Console(width=120, no_color=True, record=True)
        render_verify(delta, console)
        output = console.export_text()
        assert "Architecture and smells" in output
        assert "LV-DIR a → b" in output
