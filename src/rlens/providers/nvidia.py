"""NVIDIA NIM adapter (bulut, opsiyonel).

`integrate.api.nvidia.com` OpenAI uyumlu bir sohbet uç noktasıdır; istek
mantığı Groq ile ortaktır (`openai_compat`). LensBench v1'de Gemini'nin yerine
birincil model için eklendi (ön kayıt N8). 429/503/413 ve kopan bağlantı
`base.post_with_retry`'daki türlere eşlenir.
"""

from __future__ import annotations

from rlens.providers.openai_compat import OpenAICompatibleProvider

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
API_KEY_VARIABLE = "NVIDIA_API_KEY"


class NvidiaProvider(OpenAICompatibleProvider):
    name = "nvidia"
    label = "NVIDIA"
    default_base_url = DEFAULT_BASE_URL
    api_key_variable = API_KEY_VARIABLE
    max_tokens_field = "max_tokens"
