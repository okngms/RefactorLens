"""LLM sağlayıcı sözleşmesi, hata tipleri ve ortak yeniden deneme mantığı.

Yeni bir sağlayıcı eklemek = `Provider` protokolünü uygulayan ~30 satırlık bir
dosya. Çekirdek ikili bilinçlidir: **Groq** anahtar alıp hemen denemeyi mümkün
kılar, **Ollama** kodun makineden hiç çıkmamasını sağlar.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx

from rlens.config import ProviderConfig


class ProviderError(Exception):
    """Sağlayıcı çağrısı kalıcı olarak başarısız olduğunda yükseltilir."""


class ProviderConfigError(ProviderError):
    """Eksik model adı veya API anahtarı gibi yapılandırma sorunları."""


@runtime_checkable
class Provider(Protocol):
    """Tüm sağlayıcıların uyduğu tek metotlu sözleşme."""

    name: str

    def generate(self, system: str, user: str, config: ProviderConfig, temperature: float) -> str:
        """Prompt'u modele gönderir ve ham metin yanıtı döndürür.

        `temperature` ayrı bir parametredir çünkü config'te `advise` bölümüne
        aittir, sağlayıcıya değil: aynı sağlayıcı farklı sıcaklıklarla
        çağrılabilir ve Faz 5 deneyi bunu sabitlemek zorundadır.

        Uygulama kuralları:

        * `config.timeout_seconds` **zorunlu** uygulanır. Zaman aşımı olmayan
          bir çağrı, terminali süresiz kilitleyebilir.
        * Geçici hatalarda `config.max_retries` kadar geri çekilmeli tekrar.
        * Kalıcı hatada `ProviderError`; asla sessizce boş metin dönmez.
        """
        ...


def load_env_file(start: Path | None = None) -> None:
    """`.env` dosyasındaki anahtarları ortama yükler.

    Küçük ve bağımlılıksız: `python-dotenv` eklemek yerine on satır yazmak,
    kurulum yükünü artırmamak için tercih edildi. Zaten tanımlı olan ortam
    değişkenleri **ezilmez** — kabuktan verilen değer dosyadan gelenden
    önceliklidir.
    """
    directory = (start or Path.cwd()).resolve()
    for candidate in [directory, *directory.parents]:
        env_file = candidate / ".env"
        if not env_file.is_file():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value
        return


def require_api_key(variable: str, provider: str) -> str:
    """Ortamdan API anahtarını okur; yoksa ne yapılacağını söyleyerek hata verir."""
    key = os.environ.get(variable, "").strip()
    if not key:
        raise ProviderConfigError(
            f"{provider} requires an API key. Set {variable} in your environment "
            f"or in a .env file (see .env.example)."
        )
    return key


def require_model(config: ProviderConfig, provider: str) -> str:
    """Model adını config'ten okur; koda gömülmez."""
    if not config.model:
        raise ProviderConfigError(
            f"No model configured for {provider}. Set `provider.model` in rlens.yaml. "
            f"Model names change often, so rlens does not hard-code one."
        )
    return config.model


#: Yeniden denemeye değer HTTP durum kodları: oran limiti ve sunucu hataları.
RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


def post_with_retry(
    url: str,
    payload: dict,
    headers: dict[str, str],
    config: ProviderConfig,
    *,
    sleep=time.sleep,
) -> dict:
    """Geri çekilmeli POST.

    Ücretsiz katmanlarda oran limiti kuraldır, istisna değil. Geri çekilme
    üstel olur (1s, 2s, 4s…) çünkü sabit aralıkla ısrar etmek limiti daha da
    kötüleştirir.

    `sleep` dışarıdan verilebilir; testler gerçekten beklemek zorunda kalmasın
    diye.
    """
    last_error: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            response = httpx.post(
                url,
                json=payload,
                headers=headers,
                timeout=config.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < config.max_retries:
                sleep(2**attempt)
                continue
            raise ProviderError(
                f"Request timed out after {config.timeout_seconds}s "
                f"({config.max_retries + 1} attempts)."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Network error: {exc}") from exc

        if response.status_code in RETRYABLE_STATUS and attempt < config.max_retries:
            sleep(2**attempt)
            continue

        if response.status_code == 401:
            raise ProviderError("Authentication failed. Check your API key.")
        if response.status_code == 404:
            raise ProviderError(
                f"Endpoint or model not found ({url}). Check `provider.model` "
                f"and `provider.base_url`."
            )
        if response.status_code >= 400:
            raise ProviderError(
                f"Provider returned HTTP {response.status_code}: {response.text[:300]}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError("Provider returned a non-JSON response.") from exc

    raise ProviderError(f"Request failed after retries: {last_error}")
