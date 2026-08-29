"""Yanıt ayrıştırma ve şema doğrulama testleri.

Sağlayıcılar sahtedir: ağ çağrısı yapılmaz, dolayısıyla testler hızlı ve
deterministiktir. Gerçek sağlayıcıların HTTP davranışı `test_providers.py`de.
"""

import json
from pathlib import Path

import pytest

from rlens.advise.advisor import (
    UNLINKED,
    UNSTRUCTURED,
    AdviceParseError,
    ExpectedEffect,
    extract_json_object,
    parse_advice,
    request_advice,
    strip_code_fences,
)
from rlens.advise.context import build_context
from rlens.advise.selector import select_targets
from rlens.analysis.scanner import scan_project_with_sources
from rlens.config import load_config

MESSY_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "messy_project"


VALID_REPLY = {
    "target": "god:OrderManager",
    "diagnosis": "Four disjoint responsibilities.",
    "suggestions": [
        {
            "title": "Split out the audit log",
            "rationale_metric_link": ["LCOM4"],
            "expected_effect": [
                {"metric": "LCOM4", "direction": "down"},
                {"metric": "DCC", "direction": "same"},
            ],
            "sketch": "Move _log and its methods into an AuditLog class.",
        }
    ],
    "risk_notes": "Callers must be updated.",
}


class FakeProvider:
    """Sırayla verilen cevapları döndüren sahte sağlayıcı."""

    name = "fake"

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def generate(self, system, user, config, temperature=0.2):
        self.calls.append((system, user))
        return self.replies.pop(0) if self.replies else ""


@pytest.fixture(scope="module")
def context_and_config():
    config = load_config(search_from=MESSY_PROJECT)
    result = scan_project_with_sources(MESSY_PROJECT, config)
    target = next(t for t in select_targets(result.report, config, 5) if t.name == "OrderManager")
    return build_context(target, result.modules, result.project_classes, 100_000), config


class TestJsonExtraction:
    def test_plain_json(self):
        assert extract_json_object('{"a": 1}') == '{"a": 1}'

    def test_markdown_fences_are_stripped(self):
        assert "```" not in strip_code_fences('```json\n{"a": 1}\n```')

    def test_surrounding_prose_is_ignored(self):
        text = 'Here is my answer:\n{"a": 1}\nHope that helps!'
        assert extract_json_object(text) == '{"a": 1}'

    def test_nested_objects_are_balanced(self):
        text = '{"a": {"b": {"c": 1}}}'
        assert extract_json_object(text) == text

    def test_braces_inside_strings_do_not_confuse_the_parser(self):
        text = '{"a": "a } brace"}'
        assert extract_json_object(text) == text

    def test_escaped_quotes_are_handled(self):
        text = '{"a": "say \\" hi"}'
        assert extract_json_object(text) == text

    def test_no_json_raises(self):
        with pytest.raises(AdviceParseError, match="No JSON object"):
            extract_json_object("sorry, I cannot help")

    def test_unbalanced_braces_raise(self):
        with pytest.raises(AdviceParseError, match="Unbalanced"):
            extract_json_object('{"a": 1')


class TestParseAdvice:
    def test_valid_reply(self):
        advice, warnings = parse_advice(json.dumps(VALID_REPLY), "god:OrderManager")
        assert advice.diagnosis.startswith("Four disjoint")
        assert len(advice.suggestions) == 1
        assert warnings == []

    def test_expected_effect_is_structured(self):
        advice, _ = parse_advice(json.dumps(VALID_REPLY), "god:OrderManager")
        effects = advice.suggestions[0].expected_effect
        assert effects[0] == ExpectedEffect(metric="LCOM4", direction="down")
        assert effects[1].direction == "same"

    def test_unknown_metric_in_effect_is_dropped_and_reported(self):
        payload = json.loads(json.dumps(VALID_REPLY))
        payload["suggestions"][0]["expected_effect"] = [{"metric": "ELEGANCE", "direction": "up"}]
        advice, warnings = parse_advice(json.dumps(payload), "t")
        assert advice.suggestions[0].expected_effect == []
        assert any("unknown metric" in w for w in warnings)

    def test_invalid_direction_is_dropped_and_reported(self):
        payload = json.loads(json.dumps(VALID_REPLY))
        payload["suggestions"][0]["expected_effect"] = [
            {"metric": "LCOM4", "direction": "much lower"}
        ]
        advice, warnings = parse_advice(json.dumps(payload), "t")
        assert advice.suggestions[0].expected_effect == []
        assert any("invalid direction" in w for w in warnings)

    def test_metric_names_are_normalised(self):
        payload = json.loads(json.dumps(VALID_REPLY))
        payload["suggestions"][0]["expected_effect"] = [{"metric": "lcom4", "direction": "DOWN"}]
        advice, _ = parse_advice(json.dumps(payload), "t")
        assert advice.suggestions[0].expected_effect[0] == ExpectedEffect("LCOM4", "down")

    def test_unlinked_suggestion_is_tagged_not_dropped(self):
        """Projenin tezine uymayan çıktı gizlenmez, işaretlenir."""
        payload = json.loads(json.dumps(VALID_REPLY))
        payload["suggestions"][0]["rationale_metric_link"] = []
        advice, _ = parse_advice(json.dumps(payload), "t")
        assert advice.suggestions[0].tags == [UNLINKED]
        assert advice.suggestions[0].is_linked is False

    def test_unknown_metric_in_link_is_dropped(self):
        payload = json.loads(json.dumps(VALID_REPLY))
        payload["suggestions"][0]["rationale_metric_link"] = ["LCOM4", "VIBES"]
        advice, _ = parse_advice(json.dumps(payload), "t")
        assert advice.suggestions[0].rationale_metric_link == ["LCOM4"]

    def test_missing_title_gets_a_placeholder(self):
        payload = {"suggestions": [{"rationale_metric_link": ["LCOM4"]}]}
        advice, _ = parse_advice(json.dumps(payload), "t")
        assert advice.suggestions[0].title == "(untitled)"

    def test_missing_suggestions_list_raises(self):
        with pytest.raises(AdviceParseError, match="suggestions"):
            parse_advice('{"diagnosis": "x"}', "t")

    def test_json_array_is_rejected(self):
        """Dizide hiç `{` yoktur; hata nesne arama aşamasında verilir."""
        with pytest.raises(AdviceParseError, match="No JSON object"):
            parse_advice("[1, 2, 3]", "t")

    def test_non_object_top_level_raises(self):
        """`{` içeren ama nesne olmayan bir gövde şema aşamasında yakalanır."""
        with pytest.raises(AdviceParseError):
            parse_advice('[{"a": 1}]', "t")

    def test_target_falls_back_to_the_requested_one(self):
        advice, _ = parse_advice('{"suggestions": []}', "god:OrderManager")
        assert advice.target == "god:OrderManager"

    def test_serialisation_round_trip(self):
        advice, _ = parse_advice(json.dumps(VALID_REPLY), "t")
        payload = advice.to_dict()
        assert payload["suggestions"][0]["expected_effect"][0]["metric"] == "LCOM4"
        assert json.dumps(payload)


class TestRequestAdvice:
    def test_happy_path_calls_the_provider_once(self, context_and_config):
        context, config = context_and_config
        provider = FakeProvider(json.dumps(VALID_REPLY))
        advice, warnings = request_advice(provider, context, config)
        assert len(provider.calls) == 1
        assert advice.repaired is False
        assert warnings == []

    def test_broken_json_triggers_one_repair_attempt(self, context_and_config):
        context, config = context_and_config
        provider = FakeProvider("here you go: {oops", json.dumps(VALID_REPLY))
        advice, warnings = request_advice(provider, context, config)
        assert len(provider.calls) == 2
        assert advice.repaired is True
        assert advice.is_structured
        assert any("needed repair" in w for w in warnings)

    def test_repair_prompt_carries_the_original_reply(self, context_and_config):
        context, config = context_and_config
        provider = FakeProvider("broken {", json.dumps(VALID_REPLY))
        request_advice(provider, context, config)
        assert "broken {" in provider.calls[1][1]

    def test_failed_repair_keeps_the_raw_reply(self, context_and_config):
        """Ham metin atılmaz; sessizce boş dönmek kullanıcıyı yanıltır."""
        context, config = context_and_config
        provider = FakeProvider("garbage", "still garbage")
        advice, warnings = request_advice(provider, context, config)
        assert advice.tags == [UNSTRUCTURED]
        assert advice.is_structured is False
        assert advice.raw_reply == "garbage"
        assert warnings

    def test_never_retries_more_than_once(self, context_and_config):
        context, config = context_and_config
        provider = FakeProvider("bad", "bad", json.dumps(VALID_REPLY))
        request_advice(provider, context, config)
        assert len(provider.calls) == 2

    def test_truncation_notes_are_carried_into_the_advice(self):
        config = load_config(search_from=MESSY_PROJECT)
        result = scan_project_with_sources(MESSY_PROJECT, config)
        target = next(
            t for t in select_targets(result.report, config, 5) if t.name == "OrderManager"
        )
        context = build_context(target, result.modules, result.project_classes, 300)
        provider = FakeProvider(json.dumps(VALID_REPLY))
        advice, _ = request_advice(provider, context, config)
        assert advice.truncation_notes
