"""Öneri raporunun sunumu: terminal, markdown ve dosya çıktısı."""

import json

from rich.console import Console

from rlens.advise.advisor import (
    UNSTRUCTURED,
    Advice,
    AdviceDocument,
    ExpectedEffect,
    Suggestion,
)
from rlens.analysis.model import ADVICE_SCHEMA_VERSION
from rlens.report.advice import advice_markdown, render_advice
from rlens.report.files import latest_advice, write_advice


def make_document(*advices: Advice) -> AdviceDocument:
    return AdviceDocument(
        root="/tmp/demo",
        generated_at="2026-08-29T12:00:00+00:00",
        rlens_version="0.1.0",
        provider="groq",
        model="test-model",
        temperature=0.2,
        advices=list(advices),
    )


def linked_advice() -> Advice:
    return Advice(
        target="god:OrderManager",
        diagnosis="Four disjoint responsibilities.",
        suggestions=[
            Suggestion(
                title="Extract AuditLog",
                rationale_metric_link=["LCOM4"],
                expected_effect=[
                    ExpectedEffect("LCOM4", "down"),
                    ExpectedEffect("DCC", "up"),
                ],
                sketch="Move _log into its own class.",
            )
        ],
        risk_notes="Callers must be updated.",
    )


def render_to_text(document) -> str:
    console = Console(width=120, no_color=True, record=True)
    render_advice(document, console)
    return console.export_text()


class TestTerminal:
    def test_target_and_diagnosis_appear(self):
        text = render_to_text(make_document(linked_advice()))
        assert "god:OrderManager" in text
        assert "Four disjoint responsibilities" in text

    def test_prediction_is_shown_for_every_suggestion(self):
        """expected_effect projenin ana ölçümüdür; sıradan bir alan değildir."""
        text = render_to_text(make_document(linked_advice()))
        assert "predicts:" in text
        assert "LCOM4" in text and "DCC" in text

    def test_evidence_metrics_are_shown(self):
        assert "evidence: LCOM4" in render_to_text(make_document(linked_advice()))

    def test_provider_and_temperature_are_recorded(self):
        text = render_to_text(make_document(linked_advice()))
        assert "groq" in text
        assert "0.2" in text

    def test_unlinked_suggestion_is_marked(self):
        advice = Advice(
            target="m:C",
            suggestions=[Suggestion(title="Cosmetic tidy-up")],
        )
        text = render_to_text(make_document(advice))
        assert "unlinked" in text
        assert "not linked to any metric" in text

    def test_missing_prediction_is_stated_not_hidden(self):
        advice = Advice(
            target="m:C",
            suggestions=[Suggestion(title="X", rationale_metric_link=["WMC"])],
        )
        assert "no prediction" in render_to_text(make_document(advice))

    def test_unstructured_reply_is_reported(self):
        advice = Advice(target="m:C", tags=[UNSTRUCTURED], raw_reply="sorry")
        assert "could not be parsed" in render_to_text(make_document(advice))

    def test_truncation_is_surfaced(self):
        advice = linked_advice()
        advice.truncation_notes = ["C.big body omitted"]
        assert "truncated" in render_to_text(make_document(advice))

    def test_repair_round_is_surfaced(self):
        advice = linked_advice()
        advice.repaired = True
        assert "repair" in render_to_text(make_document(advice))

    def test_warnings_are_surfaced(self):
        advice = linked_advice()
        advice.warnings = ["unknown metric in expected_effect: VIBES"]
        assert "VIBES" in render_to_text(make_document(advice))


class TestMarkdown:
    def test_has_a_title_and_metadata(self):
        markdown = advice_markdown(make_document(linked_advice()))
        assert markdown.startswith("# RefactorLens suggestions")
        assert "test-model" in markdown
        assert "0.1.0" in markdown

    def test_explains_the_verify_loop(self):
        markdown = advice_markdown(make_document(linked_advice()))
        assert "verify --advice" in markdown

    def test_suggestion_sections(self):
        markdown = advice_markdown(make_document(linked_advice()))
        assert "### 1. Extract AuditLog" in markdown
        assert "**Evidence:** LCOM4" in markdown
        assert "**Predicted effect:** LCOM4 down, DCC up" in markdown

    def test_risks_are_included(self):
        assert "**Risks:**" in advice_markdown(make_document(linked_advice()))

    def test_unlinked_is_flagged_in_the_header_and_body(self):
        advice = Advice(target="m:C", suggestions=[Suggestion(title="Tidy")])
        markdown = advice_markdown(make_document(advice))
        assert "not linked to any metric" in markdown

    def test_unstructured_reply_keeps_the_raw_text(self):
        """Ham metin atılmaz."""
        advice = Advice(target="m:C", tags=[UNSTRUCTURED], raw_reply="I refuse")
        assert "I refuse" in advice_markdown(make_document(advice))

    def test_ends_with_a_newline(self):
        assert advice_markdown(make_document(linked_advice())).endswith("\n")


class TestFiles:
    def test_writes_both_json_and_markdown(self, tmp_path):
        json_path, markdown_path = write_advice(make_document(linked_advice()), tmp_path)
        assert json_path.is_file()
        assert markdown_path.is_file()
        assert json_path.stem == markdown_path.stem

    def test_json_carries_its_own_schema_version(self, tmp_path):
        """Öneri şeması tarama şemasından ayrıdır."""
        json_path, _ = write_advice(make_document(linked_advice()), tmp_path)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == ADVICE_SCHEMA_VERSION

    def test_json_preserves_the_structured_prediction(self, tmp_path):
        """verify --advice bu alanı makine olarak okuyacak."""
        json_path, _ = write_advice(make_document(linked_advice()), tmp_path)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        effect = payload["advices"][0]["suggestions"][0]["expected_effect"][0]
        assert effect == {"metric": "LCOM4", "direction": "down"}

    def test_provider_settings_are_recorded(self, tmp_path):
        """Faz 5 'hangi model, hangi ayarla' sorusuna cevap verebilmeli."""
        json_path, _ = write_advice(make_document(linked_advice()), tmp_path)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["provider"] == "groq"
        assert payload["model"] == "test-model"
        assert payload["temperature"] == 0.2

    def test_creates_missing_directory(self, tmp_path):
        json_path, _ = write_advice(make_document(linked_advice()), tmp_path / "deep" / "out")
        assert json_path.is_file()

    def test_latest_advice_finds_the_newest(self, tmp_path):
        for name in ("advice-20260101-000000.json", "advice-20260301-000000.json"):
            (tmp_path / name).write_text("{}", encoding="utf-8")
        assert latest_advice(tmp_path).name == "advice-20260301-000000.json"

    def test_latest_advice_ignores_scan_reports(self, tmp_path):
        (tmp_path / "scan-20260301-000000.json").write_text("{}", encoding="utf-8")
        assert latest_advice(tmp_path) is None

    def test_missing_directory_is_not_an_error(self, tmp_path):
        assert latest_advice(tmp_path / "nope") is None


class TestCounts:
    def test_suggestion_and_unlinked_counts(self):
        document = make_document(
            linked_advice(),
            Advice(target="m:C", suggestions=[Suggestion(title="Tidy")]),
        )
        assert document.suggestion_count == 2
        assert document.unlinked_count == 1


class TestMarkupSafety:
    """rich köşeli parantezi biçim etiketi sanar; modelin metni kaçışlanmalı.

    Bu hata sessizdir: kullanıcı `self._orders[key]` yerine `self._orders`
    görür ve yanlış kod okuduğunu fark etmez.
    """

    def test_brackets_in_sketch_survive(self):
        advice = Advice(
            target="m:C",
            suggestions=[
                Suggestion(
                    title="Fix indexing",
                    rationale_metric_link=["WMC"],
                    sketch="Replace self._orders[key] with a lookup helper.",
                )
            ],
        )
        assert "self._orders[key]" in render_to_text(make_document(advice))

    def test_brackets_in_diagnosis_survive(self):
        advice = Advice(target="m:C", diagnosis="The type is list[str], not list.")
        assert "list[str]" in render_to_text(make_document(advice))

    def test_brackets_in_title_survive(self):
        advice = Advice(
            target="m:C",
            suggestions=[Suggestion(title="Use dict[str, int]", rationale_metric_link=["NOM"])],
        )
        assert "dict[str, int]" in render_to_text(make_document(advice))

    def test_brackets_in_risk_notes_survive(self):
        advice = Advice(target="m:C", risk_notes="Callers of items[0] break.")
        assert "items[0]" in render_to_text(make_document(advice))

    def test_brackets_in_warnings_survive(self):
        advice = Advice(target="m:C", warnings=["dropped effect for [unknown]"])
        assert "[unknown]" in render_to_text(make_document(advice))

    def test_markdown_is_unaffected(self):
        """Markdown rich'ten geçmez; kaçışlama oraya sızmamalı."""
        advice = Advice(
            target="m:C",
            suggestions=[
                Suggestion(
                    title="X",
                    rationale_metric_link=["WMC"],
                    sketch="Use items[0] here.",
                )
            ],
        )
        markdown = advice_markdown(make_document(advice))
        assert "items[0]" in markdown
        assert "\\[" not in markdown
