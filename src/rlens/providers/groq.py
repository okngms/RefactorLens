"""Groq adapter (bulut).

Groq, OpenAI uyumlu bir sohbet uç noktası sunar ve ücretsiz bir katmanı vardır;
bu yüzden "anahtar al, hemen dene" senaryosu için çekirdek sağlayıcıdır.

Model adı koda gömülmez — sağlayıcıların model kataloğu sık değişir ve gömülü
bir ad, paket eskidiğinde sessizce kırılır.
"""

from __future__ import annotations

import time

from rlens.config import ProviderConfig
from rlens.providers.base import (
    ProviderError,
    post_with_retry,
    require_api_key,
    require_model,
)

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
API_KEY_VARIABLE = "GROQ_API_KEY"


class GroqProvider:
    name = "groq"

    def generate(
        self,
        system: str,
        user: str,
        config: ProviderConfig,
        temperature: float = 0.2,
        *,
        sleep=time.sleep,
    ) -> str:
        model = require_model(config, "Groq")
        key = require_api_key(API_KEY_VARIABLE, "Groq")
        base_url = (config.base_url or DEFAULT_BASE_URL).rstrip("/")

        payload = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = post_with_retry(
            f"{base_url}/chat/completions",
            payload,
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            config,
            sleep=sleep,
        )

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                "Unexpected response shape from Groq; no message content found."
            ) from exc
