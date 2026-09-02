"""Yanıt önbelleği testleri."""

import json

import pytest

from rlens.config import CacheConfig
from rlens.llm.cache import ResponseCache, prompt_hash


@pytest.fixture
def cache(tmp_path):
    return ResponseCache(CacheConfig(enabled=True, directory=str(tmp_path / "cache")))


class TestPromptHash:
    def test_is_deterministic(self):
        assert prompt_hash("groq", "m", "p") == prompt_hash("groq", "m", "p")

    def test_provider_changes_the_key(self):
        assert prompt_hash("groq", "m", "p") != prompt_hash("ollama", "m", "p")

    def test_model_changes_the_key(self):
        assert prompt_hash("groq", "a", "p") != prompt_hash("groq", "b", "p")

    def test_prompt_changes_the_key(self):
        """A/B koşulları farklı prompt kullanır; karışmamalı."""
        assert prompt_hash("groq", "m", "with rules") != prompt_hash("groq", "m", "without")

    def test_missing_model_is_allowed(self):
        assert len(prompt_hash("ollama", None, "p")) == 64


class TestRoundTrip:
    def test_miss_then_hit(self, cache):
        key = prompt_hash("groq", "m", "prompt")
        assert cache.get(key) is None
        cache.set(key, "the reply")
        assert cache.get(key) == "the reply"

    def test_counters(self, cache):
        key = prompt_hash("groq", "m", "prompt")
        cache.get(key)
        cache.set(key, "x")
        cache.get(key)
        assert (cache.hits, cache.misses, cache.writes) == (1, 1, 1)

    def test_unicode_survives(self, cache):
        key = prompt_hash("groq", "m", "p")
        cache.set(key, "ölçüm — tamam")
        assert cache.get(key) == "ölçüm — tamam"

    def test_stored_entry_records_metadata(self, cache):
        key = prompt_hash("groq", "m", "p")
        cache.set(key, "x", meta={"target": "god:OrderManager"})
        stored = json.loads(next(cache.directory.rglob("*.json")).read_text(encoding="utf-8"))
        assert stored["meta"]["target"] == "god:OrderManager"
        assert stored["cached_at"].endswith("+00:00")

    def test_entries_are_sharded_by_prefix(self, cache):
        """Tek dizinde binlerce dosya birikmesin."""
        key = prompt_hash("groq", "m", "p")
        cache.set(key, "x")
        assert (cache.directory / key[:2] / f"{key}.json").is_file()


class TestDisabled:
    @pytest.fixture
    def disabled(self, tmp_path):
        return ResponseCache(CacheConfig(enabled=False, directory=str(tmp_path / "c")))

    def test_get_returns_none(self, disabled):
        key = prompt_hash("groq", "m", "p")
        disabled.set(key, "x")
        assert disabled.get(key) is None

    def test_nothing_is_written(self, disabled, tmp_path):
        disabled.set(prompt_hash("groq", "m", "p"), "x")
        assert not (tmp_path / "c").exists()

    def test_describe_says_so(self, disabled):
        assert "disabled" in disabled.describe()


class TestResilience:
    def test_corrupt_entry_is_a_miss_not_a_crash(self, cache):
        """Bozuk önbellek kaydı hata değildir; yanıt yeniden üretilebilir."""
        key = prompt_hash("groq", "m", "p")
        path = cache.directory / key[:2] / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        assert cache.get(key) is None
        assert cache.misses == 1

    def test_entry_without_reply_is_a_miss(self, cache):
        key = prompt_hash("groq", "m", "p")
        path = cache.directory / key[:2] / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"key": "x"}', encoding="utf-8")
        assert cache.get(key) is None

    def test_missing_directory_is_a_miss(self, cache):
        assert cache.get(prompt_hash("groq", "m", "nothing")) is None
