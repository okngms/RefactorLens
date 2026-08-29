"""Ollama adapter (lokal).

Kodun makineden hiç çıkmaması gereken durumlar için. API anahtarı istemez;
karşılığında modeli kendiniz indirip çalıştırırsınız.

Yerel modeller genellikle daha yavaştır, bu yüzden zaman aşımının bulut
sağlayıcılardaki kadar kısa tutulmaması gerekebilir.
"""

from __future__ import annotations

import time

from rlens.config import ProviderConfig
from rlens.providers.base import (
    ProviderError,
    post_with_retry,
    require_model,
)

DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider:
    name = "ollama"

    def generate(
        self,
        system: str,
        user: str,
        config: ProviderConfig,
        temperature: float = 0.2,
        *,
        sleep=time.sleep,
    ) -> str:
        model = require_model(config, "Ollama")
        base_url = (config.base_url or DEFAULT_BASE_URL).rstrip("/")

        payload = {
            "model": model,
            "stream": False,
            "options": {"temperature": temperature},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = post_with_retry(
            f"{base_url}/api/chat",
            payload,
            {"Content-Type": "application/json"},
            config,
            sleep=sleep,
        )

        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ProviderError(
                "Unexpected response shape from Ollama; no message content found. "
                "Is the model pulled and the server running?"
            ) from exc
