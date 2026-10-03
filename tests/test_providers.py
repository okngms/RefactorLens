"""Sağlayıcı adapter testleri.

Gerçek ağ çağrısı yapılmaz: `httpx.post` sahte bir işlevle değiştirilir.
Gecikme de sahtedir, testler geri çekilme süresini gerçekten beklemez.
"""

import httpx
import pytest

from rlens.config import load_config
from rlens.providers import PROVIDERS, get_provider
from rlens.providers.base import (
    ProviderConfigError,
    ProviderError,
    ProviderTruncated,
    load_env_file,
    post_with_retry,
    require_api_key,
    require_model,
)
from rlens.providers.groq import GroqProvider
from rlens.providers.ollama import OllamaProvider


@pytest.fixture
def provider_config(tmp_path):
    (tmp_path / "rlens.yaml").write_text(
        "provider:\n  name: groq\n  model: test-model\n  max_retries: 2\n",
        encoding="utf-8",
    )
    return load_config(search_from=tmp_path).provider


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or str(self._payload)

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class Recorder:
    """httpx.post yerine geçen kaydedici."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        item = self.responses.pop(0) if self.responses else FakeResponse()
        if isinstance(item, Exception):
            raise item
        return item


class TestRegistry:
    def test_core_providers_are_registered(self):
        assert {"groq", "ollama"} <= set(PROVIDERS)

    def test_gemini_is_registered_as_optional(self):
        assert "gemini" in PROVIDERS

    def test_get_provider_returns_an_instance(self, provider_config):
        assert isinstance(get_provider(provider_config), GroqProvider)

    def test_unknown_provider_is_rejected_by_config(self, tmp_path):
        from rlens.config import ConfigError

        (tmp_path / "rlens.yaml").write_text("provider:\n  name: openai\n", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_config(search_from=tmp_path)


class TestRequirements:
    def test_missing_model_explains_why_it_is_not_hardcoded(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text("provider:\n  name: groq\n", encoding="utf-8")
        config = load_config(search_from=tmp_path).provider
        with pytest.raises(ProviderConfigError, match="does not hard-code"):
            require_model(config, "Groq")

    def test_missing_api_key_names_the_variable(self, monkeypatch):
        monkeypatch.delenv("TEST_KEY", raising=False)
        with pytest.raises(ProviderConfigError, match="TEST_KEY"):
            require_api_key("TEST_KEY", "Test")

    def test_present_api_key_is_returned(self, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "secret")
        assert require_api_key("TEST_KEY", "Test") == "secret"


class TestEnvFile:
    def test_values_are_loaded(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DEMO_KEY", raising=False)
        (tmp_path / ".env").write_text("DEMO_KEY=from-file\n", encoding="utf-8")
        load_env_file(tmp_path)
        import os

        assert os.environ["DEMO_KEY"] == "from-file"

    def test_existing_environment_wins(self, tmp_path, monkeypatch):
        """Kabuktan verilen değer dosyadan gelenden önceliklidir."""
        monkeypatch.setenv("DEMO_KEY", "from-shell")
        (tmp_path / ".env").write_text("DEMO_KEY=from-file\n", encoding="utf-8")
        load_env_file(tmp_path)
        import os

        assert os.environ["DEMO_KEY"] == "from-shell"

    def test_comments_and_blank_lines_are_ignored(self, tmp_path, monkeypatch):
        monkeypatch.delenv("REAL", raising=False)
        (tmp_path / ".env").write_text("# comment\n\nREAL=1\n", encoding="utf-8")
        load_env_file(tmp_path)
        import os

        assert os.environ["REAL"] == "1"

    def test_quotes_are_stripped(self, tmp_path, monkeypatch):
        monkeypatch.delenv("QUOTED", raising=False)
        (tmp_path / ".env").write_text('QUOTED="value"\n', encoding="utf-8")
        load_env_file(tmp_path)
        import os

        assert os.environ["QUOTED"] == "value"


class TestRetry:
    def test_timeout_is_always_applied(self, provider_config, monkeypatch):
        """Zaman aşımı olmayan çağrı terminali süresiz kilitleyebilir."""
        recorder = Recorder(FakeResponse(200, {"ok": True}))
        monkeypatch.setattr(httpx, "post", recorder)
        post_with_retry("http://x", {}, {}, provider_config, sleep=lambda _: None)
        assert recorder.calls[0]["timeout"] == provider_config.timeout_seconds

    def test_rate_limit_is_retried(self, provider_config, monkeypatch):
        recorder = Recorder(FakeResponse(429), FakeResponse(429), FakeResponse(200, {"ok": True}))
        monkeypatch.setattr(httpx, "post", recorder)
        result = post_with_retry("http://x", {}, {}, provider_config, sleep=lambda _: None)
        assert result == {"ok": True}
        assert len(recorder.calls) == 3

    def test_backoff_is_exponential(self, provider_config, monkeypatch):
        """Sabit aralıkla ısrar etmek oran limitini daha da kötüleştirir."""
        delays = []
        recorder = Recorder(FakeResponse(429), FakeResponse(429), FakeResponse(200, {}))
        monkeypatch.setattr(httpx, "post", recorder)
        post_with_retry("http://x", {}, {}, provider_config, sleep=delays.append)
        assert delays == [1, 2]

    def test_retries_are_bounded(self, provider_config, monkeypatch):
        recorder = Recorder(*[FakeResponse(503) for _ in range(10)])
        monkeypatch.setattr(httpx, "post", recorder)
        with pytest.raises(ProviderError):
            post_with_retry("http://x", {}, {}, provider_config, sleep=lambda _: None)
        assert len(recorder.calls) == provider_config.max_retries + 1

    def test_auth_error_is_not_retried(self, provider_config, monkeypatch):
        recorder = Recorder(FakeResponse(401))
        monkeypatch.setattr(httpx, "post", recorder)
        with pytest.raises(ProviderError, match="Authentication failed"):
            post_with_retry("http://x", {}, {}, provider_config, sleep=lambda _: None)
        assert len(recorder.calls) == 1

    def test_not_found_mentions_model_and_base_url(self, provider_config, monkeypatch):
        monkeypatch.setattr(httpx, "post", Recorder(FakeResponse(404)))
        with pytest.raises(ProviderError, match="provider.model"):
            post_with_retry("http://x", {}, {}, provider_config, sleep=lambda _: None)

    def test_timeout_exception_is_retried_then_reported(self, provider_config, monkeypatch):
        recorder = Recorder(*[httpx.TimeoutException("slow") for _ in range(5)])
        monkeypatch.setattr(httpx, "post", recorder)
        with pytest.raises(ProviderError, match="timed out"):
            post_with_retry("http://x", {}, {}, provider_config, sleep=lambda _: None)

    def test_non_json_response_is_reported(self, provider_config, monkeypatch):
        response = FakeResponse(200)
        response._payload = None
        monkeypatch.setattr(httpx, "post", Recorder(response))
        with pytest.raises(ProviderError, match="non-JSON"):
            post_with_retry("http://x", {}, {}, provider_config, sleep=lambda _: None)


class TestGroq:
    def test_sends_system_and_user_messages(self, provider_config, monkeypatch):
        recorder = Recorder(FakeResponse(200, {"choices": [{"message": {"content": "hello"}}]}))
        monkeypatch.setattr(httpx, "post", recorder)
        monkeypatch.setenv("GROQ_API_KEY", "key")
        reply = GroqProvider().generate("sys", "usr", provider_config, 0.2, sleep=lambda _: None)
        assert reply == "hello"
        messages = recorder.calls[0]["json"]["messages"]
        assert [m["role"] for m in messages] == ["system", "user"]

    def test_model_comes_from_config_not_code(self, provider_config, monkeypatch):
        recorder = Recorder(FakeResponse(200, {"choices": [{"message": {"content": "x"}}]}))
        monkeypatch.setattr(httpx, "post", recorder)
        monkeypatch.setenv("GROQ_API_KEY", "key")
        GroqProvider().generate("s", "u", provider_config, 0.2, sleep=lambda _: None)
        assert recorder.calls[0]["json"]["model"] == "test-model"

    def test_api_key_is_sent_as_bearer(self, provider_config, monkeypatch):
        recorder = Recorder(FakeResponse(200, {"choices": [{"message": {"content": "x"}}]}))
        monkeypatch.setattr(httpx, "post", recorder)
        monkeypatch.setenv("GROQ_API_KEY", "secret")
        GroqProvider().generate("s", "u", provider_config, 0.2, sleep=lambda _: None)
        assert recorder.calls[0]["headers"]["Authorization"] == "Bearer secret"

    def test_unexpected_shape_is_reported(self, provider_config, monkeypatch):
        monkeypatch.setattr(httpx, "post", Recorder(FakeResponse(200, {"weird": True})))
        monkeypatch.setenv("GROQ_API_KEY", "key")
        with pytest.raises(ProviderError, match="Unexpected response shape"):
            GroqProvider().generate("s", "u", provider_config, 0.2, sleep=lambda _: None)


class TestOllama:
    @pytest.fixture
    def ollama_config(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text(
            "provider:\n  name: ollama\n  model: llama3\n", encoding="utf-8"
        )
        return load_config(search_from=tmp_path).provider

    def test_needs_no_api_key(self, ollama_config, monkeypatch):
        """Lokal sağlayıcının varlık sebebi: kod makineden çıkmaz."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        recorder = Recorder(FakeResponse(200, {"message": {"content": "hi"}}))
        monkeypatch.setattr(httpx, "post", recorder)
        assert OllamaProvider().generate("s", "u", ollama_config, 0.2, sleep=lambda _: None) == "hi"

    def test_defaults_to_localhost(self, ollama_config, monkeypatch):
        recorder = Recorder(FakeResponse(200, {"message": {"content": "hi"}}))
        monkeypatch.setattr(httpx, "post", recorder)
        OllamaProvider().generate("s", "u", ollama_config, 0.2, sleep=lambda _: None)
        assert recorder.calls[0]["url"].startswith("http://localhost:11434")

    def test_base_url_override(self, tmp_path, monkeypatch):
        (tmp_path / "rlens.yaml").write_text(
            "provider:\n  name: ollama\n  model: llama3\n  base_url: http://gpu-box:11434\n",
            encoding="utf-8",
        )
        config = load_config(search_from=tmp_path).provider
        recorder = Recorder(FakeResponse(200, {"message": {"content": "hi"}}))
        monkeypatch.setattr(httpx, "post", recorder)
        OllamaProvider().generate("s", "u", config, 0.2, sleep=lambda _: None)
        assert recorder.calls[0]["url"].startswith("http://gpu-box:11434")

    def test_streaming_is_disabled(self, ollama_config, monkeypatch):
        recorder = Recorder(FakeResponse(200, {"message": {"content": "hi"}}))
        monkeypatch.setattr(httpx, "post", recorder)
        OllamaProvider().generate("s", "u", ollama_config, 0.2, sleep=lambda _: None)
        assert recorder.calls[0]["json"]["stream"] is False

    def test_missing_model_hint_mentions_pulling(self, ollama_config, monkeypatch):
        monkeypatch.setattr(httpx, "post", Recorder(FakeResponse(200, {"nope": 1})))
        with pytest.raises(ProviderError, match="pulled"):
            OllamaProvider().generate("s", "u", ollama_config, 0.2, sleep=lambda _: None)


class TestServerAdvisedBackoff:
    """Sunucu gerçek süreyi söylüyorsa tahmin etmeye gerek yok."""

    def response(self, status=429, text="", headers=None):
        import httpx

        return httpx.Response(status, text=text, headers=headers or {})

    def test_body_hint_is_read(self):
        from rlens.providers.base import advised_wait

        body = '{"error":{"message":"Rate limit. Please try again in 13.9275s."}}'
        assert advised_wait(self.response(text=body)) == 13.9275

    def test_retry_after_header_is_read(self):
        from rlens.providers.base import advised_wait

        assert advised_wait(self.response(headers={"retry-after": "7"})) == 7.0

    def test_header_wins_over_the_body(self):
        from rlens.providers.base import advised_wait

        body = "try again in 30s"
        assert advised_wait(self.response(text=body, headers={"retry-after": "2"})) == 2.0

    def test_an_http_date_header_falls_through_to_the_body(self):
        from rlens.providers.base import advised_wait

        response = self.response(
            text="try again in 4s", headers={"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}
        )
        assert advised_wait(response) == 4.0

    def test_nothing_advised(self):
        from rlens.providers.base import advised_wait

        assert advised_wait(self.response(status=500, text="oops")) is None

    def test_advice_beats_exponential_backoff(self):
        from rlens.providers.base import backoff_delay

        body = "try again in 13.9s"
        assert backoff_delay(0, self.response(text=body)) == pytest.approx(14.9)

    def test_exponential_backoff_wins_when_larger(self):
        """Sunucu 0.5 derken 4 beklemek zararsız; tersi ikinci bir 429."""
        from rlens.providers.base import backoff_delay

        assert backoff_delay(2, self.response(text="try again in 0.5s")) == 4.0

    def test_a_margin_is_added(self):
        from rlens.providers.base import backoff_delay

        assert backoff_delay(0, self.response(text="try again in 5.04s")) == pytest.approx(6.04)

    def test_absurd_advice_is_capped(self):
        from rlens.providers.base import MAX_RETRY_WAIT_SECONDS, backoff_delay

        delay = backoff_delay(0, self.response(text="try again in 9999s"))
        assert delay == MAX_RETRY_WAIT_SECONDS

    def test_without_a_response_it_is_purely_exponential(self):
        from rlens.providers.base import backoff_delay

        assert backoff_delay(3) == 8.0

    def test_the_retry_loop_uses_it(self, provider_config, monkeypatch):
        """429 gövdesindeki süre gerçekten uygulanıyor mu?"""
        import httpx

        from rlens.providers import base

        waits: list[float] = []
        responses = [
            httpx.Response(429, text="try again in 6s", request=httpx.Request("POST", "http://x")),
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": "ok"}}]},
                request=httpx.Request("POST", "http://x"),
            ),
        ]
        monkeypatch.setattr(base.httpx, "post", lambda *a, **k: responses.pop(0))
        base.post_with_retry("http://x", {}, {}, provider_config, sleep=waits.append)
        assert waits == [7.0]

    def test_a_response_without_headers_does_not_crash(self):
        """Her sağlayıcı `Retry-After` göndermez; eksiklik hata değildir."""
        from rlens.providers.base import advised_wait

        class Bare:
            text = "try again in 3s"

        assert advised_wait(Bare()) == 3.0

    def test_a_response_without_a_body_does_not_crash(self):
        from rlens.providers.base import advised_wait

        class Bare:
            headers = {}

        assert advised_wait(Bare()) is None


class TestOutputLimit:
    """Kesilen yanıt sessizce geçmez (v2.4).

    Groq yanıtı varsayılan çıktı sınırında kesip `finish_reason: length`
    döndürüyordu; araç bunu görmüyordu. `apply`'da yarım patch "diff bloğu
    yok" diye yanlış nedenle reddediliyordu; `advise`'da yarım JSON modelin
    sözleşme ihlali (`unstructured`) sayılırdı — bu bizim sınırımızdır.
    """

    @pytest.fixture
    def limited(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text(
            "provider:\n  name: groq\n  model: m\n  max_output_tokens: 9000\n",
            encoding="utf-8",
        )
        return load_config(search_from=tmp_path).provider

    def test_groq_sends_the_limit(self, limited, monkeypatch):
        recorder = Recorder(FakeResponse(200, {"choices": [{"message": {"content": "x"}}]}))
        monkeypatch.setattr(httpx, "post", recorder)
        monkeypatch.setenv("GROQ_API_KEY", "key")
        GroqProvider().generate("s", "u", limited, 0.2, sleep=lambda _: None)
        assert recorder.calls[0]["json"]["max_completion_tokens"] == 9000

    def test_groq_sends_no_limit_by_default(self, provider_config, monkeypatch):
        recorder = Recorder(FakeResponse(200, {"choices": [{"message": {"content": "x"}}]}))
        monkeypatch.setattr(httpx, "post", recorder)
        monkeypatch.setenv("GROQ_API_KEY", "key")
        GroqProvider().generate("s", "u", provider_config, 0.2, sleep=lambda _: None)
        assert "max_completion_tokens" not in recorder.calls[0]["json"]

    def test_groq_truncation_is_raised_with_the_partial_text(self, provider_config, monkeypatch):
        body = {
            "choices": [{"message": {"content": "```diff\n--- a/x"}, "finish_reason": "length"}]
        }
        monkeypatch.setattr(httpx, "post", Recorder(FakeResponse(200, body)))
        monkeypatch.setenv("GROQ_API_KEY", "key")
        with pytest.raises(ProviderTruncated, match="output limit") as caught:
            GroqProvider().generate("s", "u", provider_config, 0.2, sleep=lambda _: None)
        assert caught.value.partial == "```diff\n--- a/x"
        assert isinstance(caught.value, ProviderError)

    def test_ollama_sends_the_limit_and_detects_truncation(self, tmp_path, monkeypatch):
        (tmp_path / "rlens.yaml").write_text(
            "provider:\n  name: ollama\n  model: llama3\n  max_output_tokens: 500\n",
            encoding="utf-8",
        )
        config = load_config(search_from=tmp_path).provider
        body = {"message": {"content": "part"}, "done_reason": "length"}
        recorder = Recorder(FakeResponse(200, body))
        monkeypatch.setattr(httpx, "post", recorder)
        with pytest.raises(ProviderTruncated):
            OllamaProvider().generate("s", "u", config, 0.2, sleep=lambda _: None)
        assert recorder.calls[0]["json"]["options"]["num_predict"] == 500


class TestRequestTooLarge:
    """HTTP 413: istek sağlayıcının istek başına sınırını aşıyor (LensBench'te
    Groq ücretsiz katmanı, dakikada 8000 token). Yeniden denenmez: aynı istek
    her seferinde aynı boyuttadır."""

    def test_413_is_its_own_error_and_is_not_retried(self, provider_config, monkeypatch):
        from rlens.providers.base import ProviderRequestTooLarge

        recorder = Recorder(FakeResponse(413, {"error": "too large"}, text="Request too large"))
        monkeypatch.setattr(httpx, "post", recorder)
        with pytest.raises(ProviderRequestTooLarge, match="413"):
            post_with_retry("u", {}, {}, provider_config, sleep=lambda _: None)
        assert len(recorder.calls) == 1


class TestRateLimitedAfterRetries:
    def test_exhausted_429_is_its_own_error(self, provider_config, monkeypatch):
        from rlens.providers.base import ProviderRateLimited

        monkeypatch.setattr(httpx, "post", Recorder(*[FakeResponse(429) for _ in range(5)]))
        with pytest.raises(ProviderRateLimited, match="429"):
            post_with_retry("u", {}, {}, provider_config, sleep=lambda _: None)


class TestTooLargeDisguisedAs429:
    """Groq, dakikalık token sınırını tek istek aştığında 413 değil 429 döndürür
    (qwen/qwen3.8-27b ücretsiz katman: "Limit 1000, Requested 1069"). Bu bir
    kota değildir; beklemek çözmez (ön kayıt N4)."""

    BODY = (
        '{"error":{"message":"Request too large for model `qwen/qwen3.8-27b` ... on '
        'output tokens per minute (OTPM): Limit 1000, Requested 1069",'
        '"code":"rate_limit_exceeded"}}'
    )

    def test_is_request_too_large_and_not_retried(self, provider_config, monkeypatch):
        from rlens.providers.base import ProviderRequestTooLarge

        recorder = Recorder(FakeResponse(429, text=self.BODY), FakeResponse(200, {"ok": 1}))
        monkeypatch.setattr(httpx, "post", recorder)
        with pytest.raises(ProviderRequestTooLarge, match="429"):
            post_with_retry("u", {}, {}, provider_config, sleep=lambda _: None)
        assert len(recorder.calls) == 1

    def test_an_ordinary_429_is_still_retried(self, provider_config, monkeypatch):
        recorder = Recorder(
            FakeResponse(429, text="Rate limit reached. Please try again in 2s."),
            FakeResponse(200, {"ok": 1}),
        )
        monkeypatch.setattr(httpx, "post", recorder)
        assert post_with_retry("u", {}, {}, provider_config, sleep=lambda _: None) == {"ok": 1}


class TestGeminiRetryHints:
    def test_retry_in_text(self):
        from rlens.providers.base import advised_wait

        assert advised_wait(FakeResponse(429, text="Please retry in 12.5s.")) == 12.5

    def test_retry_delay_detail(self):
        from rlens.providers.base import advised_wait

        body = '{"details": [{"@type": "RetryInfo", "retryDelay": "37s"}]}'
        assert advised_wait(FakeResponse(429, text=body)) == 37.0


def gemini_body(text="hello", reason="STOP", parts=None):
    return {
        "candidates": [
            {
                "content": {"role": "model", "parts": parts or [{"text": text}]},
                "finishReason": reason,
            }
        ]
    }


class TestGemini:
    @pytest.fixture
    def config(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "secret")
        (tmp_path / "rlens.yaml").write_text(
            "provider:\n  name: gemini\n  model: gemini-test\n  max_output_tokens: 700\n",
            encoding="utf-8",
        )
        return load_config(search_from=tmp_path).provider

    def generate(self, config, monkeypatch, *responses):
        from rlens.providers.gemini import GeminiProvider

        recorder = Recorder(*responses)
        monkeypatch.setattr(httpx, "post", recorder)
        reply = GeminiProvider().generate("sys", "usr", config, 0.2, sleep=lambda _: None)
        return reply, recorder

    def test_request_shape(self, config, monkeypatch):
        reply, recorder = self.generate(config, monkeypatch, FakeResponse(200, gemini_body()))
        assert reply == "hello"
        call = recorder.calls[0]
        assert call["url"].endswith("/models/gemini-test:generateContent")
        assert call["headers"]["x-goog-api-key"] == "secret"
        assert "secret" not in call["url"]
        body = call["json"]
        assert body["systemInstruction"] == {"parts": [{"text": "sys"}]}
        assert body["contents"] == [{"role": "user", "parts": [{"text": "usr"}]}]
        assert body["generationConfig"] == {"temperature": 0.2, "maxOutputTokens": 700}

    def test_thought_parts_are_not_the_reply(self, config, monkeypatch):
        parts = [{"text": "thinking...", "thought": True}, {"text": "a"}, {"text": "b"}]
        reply, _ = self.generate(config, monkeypatch, FakeResponse(200, gemini_body(parts=parts)))
        assert reply == "ab"

    def test_max_tokens_is_truncation_with_partial(self, config, monkeypatch):
        with pytest.raises(ProviderTruncated) as caught:
            self.generate(config, monkeypatch, FakeResponse(200, gemini_body("half", "MAX_TOKENS")))
        assert caught.value.partial == "half"

    def test_empty_reply_is_an_error_not_empty_text(self, config, monkeypatch):
        body = {"candidates": [{"finishReason": "SAFETY"}]}
        with pytest.raises(ProviderError, match="SAFETY"):
            self.generate(config, monkeypatch, FakeResponse(200, body))

    def test_blocked_prompt_is_reported(self, config, monkeypatch):
        body = {"promptFeedback": {"blockReason": "OTHER"}}
        with pytest.raises(ProviderError, match="blocked: OTHER"):
            self.generate(config, monkeypatch, FakeResponse(200, body))

    def test_missing_key_explains_itself(self, config, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY")
        with pytest.raises(ProviderConfigError, match="GEMINI_API_KEY"):
            self.generate(config, monkeypatch, FakeResponse(200, gemini_body()))
