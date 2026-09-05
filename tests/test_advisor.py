"""Yanıt ayrıştırma ve şema doğrulama testleri.

Sağlayıcılar sahtedir: ağ çağrısı yapılmaz, dolayısıyla testler hızlı ve
deterministiktir. Gerçek sağlayıcıların HTTP davranışı `test_providers.py`de.
"""

import json
from pathlib import Path

import pytest

from rlens.advise.advisor import (
    LINKED,
    REJECTED,
    UNLINKED,
    UNSTRUCTURED,
    Advice,
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
        assert advice.suggestions[0].status == UNLINKED
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

    def test_model_echoing_the_schema_placeholder_is_overridden(self):
        """Gerçekte gözlemlendi: model `"module:Name"` yer tutucusunu kopyaladı.

        O ad hiçbir sınıfa karşılık gelmez ve `verify --advice` eşleştirmesini
        sessizce kırardı.
        """
        advice, warnings = parse_advice(
            '{"target": "module:Name", "suggestions": []}', "god:OrderManager"
        )
        assert advice.target == "god:OrderManager"
        assert any("module:Name" in w for w in warnings)

    def test_matching_target_produces_no_warning(self):
        _, warnings = parse_advice(
            '{"target": "god:OrderManager", "suggestions": []}', "god:OrderManager"
        )
        assert warnings == []

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


class CountingProvider(FakeProvider):
    """Kaç kez gerçekten çağrıldığını sayar."""

    name = "groq"

    def __init__(self, *replies):
        super().__init__(*replies)
        self.generated = 0

    def generate(self, system, user, config, temperature=0.2):
        self.generated += 1
        return super().generate(system, user, config, temperature)


@pytest.fixture
def cache(tmp_path):
    from rlens.config import CacheConfig
    from rlens.llm.cache import ResponseCache

    return ResponseCache(CacheConfig(enabled=True, directory=str(tmp_path / "cache")))


@pytest.fixture
def budget(context_and_config):
    from rlens.llm.budget import Budget

    _, config = context_and_config
    return Budget(config.budget)


class TestCacheIntegration:
    """Aşama 0 kabul kriteri: aynı prompt ikinci koşuda önbellekten döner."""

    def test_second_run_does_not_call_the_provider(self, context_and_config, cache, budget):
        context, config = context_and_config
        provider = CountingProvider(json.dumps(VALID_REPLY), json.dumps(VALID_REPLY))
        request_advice(provider, context, config, cache=cache, budget=budget)
        request_advice(provider, context, config, cache=cache, budget=budget)
        assert provider.generated == 1

    def test_cached_reply_is_marked(self, context_and_config, cache, budget):
        context, config = context_and_config
        provider = CountingProvider(json.dumps(VALID_REPLY))
        first, _ = request_advice(provider, context, config, cache=cache, budget=budget)
        second, _ = request_advice(provider, context, config, cache=cache, budget=budget)
        assert first.from_cache is False
        assert second.from_cache is True

    def test_cache_hit_does_not_consume_budget(self, context_and_config, cache, budget):
        """Önbellekten dönen yanıt para harcamaz."""
        context, config = context_and_config
        provider = CountingProvider(json.dumps(VALID_REPLY))
        request_advice(provider, context, config, cache=cache, budget=budget)
        calls_after_first = budget.calls
        request_advice(provider, context, config, cache=cache, budget=budget)
        assert budget.calls == calls_after_first
        assert budget.cache_hits == 1

    def test_prompt_hash_is_recorded(self, context_and_config, cache, budget):
        """İki koşunun aynı prompt'la yapıldığını kanıtlamanın tek yolu."""
        context, config = context_and_config
        provider = CountingProvider(json.dumps(VALID_REPLY))
        advice, _ = request_advice(provider, context, config, cache=cache, budget=budget)
        assert len(advice.prompt_hash) == 64

    def test_works_without_a_cache(self, context_and_config):
        context, config = context_and_config
        provider = CountingProvider(json.dumps(VALID_REPLY), json.dumps(VALID_REPLY))
        request_advice(provider, context, config)
        request_advice(provider, context, config)
        assert provider.generated == 2


class TestBudgetIntegration:
    def test_a_call_is_counted(self, context_and_config, budget):
        context, config = context_and_config
        request_advice(FakeProvider(json.dumps(VALID_REPLY)), context, config, budget=budget)
        assert budget.calls == 1

    def test_repair_counts_as_a_second_call(self, context_and_config, budget):
        context, config = context_and_config
        provider = FakeProvider("broken {", json.dumps(VALID_REPLY))
        request_advice(provider, context, config, budget=budget)
        assert budget.calls == 2

    def test_exhausted_budget_stops_the_call(self, context_and_config):
        from rlens.config import BudgetConfig
        from rlens.llm.budget import Budget, BudgetExceeded

        context, config = context_and_config
        spent = Budget(BudgetConfig(max_calls_per_run=1, max_tokens_per_call=100_000))
        spent.record_call()
        with pytest.raises(BudgetExceeded):
            request_advice(FakeProvider(json.dumps(VALID_REPLY)), context, config, budget=spent)

    def test_target_name_is_recorded_when_skipped(self, context_and_config):
        from rlens.config import BudgetConfig
        from rlens.llm.budget import Budget, BudgetExceeded

        context, config = context_and_config
        spent = Budget(BudgetConfig(max_calls_per_run=1, max_tokens_per_call=100_000))
        spent.record_call()
        with pytest.raises(BudgetExceeded):
            request_advice(FakeProvider(json.dumps(VALID_REPLY)), context, config, budget=spent)
        assert spent.skipped == [context.target.qualified_name]

    def test_budget_exhausted_during_repair_keeps_the_raw_reply(self, context_and_config):
        """Onarım bütçeye takılsa bile ham metin atılmaz."""
        from rlens.config import BudgetConfig
        from rlens.llm.budget import Budget

        context, config = context_and_config
        tight = Budget(BudgetConfig(max_calls_per_run=1, max_tokens_per_call=100_000))
        provider = FakeProvider("not json at all", json.dumps(VALID_REPLY))
        advice, _ = request_advice(provider, context, config, budget=tight)
        assert advice.tags == [UNSTRUCTURED]
        assert advice.raw_reply == "not json at all"


class TestConfidence:
    """Opsiyoneldir; yokluğu öneriyi düşürmez."""

    def _reply(self, effect):
        payload = json.loads(json.dumps(VALID_REPLY))
        payload["suggestions"][0]["expected_effect"] = [effect]
        return json.dumps(payload)

    def test_confidence_is_parsed(self):
        advice, _ = parse_advice(
            self._reply({"metric": "LCOM4", "direction": "down", "confidence": 0.8}), "t"
        )
        assert advice.suggestions[0].expected_effect[0].confidence == 0.8

    def test_missing_confidence_is_none_not_zero(self):
        """Sıfır 'hiç emin değilim' demek olurdu; doğrusu 'söylemedi'."""
        advice, _ = parse_advice(self._reply({"metric": "LCOM4", "direction": "down"}), "t")
        assert advice.suggestions[0].expected_effect[0].confidence is None

    def test_missing_confidence_keeps_the_prediction(self):
        advice, _ = parse_advice(self._reply({"metric": "LCOM4", "direction": "down"}), "t")
        assert len(advice.suggestions[0].expected_effect) == 1

    def test_out_of_range_confidence_is_dropped_and_reported(self):
        advice, warnings = parse_advice(
            self._reply({"metric": "LCOM4", "direction": "down", "confidence": 1.7}), "t"
        )
        assert advice.suggestions[0].expected_effect[0].confidence is None
        assert any("outside 0-1" in w for w in warnings)

    def test_non_numeric_confidence_is_dropped(self):
        advice, warnings = parse_advice(
            self._reply({"metric": "LCOM4", "direction": "down", "confidence": "high"}),
            "t",
        )
        assert advice.suggestions[0].expected_effect[0].confidence is None
        assert any("non-numeric" in w for w in warnings)

    def test_serialisation_keeps_it(self):
        advice, _ = parse_advice(
            self._reply({"metric": "LCOM4", "direction": "down", "confidence": 0.6}), "t"
        )
        assert advice.to_dict()["suggestions"][0]["expected_effect"][0]["confidence"] == 0.6


class TestConstraintValidation:
    """Modelin beyanı bir çıktıdır; araç kendi kontrolünü yapar."""

    @pytest.fixture
    def scheme(self, context_and_config):
        _, config = context_and_config
        return config.arch.scheme

    def _reply(self, **fields):
        payload = json.loads(json.dumps(VALID_REPLY))
        payload["suggestions"][0].update(fields)
        return json.dumps(payload)

    def test_valid_destination_layer_is_accepted(self, scheme):
        advice, _ = parse_advice(
            self._reply(target_layer_after="domain", constraints_respected=True),
            "t",
            scheme=scheme,
        )
        suggestion = advice.suggestions[0]
        assert suggestion.status == LINKED
        assert suggestion.constraint_agreement is True

    def test_unknown_destination_layer_is_rejected(self, scheme):
        advice, _ = parse_advice(
            self._reply(target_layer_after="persistence", constraints_respected=True),
            "t",
            scheme=scheme,
        )
        assert advice.suggestions[0].status == REJECTED

    def test_disagreement_is_recorded(self, scheme):
        """5a'nın ölçütlerinden biri: beyan ile gerçek arasındaki fark."""
        advice, _ = parse_advice(
            self._reply(target_layer_after="persistence", constraints_respected=True),
            "t",
            scheme=scheme,
        )
        suggestion = advice.suggestions[0]
        assert suggestion.constraint_agreement is False
        assert any("disagrees" in note for note in suggestion.notes)

    def test_model_admitting_a_violation_is_rejected(self, scheme):
        advice, _ = parse_advice(self._reply(constraints_respected=False), "t", scheme=scheme)
        assert advice.suggestions[0].status == REJECTED

    def test_admitting_is_not_a_disagreement(self, scheme):
        advice, _ = parse_advice(self._reply(constraints_respected=False), "t", scheme=scheme)
        assert advice.suggestions[0].constraint_agreement is True

    def test_rejected_suggestions_are_kept(self, scheme):
        """Hiçbir öneri silinmez; oranlar raporlanır."""
        advice, _ = parse_advice(self._reply(target_layer_after="nowhere"), "t", scheme=scheme)
        assert len(advice.suggestions) == 1

    def test_no_scheme_means_no_layer_judgment(self):
        advice, _ = parse_advice(self._reply(target_layer_after="persistence"), "t")
        assert advice.suggestions[0].status == LINKED

    def test_unknown_smell_labels_are_reported(self, context_and_config):
        context, config = context_and_config
        advice, _ = parse_advice(
            self._reply(addresses_smells=["god_class", "shotgun_surgery"]),
            "t",
            advice_target=context.target,
            scheme=config.arch.scheme,
        )
        assert any("does not carry" in note for note in advice.suggestions[0].notes)

    def test_unknown_smell_labels_do_not_reject(self, context_and_config):
        """Yanlış etiket bir hatadır ama öneriyi geçersiz kılmaz."""
        context, config = context_and_config
        advice, _ = parse_advice(
            self._reply(addresses_smells=["shotgun_surgery"]),
            "t",
            advice_target=context.target,
            scheme=config.arch.scheme,
        )
        assert advice.suggestions[0].status == LINKED


class TestDocumentCounters:
    def test_rejected_and_disagreement_counts(self):
        from rlens.advise.advisor import AdviceDocument, Suggestion

        document = AdviceDocument(
            root="/tmp",
            generated_at="2026-01-01T00:00:00+00:00",
            rlens_version="1.0.0",
            provider="fake",
            model="m",
            temperature=0.2,
            advices=[
                Advice(
                    target="m:C",
                    suggestions=[
                        Suggestion(title="a", status=REJECTED, constraint_agreement=False),
                        Suggestion(title="b", status=UNLINKED),
                        Suggestion(title="c", rationale_metric_link=["NOM"]),
                    ],
                )
            ],
        )
        assert document.rejected_count == 1
        assert document.unlinked_count == 2
        assert document.constraint_disagreements == 1
