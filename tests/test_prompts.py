"""Prompt üretimi testleri.

En önemli grup `TestNoRawThresholds`: modelin eşik sayısını görmemesi projenin
Goodhart azaltmasının temelidir ve sessizce bozulabilecek bir özelliktir.
"""

import json
from pathlib import Path

import pytest

from rlens.advise.context import build_context
from rlens.advise.prompts import (
    SYSTEM_INSTRUCTION,
    VALID_DIRECTIONS,
    VALID_METRICS,
    build_repair_prompt,
    build_user_prompt,
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
