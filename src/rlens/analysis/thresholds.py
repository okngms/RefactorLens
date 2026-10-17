"""Eşik ihlalleri: hangi metrik hangi seviyede eşiği aşıyor.

Terminal tablosunu boyar, hedef seçimi (`advise.selector`) önceliği bundan
hesaplar. Eskiden `report.terminal`'deydi; uygulama katmanı sunum katmanına
geri çağırıyordu (docs/self-architecture.md §2). Eşiklerin kendisi
`config`'te; burası onları ölçülmüş değerlere uygular.
"""

from __future__ import annotations

from rlens.analysis.model import ClassReport, FunctionReport
from rlens.config import Config

#: Sınıf metriği adı → config'teki eşik anahtarı.
_CLASS_THRESHOLD_KEYS = {
    "nom": "nom",
    "wmc": "wmc",
    "lcom4": "lcom4",
    "dcc": "dcc",
}

#: Fonksiyon metriği adı → config anahtarı.
_FUNCTION_THRESHOLD_KEYS = {
    "cyclomatic_complexity": "cyclomatic_complexity",
    "param_count": "max_params",
    "max_nesting": "max_nesting",
}


def class_violations(report: ClassReport, config: Config) -> dict[str, str]:
    """Sınıfın hangi metriklerinin hangi seviyede eşiği aştığı."""
    levels: dict[str, str] = {}
    for metric, key in _CLASS_THRESHOLD_KEYS.items():
        # Aynı DCC değeri application-service'te tasarım gereği, domain
        # modelinde kokudur. Katman bilinmiyorsa genel eşiğe düşülür.
        threshold = config.threshold_for(key, report.layer)
        if threshold is None:
            continue
        level = threshold.level(getattr(report, metric))
        if level:
            levels[metric] = level
    return levels


def function_violations(report: FunctionReport, config: Config) -> dict[str, str]:
    """Fonksiyonun hangi metriklerinin eşiği aştığı."""
    levels: dict[str, str] = {}
    for metric, key in _FUNCTION_THRESHOLD_KEYS.items():
        threshold = config.thresholds.get(key)
        if threshold is None:
            continue
        level = threshold.level(getattr(report, metric))
        if level:
            levels[metric] = level
    return levels
