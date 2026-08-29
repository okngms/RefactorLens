"""`rlens.yaml` yükleme, varsayılanlarla birleştirme ve doğrulama.

Tasarım kuralları (bkz. teknik doküman Bölüm 3–4):

* Config dosyası **zorunlu değildir**; yoksa makul varsayılanlar kullanılır.
* Kullanıcı config'i varsayılanların üzerine *derin* birleştirilir; kullanıcının
  yalnızca bir eşiği değiştirmesi diğerlerini silmez.
* **Bilinmeyen anahtar hatadır.** Sessizce yok saymak, kullanıcının yazım
  hatasını (örn. ``max_nestings``) fark etmeden yanlış eşikle çalışmasına yol
  açar — bu araçta kabul edilemez.
* Doğrulama yalnızca "tip doğru mu"ya değil, "anlamlı mı"ya da bakar
  (``warn < critical``, oranlar 0–1 aralığında, sayılar pozitif).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILENAME = "rlens.yaml"

#: Bir metriğin config'te tanımlı olabilecek eşik anahtarları.
_THRESHOLD_KEYS = ("warn", "critical")

#: M1 çekirdek sağlayıcıları + opsiyonel olanlar (bkz. Bölüm 3).
KNOWN_PROVIDERS = ("groq", "ollama", "gemini", "anthropic")
CORE_PROVIDERS = ("groq", "ollama")


DEFAULTS: dict[str, Any] = {
    "provider": {
        "name": "groq",
        "model": None,  # koda gömülmez; kullanıcı config'ten verir
        "base_url": None,  # ollama için örn. http://localhost:11434
        "timeout_seconds": 60,
        "max_retries": 3,
    },
    "scan": {
        "include": ["src/"],
        "exclude": ["tests/", "venv/", ".venv/", "migrations/"],
        "output_dir": "reports/",
    },
    "advise": {
        "top_n": 3,
        "max_context_tokens": 12000,
        "temperature": 0.2,
    },
    "metrics": {
        "cam_min_annotation_coverage": 0.7,
    },
    "thresholds": {
        "cyclomatic_complexity": {"warn": 10, "critical": 20},
        "max_params": {"warn": 5},
        "max_nesting": {"warn": 4},
        "lcom4": {"warn": 2, "critical": 4},
        "dcc": {"warn": 7},
        "wmc": {"warn": 50},
        "nom": {"warn": 20},
    },
}


class ConfigError(Exception):
    """Config dosyası okunamadığında veya geçersiz olduğunda yükseltilir."""


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str | None
    base_url: str | None
    timeout_seconds: int
    max_retries: int

    @property
    def is_local(self) -> bool:
        """Kod dışarı gönderiliyor mu? Gizlilik uyarısı bu bilgiye dayanır."""
        return self.name == "ollama"


@dataclass(frozen=True)
class ScanConfig:
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    output_dir: str


@dataclass(frozen=True)
class AdviseConfig:
    top_n: int
    max_context_tokens: int
    temperature: float


@dataclass(frozen=True)
class MetricsConfig:
    cam_min_annotation_coverage: float


@dataclass(frozen=True)
class Threshold:
    """Tek bir metriğin eşikleri. `critical` opsiyoneldir."""

    warn: float
    critical: float | None = None

    def level(self, value: float | None) -> str | None:
        """Bir değeri ``"warn"`` / ``"critical"`` / ``None`` olarak sınıflandırır.

        ``value is None`` (hesaplanamayan metrik) için asla ihlal üretmez —
        "hesaplanamayan metrik uydurulmaz" ilkesinin doğal sonucu.
        """
        if value is None:
            return None
        if self.critical is not None and value >= self.critical:
            return "critical"
        if value >= self.warn:
            return "warn"
        return None


@dataclass(frozen=True)
class Config:
    provider: ProviderConfig
    scan: ScanConfig
    advise: AdviseConfig
    metrics: MetricsConfig
    thresholds: dict[str, Threshold] = field(default_factory=dict)
    source_path: Path | None = None

    @property
    def loaded_from_file(self) -> bool:
        return self.source_path is not None


# --------------------------------------------------------------------------- #
# Yükleme
# --------------------------------------------------------------------------- #


def find_config_file(start: Path) -> Path | None:
    """`start` dizininden köke doğru yürüyerek ilk `rlens.yaml`'ı bulur.

    Alt dizinden çalıştırıldığında da proje kökündeki config'in bulunmasını
    sağlar (git'in `.git` arayışıyla aynı mantık).
    """
    start = start.resolve()
    candidates = [start, *start.parents] if start.is_dir() else [start.parent, *start.parents]
    for directory in candidates:
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_config(path: Path | None = None, *, search_from: Path | None = None) -> Config:
    """Config'i yükler.

    Args:
        path: Açıkça verilen config yolu. Verilmişse ve yoksa hata.
        search_from: `path` yoksa arama başlangıç dizini (varsayılan: cwd).
    """
    config_path: Path | None
    if path is not None:
        config_path = Path(path)
        if not config_path.is_file():
            raise ConfigError(f"Config dosyası bulunamadı: {config_path}")
    else:
        config_path = find_config_file(search_from or Path.cwd())

    raw: dict[str, Any] = {}
    if config_path is not None:
        try:
            text = config_path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - dosya sistemi hatası
            raise ConfigError(f"Config okunamadı: {config_path} ({exc})") from exc
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Config geçerli YAML değil: {config_path}\n{exc}") from exc
        if parsed is None:
            parsed = {}
        if not isinstance(parsed, dict):
            raise ConfigError(f"Config'in kökü bir eşleme (mapping) olmalı: {config_path}")
        raw = parsed

    merged = _deep_merge(copy.deepcopy(DEFAULTS), raw)
    _reject_unknown_keys(raw)
    return _build(merged, config_path)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _reject_unknown_keys(raw: dict[str, Any]) -> None:
    """Yazım hatalarını sessizce yutmamak için bilinmeyen anahtarları reddeder."""
    unknown_top = set(raw) - set(DEFAULTS)
    if unknown_top:
        raise ConfigError(
            f"Bilinmeyen config bölümü: {', '.join(sorted(unknown_top))}. "
            f"Beklenenler: {', '.join(sorted(DEFAULTS))}"
        )
    for section in ("provider", "scan", "advise", "metrics"):
        value = raw.get(section)
        if isinstance(value, dict):
            unknown = set(value) - set(DEFAULTS[section])
            if unknown:
                raise ConfigError(
                    f"`{section}` altında bilinmeyen anahtar: {', '.join(sorted(unknown))}"
                )
    thresholds = raw.get("thresholds")
    if isinstance(thresholds, dict):
        for metric, spec in thresholds.items():
            if not isinstance(spec, dict):
                raise ConfigError(f"`thresholds.{metric}` bir eşleme olmalı (örn. {{warn: 10}})")
            unknown = set(spec) - set(_THRESHOLD_KEYS)
            if unknown:
                raise ConfigError(
                    f"`thresholds.{metric}` altında bilinmeyen anahtar: "
                    f"{', '.join(sorted(unknown))}"
                )


# --------------------------------------------------------------------------- #
# Doğrulama + inşa
# --------------------------------------------------------------------------- #


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def _as_int(value: Any, label: str, *, minimum: int = 1) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool), f"`{label}` tam sayı olmalı")
    _require(value >= minimum, f"`{label}` en az {minimum} olmalı (verilen: {value})")
    return int(value)


def _as_float(value: Any, label: str, *, low: float, high: float) -> float:
    _require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"`{label}` sayı olmalı",
    )
    _require(low <= value <= high, f"`{label}` {low}–{high} aralığında olmalı (verilen: {value})")
    return float(value)


def _as_str_list(value: Any, label: str) -> tuple[str, ...]:
    _require(isinstance(value, list), f"`{label}` bir liste olmalı")
    _require(all(isinstance(item, str) for item in value), f"`{label}` yalnızca metin içermeli")
    return tuple(value)


def _build(data: dict[str, Any], source: Path | None) -> Config:
    provider_raw = data["provider"]
    name = provider_raw["name"]
    _require(
        name in KNOWN_PROVIDERS,
        f"Bilinmeyen sağlayıcı: {name}. Bilinenler: {', '.join(KNOWN_PROVIDERS)}",
    )
    model = provider_raw["model"]
    _require(model is None or isinstance(model, str), "`provider.model` metin ya da boş olmalı")
    base_url = provider_raw["base_url"]
    _require(
        base_url is None or isinstance(base_url, str),
        "`provider.base_url` metin ya da boş olmalı",
    )
    provider = ProviderConfig(
        name=name,
        model=model,
        base_url=base_url,
        timeout_seconds=_as_int(provider_raw["timeout_seconds"], "provider.timeout_seconds"),
        max_retries=_as_int(provider_raw["max_retries"], "provider.max_retries", minimum=0),
    )

    scan_raw = data["scan"]
    _require(isinstance(scan_raw["output_dir"], str), "`scan.output_dir` metin olmalı")
    scan = ScanConfig(
        include=_as_str_list(scan_raw["include"], "scan.include"),
        exclude=_as_str_list(scan_raw["exclude"], "scan.exclude"),
        output_dir=scan_raw["output_dir"],
    )

    advise_raw = data["advise"]
    advise = AdviseConfig(
        top_n=_as_int(advise_raw["top_n"], "advise.top_n"),
        max_context_tokens=_as_int(
            advise_raw["max_context_tokens"], "advise.max_context_tokens", minimum=500
        ),
        temperature=_as_float(advise_raw["temperature"], "advise.temperature", low=0.0, high=2.0),
    )

    metrics_raw = data["metrics"]
    metrics = MetricsConfig(
        cam_min_annotation_coverage=_as_float(
            metrics_raw["cam_min_annotation_coverage"],
            "metrics.cam_min_annotation_coverage",
            low=0.0,
            high=1.0,
        )
    )

    thresholds: dict[str, Threshold] = {}
    for metric, spec in data["thresholds"].items():
        _require(isinstance(spec, dict), f"`thresholds.{metric}` bir eşleme olmalı")
        _require("warn" in spec, f"`thresholds.{metric}` için `warn` zorunlu")
        warn = _as_float(spec["warn"], f"thresholds.{metric}.warn", low=0.0, high=1e9)
        critical: float | None = None
        if spec.get("critical") is not None:
            critical = _as_float(
                spec["critical"], f"thresholds.{metric}.critical", low=0.0, high=1e9
            )
            _require(
                critical > warn,
                f"`thresholds.{metric}`: critical ({critical}) > warn ({warn}) olmalı",
            )
        thresholds[metric] = Threshold(warn=warn, critical=critical)

    return Config(
        provider=provider,
        scan=scan,
        advise=advise,
        metrics=metrics,
        thresholds=thresholds,
        source_path=source,
    )
