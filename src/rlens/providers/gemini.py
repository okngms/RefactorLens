"""Gemini adapter (bulut, opsiyonel).

Google'ın `generateContent` uç noktası. LensBench v1'de üçüncü birincil model
için eklendi: Groq ücretsiz katmanındaki qwen, istek başına çıktı sınırı
yüzünden hiç çağrılamıyordu (ön kayıt N4).

Model adı koda gömülmez; sistem talimatı `systemInstruction` alanıyla, kullanıcı
metni tek bir `user` turu olarak gönderilir.
"""

from __future__ import annotations

import time

from rlens.config import ProviderConfig
from rlens.providers.base import (
    ProviderError,
    ProviderTruncated,
    post_with_retry,
    require_api_key,
    require_model,
)

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
API_KEY_VARIABLE = "GEMINI_API_KEY"


class GeminiProvider:
    name = "gemini"

    def generate(
        self,
        system: str,
        user: str,
        config: ProviderConfig,
        temperature: float = 0.2,
        *,
        sleep=time.sleep,
    ) -> str:
        model = require_model(config, "Gemini")
        key = require_api_key(API_KEY_VARIABLE, "Gemini")
        base_url = (config.base_url or DEFAULT_BASE_URL).rstrip("/")

        generation = {"temperature": temperature}
        if config.max_output_tokens:
            generation["maxOutputTokens"] = config.max_output_tokens
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": generation,
        }
        data = post_with_retry(
            f"{base_url}/models/{model}:generateContent",
            payload,
            # Anahtar başlıkta gider, URL'de değil: URL hata mesajlarına düşer.
            {"x-goog-api-key": key, "Content-Type": "application/json"},
            config,
            sleep=sleep,
        )

        try:
            candidate = data["candidates"][0]
        except (KeyError, IndexError, TypeError) as exc:
            feedback = data.get("promptFeedback") if isinstance(data, dict) else None
            blocked = (feedback or {}).get("blockReason")
            detail = f" (prompt blocked: {blocked})" if blocked else ""
            raise ProviderError(
                f"Unexpected response shape from Gemini; no candidate found{detail}."
            ) from exc
        # Düşünme parçaları (`thought: true`) yanıt değildir; yalnızca metin birleşir.
        parts = (candidate.get("content") or {}).get("parts") or []
        content = "".join(
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and not part.get("thought")
        )
        reason = candidate.get("finishReason")
        if reason == "MAX_TOKENS":
            raise ProviderTruncated(
                "Gemini stopped the reply at the model's output limit (finishReason: MAX_TOKENS). "
                "Raise `provider.max_output_tokens` in rlens.yaml.",
                partial=content,
            )
        if not content:
            raise ProviderError(f"Gemini returned no text (finishReason: {reason or 'unknown'}).")
        return content
