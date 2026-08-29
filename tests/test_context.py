"""Prompt bağlamı ve bütçe testleri."""

from pathlib import Path

import pytest

from rlens.advise.context import (
    TRUNCATION_MARKER,
    build_context,
    build_signature,
    estimate_tokens,
    find_dependencies,
)
from rlens.advise.selector import select_targets
from rlens.analysis.scanner import scan_project_with_sources
from rlens.config import load_config

MESSY_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "messy_project"


@pytest.fixture(scope="module")
def messy():
    config = load_config(search_from=MESSY_PROJECT)
    return scan_project_with_sources(MESSY_PROJECT, config), config


@pytest.fixture
def god_target(messy):
    result, config = messy
    return next(t for t in select_targets(result.report, config, 5) if t.name == "OrderManager")


class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens("") == 0

    def test_scales_with_length(self):
        assert estimate_tokens("x" * 400) > estimate_tokens("x" * 40)


class TestBuildContext:
    def test_target_source_is_included_whole(self, messy, god_target):
        result, _ = messy
        context = build_context(god_target, result.modules, result.project_classes, 100_000)
        assert "class OrderManager:" in context.source
        assert "def place_order" in context.source
        assert "def reset_outbox" in context.source

    def test_nothing_is_truncated_with_a_large_budget(self, messy, god_target):
        result, _ = messy
        context = build_context(god_target, result.modules, result.project_classes, 100_000)
        assert context.truncated is False
        assert TRUNCATION_MARKER not in context.as_text()

    def test_dependency_signatures_are_added(self, messy, god_target):
        """Coupling önerisi karşı tarafı görmeden anlamsızdır."""
        result, _ = messy
        context = build_context(god_target, result.modules, result.project_classes, 100_000)
        joined = "\n".join(context.dependency_signatures)
        assert "class Customer:" in joined
        assert "class ShippingCalculator:" in joined

    def test_signatures_have_no_bodies(self, messy, god_target):
        result, _ = messy
        context = build_context(god_target, result.modules, result.project_classes, 100_000)
        joined = "\n".join(context.dependency_signatures)
        assert "self.customer_id = customer_id" not in joined
        assert "..." in joined

    def test_function_target_has_no_dependencies(self, messy):
        result, config = messy
        target = next(t for t in select_targets(result.report, config, 10) if t.kind == "function")
        context = build_context(target, result.modules, result.project_classes, 100_000)
        assert context.dependency_signatures == []

    def test_missing_target_raises(self, messy, god_target):
        result, _ = messy
        ghost = type(god_target)(kind="class", module="god", name="Ghost", lineno=1)
        with pytest.raises(LookupError):
            build_context(ghost, result.modules, result.project_classes, 100_000)

    def test_missing_module_raises(self, messy, god_target):
        result, _ = messy
        ghost = type(god_target)(kind="class", module="nope", name="OrderManager", lineno=1)
        with pytest.raises(LookupError):
            build_context(ghost, result.modules, result.project_classes, 100_000)


class TestBudget:
    def test_signatures_are_dropped_first(self, messy, god_target):
        """İmzalar yardımcı bilgidir; hedefin gövdesinden önce feda edilir."""
        result, _ = messy
        full = build_context(god_target, result.modules, result.project_classes, 100_000)
        tight = build_context(god_target, result.modules, result.project_classes, 900)
        assert len(tight.dependency_signatures) < len(full.dependency_signatures)

    def test_method_bodies_are_truncated_when_still_over(self, messy, god_target):
        result, _ = messy
        context = build_context(god_target, result.modules, result.project_classes, 300)
        assert TRUNCATION_MARKER in context.source

    def test_class_skeleton_survives_truncation(self, messy, god_target):
        """Model neyin var olduğunu görmeli; sadece nasıl yazıldığını görmemeli."""
        result, _ = messy
        context = build_context(god_target, result.modules, result.project_classes, 300)
        assert "class OrderManager:" in context.source
        assert "def place_order" in context.source

    def test_truncation_is_recorded_not_hidden(self, messy, god_target):
        result, _ = messy
        context = build_context(god_target, result.modules, result.project_classes, 300)
        assert context.truncated is True
        assert context.truncation_notes

    def test_truncation_actually_shrinks_the_prompt(self, messy, god_target):
        result, _ = messy
        full = build_context(god_target, result.modules, result.project_classes, 100_000)
        tight = build_context(god_target, result.modules, result.project_classes, 300)
        assert tight.estimated_tokens < full.estimated_tokens


class TestSignatures:
    def test_includes_methods_and_attributes(self, messy):
        import ast

        result, _ = messy
        module = next(m for m in result.modules if m.module == "models")
        node = next(
            n for n in module.tree.body if isinstance(n, ast.ClassDef) and n.name == "Customer"
        )
        signature = build_signature(node)
        assert "class Customer:" in signature
        assert "attributes:" in signature
        assert "def rename" in signature
        assert "self.name = name" not in signature


class TestDependencies:
    def test_ordering_is_stable(self, messy):
        import ast

        result, _ = messy
        module = next(m for m in result.modules if m.module == "god")
        node = next(n for n in module.tree.body if isinstance(n, ast.ClassDef))
        first = find_dependencies(node, result.modules, result.project_classes, node.name)
        second = find_dependencies(node, result.modules, result.project_classes, node.name)
        assert [n.name for _, n in first] == [n.name for _, n in second]

    def test_self_is_excluded(self, messy):
        import ast

        result, _ = messy
        module = next(m for m in result.modules if m.module == "god")
        node = next(n for n in module.tree.body if isinstance(n, ast.ClassDef))
        found = find_dependencies(node, result.modules, result.project_classes, node.name)
        assert "OrderManager" not in {n.name for _, n in found}
