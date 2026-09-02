"""Muğlak modül — KASITLI: katman çıkarımı `unknown` demeli.

Dizin adı hiçbir konvansiyona uymuyor, sınıf soneki yok, ve `helpers` ile
karşılıklı bağımlılık içinde olduğu için topolojik derinlik de belirsiz.
Aracın burada tahmin **zorlamaması** gerekir.

Ayrıca `helpers` ile birlikte KASITLI İHLAL: LV-CYCLE.
"""

from __future__ import annotations

import shared.helpers


class Registry:
    def __init__(self) -> None:
        self._items: dict[str, str] = {}

    def put(self, key: str, value: str) -> None:
        self._items[shared.helpers.normalise(key)] = value

    def get(self, key: str) -> str | None:
        return self._items.get(shared.helpers.normalise(key))

    def size(self) -> int:
        return len(self._items)
