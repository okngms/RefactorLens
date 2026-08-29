"""Sağlayıcı seçimi.

Config'teki ad, sağlayıcı sınıfına burada eşlenir. Yeni bir sağlayıcı eklemek,
bu sözlüğe bir satır eklemek demektir.
"""

from __future__ import annotations

from rlens.config import ProviderConfig
from rlens.providers.base import (
    Provider,
    ProviderConfigError,
    ProviderError,
    load_env_file,
)
from rlens.providers.groq import GroqProvider
from rlens.providers.ollama import OllamaProvider

#: Çekirdek sağlayıcılar. Gemini ve Anthropic opsiyoneldir ve henüz eklenmemiştir.
PROVIDERS = {
    GroqProvider.name: GroqProvider,
    OllamaProvider.name: OllamaProvider,
}

__all__ = [
    "PROVIDERS",
    "Provider",
    "ProviderConfigError",
    "ProviderError",
    "get_provider",
    "load_env_file",
]


def get_provider(config: ProviderConfig) -> Provider:
    """Config'te adı geçen sağlayıcıyı örnekler."""
    factory = PROVIDERS.get(config.name)
    if factory is None:
        raise ProviderConfigError(
            f"No adapter for provider '{config.name}'. Available: {', '.join(sorted(PROVIDERS))}."
        )
    return factory()
