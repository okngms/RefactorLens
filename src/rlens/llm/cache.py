"""Prompt-hash tabanlı yanıt önbelleği.

**Neden var:** Faz 5 deneyi 108 çağrı istiyor ve kesintiye dayanıklı olmak
zorunda. Önbellek olmadan yarıda kalan bir koşuyu tekrarlamak baştan ödemek
demektir.

**Anahtar neden prompt metninin tamamı:** Sağlayıcı, model ve prompt üçlüsü
yanıtı belirler. Hedef adı gibi kısa bir anahtar kullanmak, prompt değiştiğinde
eski yanıtı döndürürdü — deneyde bu, A/B koşullarının birbirine karışması
demek olurdu.

Sıcaklık anahtara **dahil değildir**: aynı prompt farklı sıcaklıkla farklı
yanıt verir, ama deney protokolü sıcaklığı koşu boyunca sabitler. Sıcaklık
değiştirilecekse `--no-cache` kullanılmalıdır; bu sınırlılık burada yazılıdır.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from rlens.config import CacheConfig


def prompt_hash(provider: str, model: str | None, prompt: str, salt: str = "") -> str:
    """Önbellek anahtarı ve rapora yazılan `prompt_hash`.

    Aynı değer deney kayıtlarında da kullanılır: iki koşunun aynı prompt'la
    yapıldığını kanıtlamanın tek yolu budur.

    **`salt` neden var:** deney protokolü aynı soruyu n kez sormayı gerektirir.
    Tuz olmadan her tekrar aynı anahtarı üretir, ikinci ve üçüncü çağrı
    önbellekten döner ve **tekrarlar birbirinin kopyası olur**. Tutarlılık
    ölçümü her yerde 1.0 çıkar, varyans görünmez, deney sessizce anlamsızlaşır.

    Tuz normal kullanımda boştur; yalnızca deney betikleri tekrar numarasını
    geçer. Böylece hem tekrarlar bağımsız kalır hem yarıda kalan koşu kaldığı
    yerden devam edebilir.
    """
    payload = "\n".join([provider, model or "", prompt, salt])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class ResponseCache:
    """Diskte yaşayan basit anahtar-değer önbelleği."""

    config: CacheConfig
    hits: int = 0
    misses: int = 0
    writes: int = 0

    @property
    def directory(self) -> Path:
        return Path(self.config.directory)

    def _path(self, key: str) -> Path:
        # İlk iki karakterle alt dizin: tek dizinde binlerce dosya birikmesin.
        return self.directory / key[:2] / f"{key}.json"

    def get(self, key: str) -> str | None:
        """Önbellekteki yanıt, yoksa None. Bozuk kayıt sessizce ıskalanır."""
        if not self.config.enabled:
            return None
        path = self._path(key)
        if not path.is_file():
            self.misses += 1
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            reply = payload["reply"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            # Bozuk önbellek kaydı bir hata değil; yeniden üretilebilir.
            self.misses += 1
            return None
        self.hits += 1
        return reply

    def set(self, key: str, reply: str, meta: dict | None = None) -> None:
        """Yanıtı yazar. Yazamamak ölümcül değildir — önbellek bir kolaylıktır."""
        if not self.config.enabled:
            return
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "key": key,
                        "cached_at": datetime.now(UTC).isoformat(timespec="seconds"),
                        "meta": meta or {},
                        "reply": reply,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            self.writes += 1
        except OSError:
            pass

    def summary(self) -> dict[str, int | bool]:
        return {
            "enabled": self.config.enabled,
            "hits": self.hits,
            "misses": self.misses,
            "writes": self.writes,
        }

    def describe(self) -> str:
        if not self.config.enabled:
            return "cache disabled"
        return f"cache {self.hits} hit / {self.misses} miss"
