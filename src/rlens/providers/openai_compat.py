"""OpenAI uyumlu sohbet uç noktaları için ortak adaptör.

Groq ve NVIDIA NIM aynı `/chat/completions` sözleşmesini konuşur; fark yalnızca
adres, anahtar değişkeni ve çıktı sınırı alanının adıdır. Alt sınıflar bunları
sınıf özniteliği olarak verir; istek, yeniden deneme ve kesilme mantığı tek
yerdedir.

Model adı koda gömülmez — sağlayıcıların model kataloğu sık değişir ve gömülü
bir ad, paket eskidiğinde sessizce kırılır.
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


class OpenAICompatibleProvider:
    name: str
    #: Kullanıcıya görünen ad (hata mesajları).
    label: str
    default_base_url: str
    api_key_variable: str
    #: Çıktı sınırının istek alanı; sağlayıcıya göre değişir.
    max_tokens_field: str = "max_tokens"

    def generate(
        self,
        system: str,
        user: str,
        config: ProviderConfig,
        temperature: float = 0.2,
        *,
        sleep=time.sleep,
    ) -> str:
        model = require_model(config, self.label)
        key = require_api_key(self.api_key_variable, self.label)
        base_url = (config.base_url or self.default_base_url).rstrip("/")

        payload = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if config.max_output_tokens:
            payload[self.max_tokens_field] = config.max_output_tokens
        data = post_with_retry(
            f"{base_url}/chat/completions",
            payload,
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            config,
            sleep=sleep,
        )

        try:
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                f"Unexpected response shape from {self.label}; no message content found."
            ) from exc
        if choice.get("finish_reason") == "length":
            raise ProviderTruncated(
                f"{self.label} stopped the reply at the model's output limit "
                "(finish_reason: length). Raise `provider.max_output_tokens` in rlens.yaml.",
                partial=content or "",
            )
        if not isinstance(content, str):
            # NVIDIA bir yanıtta `content: null` döndürdü (2026-11-11); boş değer
            # `advise`'da TypeError ile çöküyordu. Yanıtın şekli hataya yazılır.
            message = choice.get("message") or {}
            raise ProviderError(
                f"{self.label} returned no message content "
                f"(finish_reason: {choice.get('finish_reason')}; "
                f"message fields: {', '.join(sorted(message)) or 'none'}; "
                f"usage: {data.get('usage')})."
            )
        return content
