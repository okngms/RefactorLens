"""Muğlak modül — `registry` ile döngüsel bağımlılık (LV-CYCLE).

Döngü `import x` biçimiyle kurulur ve erişim fonksiyon içinde olduğu için
çalışma zamanında sorun çıkarmaz; ama import grafiğinde gerçek bir SCC'dir.
"""

from __future__ import annotations

import shared.registry


def normalise(key: str) -> str:
    return key.strip().lower()


def registry_size(registry) -> int:
    if not isinstance(registry, shared.registry.Registry):
        raise TypeError("expected a Registry")
    return registry.size()
