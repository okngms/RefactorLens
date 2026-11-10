"""Groq adapter (bulut).

Groq, OpenAI uyumlu bir sohbet uç noktası sunar ve ücretsiz bir katmanı vardır;
bu yüzden "anahtar al, hemen dene" senaryosu için çekirdek sağlayıcıdır.
İstek mantığı `openai_compat`'tadır; burada yalnızca Groq'a özgü ayarlar durur.
"""

from __future__ import annotations

from rlens.providers.openai_compat import OpenAICompatibleProvider

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
API_KEY_VARIABLE = "GROQ_API_KEY"


class GroqProvider(OpenAICompatibleProvider):
    name = "groq"
    label = "Groq"
    default_base_url = DEFAULT_BASE_URL
    api_key_variable = API_KEY_VARIABLE
    max_tokens_field = "max_completion_tokens"
