"""Prompt üretimi testleri.

En önemli grup `TestNoRawThresholds`: modelin eşik sayısını görmemesi projenin
Goodhart azaltmasının temelidir ve sessizce bozulabilecek bir özelliktir.
"""

import json
from pathlib import Path

import pytest

from rlens.advise.context import build_context
from rlens.advise.prompts import (
    METRIC_RULES,
    SYSTEM_INSTRUCTION,
    VALID_DIRECTIONS,
    VALID_METRICS,
    build_repair_prompt,
    build_user_prompt,
    format_architecture,
    format_evidence,
    output_schema,
)
from rlens.advise.selector import select_targets
from rlens.analysis.scanner import scan_project_with_sources
from rlens.config import load_config

MESSY_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "messy_project"


@pytest.fixture(scope="module")
def god_context():
    config = load_config(search_from=MESSY_PROJECT)
    result = scan_project_with_sources(MESSY_PROJECT, config)
    target = next(t for t in select_targets(result.report, config, 5) if t.name == "OrderManager")
    return build_context(target, result.modules, result.project_classes, 100_000), config


class TestEvidence:
    def test_measured_values_are_present(self, god_context):
        context, _ = god_context
        evidence = format_evidence(context)
        assert "LCOM4 = 4" in evidence
        assert "DCC = 8" in evidence

    def test_violation_flags_are_marked(self, god_context):
        context, _ = god_context
        assert "[CRITICAL]" in format_evidence(context)

    def test_uncomputed_metrics_are_not_shown_as_zero(self, god_context):
        context, _ = god_context
        assert "CAM = not computed" in format_evidence(context)

    def test_glossary_explains_each_metric(self, god_context):
        context, _ = god_context
        assert "connected components" in format_evidence(context)


class TestNoRawThresholds:
    """Model neyin sorunlu olduğunu bilmeli, eşiğin kaç olduğunu bilmemeli."""

    def test_threshold_numbers_are_absent(self, god_context):
        context, config = god_context
        prompt = build_user_prompt(context)
        evidence = prompt.split("Code:")[0]
        for key, threshold in config.thresholds.items():
            assert f"{key}: {threshold.warn}" not in evidence

    def test_prompt_says_thresholds_are_hidden_on_purpose(self, god_context):
        context, _ = god_context
        assert "deliberately not shown" in build_user_prompt(context)


class TestUserPrompt:
    def test_contains_the_code(self, god_context):
        context, _ = god_context
        assert "class OrderManager:" in build_user_prompt(context)

    def test_lists_allowed_metric_names(self, god_context):
        context, _ = god_context
        prompt = build_user_prompt(context)
        for metric in ("LCOM4", "DCC", "WMC"):
            assert metric in prompt

    def test_lists_allowed_directions(self, god_context):
        context, _ = god_context
        prompt = build_user_prompt(context)
        for direction in VALID_DIRECTIONS:
            assert direction in prompt

    def test_embeds_the_output_schema(self, god_context):
        context, _ = god_context
        assert "expected_effect" in build_user_prompt(context)

    def test_truncation_is_announced(self):
        """Modele eksik kod verildiği gizlenmez."""
        config = load_config(search_from=MESSY_PROJECT)
        result = scan_project_with_sources(MESSY_PROJECT, config)
        target = next(
            t for t in select_targets(result.report, config, 5) if t.name == "OrderManager"
        )
        context = build_context(target, result.modules, result.project_classes, 300)
        prompt = build_user_prompt(context)
        assert "incomplete" in prompt
        assert "do not guess" in prompt


class TestSystemInstruction:
    def test_requires_metric_grounding(self):
        assert "must name at least one metric" in SYSTEM_INSTRUCTION

    def test_requires_a_prediction(self):
        assert "predict its measurable effect" in SYSTEM_INSTRUCTION

    def test_warns_about_trade_offs(self):
        assert "lowers LCOM4 while raising DCC" in SYSTEM_INSTRUCTION

    def test_forbids_inventing_omitted_code(self):
        assert "Do not invent code" in SYSTEM_INSTRUCTION


class TestSchema:
    def test_schema_is_json_serialisable(self):
        assert "expected_effect" in json.dumps(output_schema())

    def test_schema_example_uses_valid_names(self):
        schema = output_schema()
        for effect in schema["suggestions"][0]["expected_effect"]:
            assert effect["metric"] in VALID_METRICS
            assert effect["direction"] in VALID_DIRECTIONS


class TestRepairPrompt:
    def test_includes_the_error_and_original_reply(self):
        prompt = build_repair_prompt("not json at all", "Invalid JSON: boom")
        assert "boom" in prompt
        assert "not json at all" in prompt

    def test_forbids_new_suggestions(self):
        """Onarım yeniden üretim değildir; ikinci cevap birinciden farklı olmamalı."""
        assert "Do not add new suggestions" in build_repair_prompt("x", "y")


LAYERED = Path(__file__).resolve().parent.parent / "examples" / "layered_project"


@pytest.fixture(scope="module")
def layered_context():
    from rlens.advise.context import build_context
    from rlens.advise.selector import select_targets
    from rlens.analysis.scanner import scan_project_with_sources

    config = load_config(search_from=LAYERED)
    result = scan_project_with_sources(LAYERED, config)
    target = next(t for t in select_targets(result.report, config, 5) if t.name == "OrderService")
    context = build_context(
        target, result.modules, result.project_classes, config.advise.max_context_tokens
    )
    return context, config


class TestArchitecturalContext:
    def test_layer_and_source_are_stated(self, layered_context):
        context, config = layered_context
        block = format_architecture(context.target, config.arch.scheme)
        assert "Target layer: application (declared, confidence 1.00)" in block

    def test_permission_matrix_is_spelled_out(self, layered_context):
        context, config = layered_context
        block = format_architecture(context.target, config.arch.scheme)
        assert "application may import: domain" in block
        assert "must NOT import" in block
        assert "infrastructure" in block

    def test_smell_labels_carry_their_evidence(self, layered_context):
        context, config = layered_context
        block = format_architecture(context.target, config.arch.scheme)
        assert "god_class" in block
        assert "nom=26" in block

    def test_the_data_class_note_travels_with_the_label(self):
        """Modele LCOM4'ün orada beklenen olduğu söylenmeli."""
        from rlens.advise.selector import AdviceTarget

        target = AdviceTarget(
            kind="class",
            module="m",
            name="C",
            lineno=1,
            layer="domain",
            layer_source="declared",
            layer_confidence=1.0,
            smells=[
                {
                    "label": "data_class",
                    "evidence": {"lcom4": 4},
                    "note": "a data holder; a high LCOM4 here is expected",
                }
            ],
        )
        config = load_config(search_from=LAYERED)
        block = format_architecture(target, config.arch.scheme)
        assert "expected" in block

    def test_no_block_without_a_layer(self):
        """`layer: unknown` satırı bilgi vermez, A/B'yi bulanıklaştırır."""
        from rlens.advise.selector import AdviceTarget

        config = load_config(search_from=LAYERED)
        target = AdviceTarget(kind="class", module="m", name="C", lineno=1)
        assert format_architecture(target, config.arch.scheme) == ""

    def test_violations_are_listed_with_their_alias(self):
        from rlens.advise.selector import AdviceTarget

        config = load_config(search_from=LAYERED)
        target = AdviceTarget(
            kind="class",
            module="m",
            name="C",
            lineno=1,
            layer="domain",
            layer_confidence=1.0,
            violations=[
                {
                    "code": "LV-DIR",
                    "alias": "back-call",
                    "source": "m",
                    "target": "infra.db",
                    "tentative": False,
                }
            ],
        )
        block = format_architecture(target, config.arch.scheme)
        assert "LV-DIR (back-call)" in block


def _flat(text: str) -> str:
    """Satır sonlarını boşluğa çevirir: kural metni sarmalı olabilir."""
    return " ".join(text.split())


class TestMetricRules:
    """FINDINGS-1'de yanılan dört metriğin dördü de doğrudan hedeflenir."""

    def test_scope_is_stated_up_front(self):
        assert "on this entity alone" in METRIC_RULES

    def test_nom_wrapper_rule(self):
        assert "delegates to another object still counts" in _flat(METRIC_RULES)

    def test_lcom4_wrapper_rule(self):
        assert "wrapper still touches whatever attribute" in _flat(METRIC_RULES)

    def test_dcc_scope_rule(self):
        assert "the project gaining a class does not raise it" in _flat(METRIC_RULES)

    def test_loc_scope_rule(self):
        assert "Lines moved to a helper leave this function" in _flat(METRIC_RULES)

    def test_no_threshold_numbers(self):
        """Değişmez: hesaplama kuralı verilir, eşik verilmez."""
        config = load_config(search_from=LAYERED)
        for key, threshold in config.thresholds.items():
            assert f"{key}: {threshold.warn}" not in METRIC_RULES


class TestPromptComposition:
    def test_architecture_block_is_optional(self, layered_context):
        context, config = layered_context
        with_arch = build_user_prompt(context, scheme=config.arch.scheme)
        without = build_user_prompt(context)
        assert "Architectural context" in with_arch
        assert "Architectural context" not in without

    def test_metric_rules_are_optional(self, layered_context):
        context, _ = layered_context
        assert "How these metrics are computed" in build_user_prompt(context, metric_rules=True)
        assert "How these metrics are computed" not in build_user_prompt(context)

    def test_schema_gains_layer_fields_only_with_context(self, layered_context):
        context, config = layered_context
        with_arch = build_user_prompt(context, scheme=config.arch.scheme)
        without = build_user_prompt(context)
        assert "target_layer_after" in with_arch
        assert "target_layer_after" not in without

    def test_confidence_is_in_the_schema(self, layered_context):
        context, _ = layered_context
        assert "confidence" in build_user_prompt(context)

    def test_system_instruction_mentions_layer_rules(self):
        assert "respect the layer rules" in SYSTEM_INSTRUCTION
