"""Bütçe sayacı testleri."""

import pytest

from rlens.config import BudgetConfig
from rlens.llm.budget import Budget, BudgetExceeded


@pytest.fixture
def budget():
    return Budget(BudgetConfig(max_calls_per_run=3, max_tokens_per_call=1000))


class TestCounting:
    def test_starts_empty(self, budget):
        assert budget.calls == 0
        assert budget.remaining_calls == 3
        assert budget.exhausted is False

    def test_record_call_decrements_remaining(self, budget):
        budget.record_call()
        assert budget.remaining_calls == 2

    def test_tokens_accumulate(self, budget):
        budget.record_call(100, 50)
        budget.record_call(200, 80)
        assert budget.tokens_in == 300
        assert budget.tokens_out == 130

    def test_negative_tokens_are_ignored(self, budget):
        """Sağlayıcı saçma bir sayı dönerse sayaç bozulmamalı."""
        budget.record_call(-5, -5)
        assert budget.tokens_in == 0


class TestLimit:
    def test_check_passes_while_budget_remains(self, budget):
        budget.check()
        budget.record_call()
        budget.check()

    def test_check_raises_when_exhausted(self, budget):
        for _ in range(3):
            budget.record_call()
        with pytest.raises(BudgetExceeded):
            budget.check()

    def test_message_says_how_to_proceed(self, budget):
        for _ in range(3):
            budget.record_call()
        with pytest.raises(BudgetExceeded, match="max_calls_per_run"):
            budget.check()

    def test_skipped_targets_are_recorded(self, budget):
        """Atlanan hedef sessizce kaybolmaz; rapora yazılır."""
        for _ in range(3):
            budget.record_call()
        with pytest.raises(BudgetExceeded):
            budget.check("god:OrderManager")
        assert budget.skipped == ["god:OrderManager"]


class TestCacheHits:
    def test_cache_hit_is_not_a_call(self, budget):
        """Önbellekten dönen yanıt para harcamaz, bütçeden düşmez."""
        budget.record_cache_hit()
        assert budget.calls == 0
        assert budget.remaining_calls == 3
        assert budget.cache_hits == 1


class TestTokenCeiling:
    def test_small_prompt_fits(self, budget):
        assert budget.fits(500) is True

    def test_oversized_prompt_does_not(self, budget):
        assert budget.fits(5000) is False

    def test_exact_limit_fits(self, budget):
        assert budget.fits(1000) is True


class TestSummary:
    def test_summary_fields(self, budget):
        budget.record_call(10, 20)
        summary = budget.summary()
        assert summary["calls"] == 1
        assert summary["max_calls"] == 3
        assert summary["exhausted"] is False

    def test_describe_is_one_line(self, budget):
        budget.record_call(10, 20)
        budget.record_cache_hit()
        described = budget.describe()
        assert "1/3 calls" in described
        assert "1 from cache" in described
        assert "\n" not in described
