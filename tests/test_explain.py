"""`explain` prompt'u ve ayrıştırıcısı.

En kritik test `TestNoRawThresholds`: eşik sayıları prompt'a **hiçbir yoldan**
girmemeli. `advise` tarafında bu bir kez sızdı (`dcc_threshold`, bir smell'in
evidence alanı üzerinden) ve blok kapsamlı test bunu görmedi. Buradaki test
prompt'un **tamamını** tarar.
"""

from __future__ import annotations

import pytest

from rlens.analysis.model import ADVICE_SCHEMA_VERSION, EXPLAIN_SCHEMA_VERSION
from rlens.explain.explainer import LINKED, UNLINKED, graded_terms, parse_explanation
from rlens.explain.prompts import (
    NOT_COMPUTED,
    SYSTEM_INSTRUCTION,
    build_user_prompt,
    format_metrics,
    format_smell,
)


@pytest.fixture
def report() -> dict:
    return {
        "root": "src",
        "modules": [
            {
                "module": "services.order_service",
                "classes": [
                    {
                        "name": "OrderService",
                        "nom": 26,
                        "wmc": 56,
                        "lcom4": 5,
                        "dam": 0.4,
                        "dcc": 4,
                        "cam": None,
                        "cam_skipped_reason": "no_annotated_parameters",
                        "smells": [
                            {
                                "label": "god_class",
                                "evidence": {
                                    "nom": 26,
                                    "wmc": 56,
                                    "lcom4": 5,
                                    "thresholds": {"nom": 20, "wmc": 50, "lcom4": 3},
                                },
                            }
                        ],
                    }
                ],
            }
        ],
        "violations": [
            {
                "code": "LV-CYCLE",
                "source": "shared.helpers",
                "target": "shared.registry",
                "tentative": False,
            }
        ],
    }


class TestNoRawThresholds:
    """Ham eşik sayıları prompt'a girmez — tüm prompt taranır."""

    def test_threshold_values_are_absent(self, report):
        prompt = build_user_prompt(report)
        assert "thresholds" not in prompt
        # 20 / 50 / 3 eşik değerleri; ölçülen 26 / 56 / 5 basılmalı.
        assert "nom=20" not in prompt
        assert "wmc=50" not in prompt

    def test_measured_values_are_present(self, report):
        prompt = build_user_prompt(report)
        assert "NOM=26" in prompt
        assert "WMC=56" in prompt

    def test_smell_evidence_drops_nested_fields(self):
        line = format_smell("god_class", {"nom": 26, "thresholds": {"nom": 20}})
        assert "nom=26" in line
        assert "20" not in line

    def test_an_unknown_evidence_key_does_not_leak(self):
        # Beyaz liste: yeni bir alan varsayılan olarak basılmaz.
        line = format_smell("new_smell", {"dcc_threshold": 7})
        assert "7" not in line


class TestUncomputableMetrics:
    def test_none_is_not_printed_as_zero(self):
        line = format_metrics({"CAM": None, "NOM": 3})
        assert f"CAM={NOT_COMPUTED}" in line
        assert "CAM=0" not in line

    def test_the_reason_reaches_the_prompt(self, report):
        assert "no_annotated_parameters" in build_user_prompt(report)

    def test_the_model_is_told_not_to_read_it_as_low(self):
        assert "never describe it as low" in SYSTEM_INSTRUCTION


class TestNoGradingOrAdvice:
    """Derecelendirme ve öneri yasağı talimatta yazılı olmalı."""

    def test_grading_is_forbidden(self):
        assert "Describe, do not grade" in SYSTEM_INSTRUCTION

    def test_suggestions_are_forbidden(self):
        assert "Do not suggest changes" in SYSTEM_INSTRUCTION

    def test_the_schema_has_no_suggestion_field(self, report):
        prompt = build_user_prompt(report)
        assert "suggestions" not in prompt
        assert "expected_effect" not in prompt

    def test_the_forbidden_adjectives_are_named(self):
        # İlk gerçek koşuda model "low", "limited", "fragmented" ve "moderate"
        # kullandı; talimat artık dördünü de birebir sayıyor.
        for word in ("low", "limited", "fragmented", "moderate"):
            assert word in SYSTEM_INSTRUCTION

    def test_a_rewrite_example_is_given(self):
        assert "Not this:" in SYSTEM_INSTRUCTION


class TestPromptContent:
    def test_violations_are_listed(self, report):
        assert "LV-CYCLE" in build_user_prompt(report)

    def test_truncation_is_announced(self, report):
        prompt = build_user_prompt(report, max_classes=0)
        assert "showing 0 of 1 classes" in prompt

    def test_no_truncation_notice_when_everything_fits(self, report):
        assert "omitted" not in build_user_prompt(report)


class TestGradedLanguage:
    """Talimat çiğnendiğinde sessiz kalınmaz, sayılır."""

    def test_a_forbidden_adjective_is_detected(self):
        assert graded_terms("LCOM4=4 indicates low cohesion") == ["low"]

    def test_word_boundaries_are_respected(self):
        # "lower" ve "slowly" derecelendirme değil; liste kaba olmamalı.
        assert graded_terms("the lower half slowly grows") == []

    def test_a_neutral_statement_is_clean(self):
        assert graded_terms("LCOM4=4 means four groups share no attribute") == []

    def test_the_finding_is_kept_and_tagged(self):
        reply = """{"findings": [{"statement": "DAM=0.2 is low.",
            "subjects": ["a:B"], "metric_link": ["DAM"]}]}"""
        explanation, warnings = parse_explanation(reply)
        assert len(explanation.findings) == 1
        assert explanation.findings[0].graded == ["low"]
        assert explanation.graded_count == 1
        assert any("grading language" in w for w in warnings)

    def test_it_reaches_the_payload(self):
        reply = """{"findings": [{"statement": "WMC=56 is high.",
            "subjects": ["a:B"], "metric_link": ["WMC"]}]}"""
        explanation, _ = parse_explanation(reply)
        assert explanation.to_dict()["findings"][0]["graded_terms"] == ["high"]
        assert explanation.to_dict()["graded_count"] == 1


class TestTableRestatement:
    """Tek ölçüme ve tek özneye dayanan tespit sayılır."""

    def test_a_single_metric_single_subject_finding_is_counted(self):
        reply = """{"findings": [{"statement": "It has 3 methods.",
            "subjects": ["a:B"], "metric_link": ["NOM"]}]}"""
        explanation, _ = parse_explanation(reply)
        assert explanation.single_metric_count == 1

    def test_two_metrics_do_not_count(self):
        reply = """{"findings": [{"statement": "st",
            "subjects": ["a:B"], "metric_link": ["NOM", "WMC"]}]}"""
        explanation, _ = parse_explanation(reply)
        assert explanation.single_metric_count == 0

    def test_two_subjects_do_not_count(self):
        reply = """{"findings": [{"statement": "st",
            "subjects": ["a:B", "c:D"], "metric_link": ["NOM"]}]}"""
        explanation, _ = parse_explanation(reply)
        assert explanation.single_metric_count == 0


class TestParsing:
    def test_a_linked_finding_is_kept(self):
        reply = """{"summary": "s", "findings": [
            {"statement": "st", "subjects": ["a:B", "c:D"],
             "metric_link": ["LCOM4"]}], "not_shown": "n"}"""
        explanation, warnings = parse_explanation(reply)
        assert warnings == []
        assert explanation.findings[0].status == LINKED
        assert explanation.findings[0].subjects == ["a:B", "c:D"]
        assert explanation.summary == "s"

    def test_an_unlinked_finding_is_tagged_not_dropped(self):
        reply = """{"findings": [{"statement": "st", "subjects": ["a:B"]}]}"""
        explanation, _ = parse_explanation(reply)
        assert len(explanation.findings) == 1
        assert explanation.findings[0].status == UNLINKED
        assert explanation.unlinked_count == 1

    def test_a_singular_subject_key_is_accepted(self):
        # Eski şemayı hatırlayan bir model yüzünden tespiti kaybetmeyiz.
        reply = """{"findings": [{"statement": "st", "subject": "a:B",
            "metric_link": ["NOM"]}]}"""
        explanation, _ = parse_explanation(reply)
        assert explanation.findings[0].subjects == ["a:B"]

    def test_an_invented_metric_name_is_dropped_with_a_warning(self):
        reply = """{"findings": [
            {"statement": "st", "subjects": ["a:B"], "metric_link": ["ELEGANCE", "wmc"]}]}"""
        explanation, warnings = parse_explanation(reply)
        assert explanation.findings[0].metric_link == ["WMC"]
        assert any("ELEGANCE" in w for w in warnings)

    def test_an_unparseable_reply_keeps_its_raw_text(self):
        explanation, warnings = parse_explanation("I cannot help with that.")
        assert explanation.is_structured is False
        assert explanation.raw_reply == "I cannot help with that."
        assert warnings

        payload = explanation.to_dict()
        assert payload["status"] == "unstructured"
        assert payload["raw_reply"] == "I cannot help with that."

    def test_a_statementless_finding_is_dropped_with_a_warning(self):
        reply = """{"findings": [{"subjects": ["a:B"], "statement": "  "}]}"""
        explanation, warnings = parse_explanation(reply)
        assert explanation.findings == []
        assert any("no statement" in w for w in warnings)

    def test_code_fences_are_tolerated(self):
        reply = '```json\n{"summary": "s", "findings": []}\n```'
        explanation, _ = parse_explanation(reply)
        assert explanation.summary == "s"


class TestSchemaVersion:
    def test_explain_versions_independently_of_advice(self):
        # İkisi ayrı sabit; ortak sayı kullanılsaydı öneri şemasındaki her
        # değişiklik ilgisiz yorum raporlarını da eskitirdi.
        assert EXPLAIN_SCHEMA_VERSION == 1
        assert ADVICE_SCHEMA_VERSION == 2

    def test_the_payload_carries_it(self):
        explanation, _ = parse_explanation('{"summary": "s", "findings": []}')
        assert explanation.to_dict()["schema_version"] == EXPLAIN_SCHEMA_VERSION
