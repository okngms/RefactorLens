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
        # Varsayılan "her şey"dir, "src/" değil. Kullanıcı taranacak yolu zaten
        # argümanla seçer; config'in onu ikinci kez daraltması sürpriz üretir:
        # `rlens scan src/rlens` komutu "src/" filtresiyle hiçbir şey bulamazdı.
        # Daraltma isteyen `include` yazar; varsayılan davranış öngörülebilir olmalı.
        "include": ["."],
        "exclude": ["tests/", "venv/", ".venv/", "migrations/", "build/", "dist/"],
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
    "arch": {
        "enabled": True,
        "scheme": {
            "layers": ["presentation", "application", "domain", "infrastructure"],
            "allowed": {
                "presentation": ["application", "domain"],
                "application": ["domain"],
                "infrastructure": ["domain"],
                "domain": [],
            },
            "allow_skip": False,
        },
        # Beyan: verilirse çıkarım hiç çalışmaz (`source: declared`).
        "layers": {},
        "conventions": {"extra_dirs": {}, "extra_suffixes": {}},
        # Bu güvenin altındaki atama `unknown` olur. Tahmin zorlanmaz.
        "min_confidence": 0.5,
    },
    "smells": {
        "god_class": {"nom": 20, "wmc": 50, "lcom4": 3},
        "data_class": {"max_nom": 5, "min_dam": 0.5, "accessor_ratio": 0.7},
        "feature_envy": {"ratio": 2.0, "min_accesses": 3},
        "long_method": {"loc": 40},
    },
    "budget": {"max_calls_per_run": 10, "max_tokens_per_call": 4000},
    "cache": {"enabled": True, "dir": ".rlens-cache/"},
    "verify": {"treat_suspicious_as_regression": True},
    "thresholds": {
        # Katman bazlı geçersiz kılma: `by_layer.<katman>.<metrik>.<warn|critical>`
        "by_layer": {},
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
class SchemeConfig:
    """Katman şeması: hangi katmanlar var, hangisi hangisini import edebilir."""

    layers: tuple[str, ...]
    allowed: dict[str, tuple[str, ...]]
    allow_skip: bool

    def may_import(self, source: str, destination: str) -> bool:
        """`source` katmanı `destination`'ı import edebilir mi?

        Aynı katman içi importlar her zaman serbesttir; katmanlar arası kural
        `allowed` tablosundan okunur.
        """
        if source == destination:
            return True
        return destination in self.allowed.get(source, ())

    def depth(self, layer: str) -> int | None:
        """Katmanın şemadaki sırası. Bilinmeyen katman için None."""
        try:
            return self.layers.index(layer)
        except ValueError:
            return None


@dataclass(frozen=True)
class ArchConfig:
    enabled: bool
    scheme: SchemeConfig
    declared: dict[str, tuple[str, ...]]
    """Beyan edilmiş katman → yol önekleri. Boşsa çıkarım çalışır."""

    extra_dirs: dict[str, tuple[str, ...]]
    extra_suffixes: dict[str, tuple[str, ...]]
    min_confidence: float

    @property
    def has_declaration(self) -> bool:
        return bool(self.declared)


@dataclass(frozen=True)
class SmellsConfig:
    """Koku kurallarının eşikleri. Kurallar LLM'siz, tamamen kural tabanlıdır."""

    god_class_nom: int
    god_class_wmc: int
    god_class_lcom4: int
    data_class_max_nom: int
    data_class_min_dam: float
    data_class_accessor_ratio: float
    feature_envy_ratio: float
    feature_envy_min_accesses: int
    """Oranın tek başına yetmediği durum: iki erişim her metotta olur.

    Literatür kuralı (Lanza & Marinescu) "birkaç yabancı attribute" der; oran
    olmadan sayı, sayı olmadan oran yanlış pozitif üretir."""

    long_method_loc: int


@dataclass(frozen=True)
class BudgetConfig:
    max_calls_per_run: int
    max_tokens_per_call: int


@dataclass(frozen=True)
class CacheConfig:
    enabled: bool
    directory: str


@dataclass(frozen=True)
class VerifyConfig:
    treat_suspicious_as_regression: bool
    """Metrikler iyileşirken public arayüz küçüldüyse bu bir regresyondur."""


@dataclass(frozen=True)
class Config:
    provider: ProviderConfig
    scan: ScanConfig
    advise: AdviseConfig
    metrics: MetricsConfig
    thresholds: dict[str, Threshold] = field(default_factory=dict)
    by_layer_thresholds: dict[str, dict[str, Threshold]] = field(default_factory=dict)
    arch: ArchConfig | None = None
    smells: SmellsConfig | None = None
    budget: BudgetConfig | None = None
    cache: CacheConfig | None = None
    verify: VerifyConfig | None = None
    source_path: Path | None = None

    def threshold_for(self, metric: str, layer: str | None = None) -> Threshold | None:
        """Bir metriğin eşiği, katman geçersiz kılmaları uygulanmış hâliyle.

        Aynı DCC değeri application-service sınıfında tasarım gereği, domain
        modelinde kokudur. Katman bilinmiyorsa (`None` veya `unknown`) genel
        eşik kullanılır — tahmin zorlanmaz.
        """
        if layer and layer != "unknown":
            override = self.by_layer_thresholds.get(layer, {}).get(metric)
            if override is not None:
                return override
        return self.thresholds.get(metric)

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
            raise ConfigError(f"Config file not found: {config_path}")
    else:
        config_path = find_config_file(search_from or Path.cwd())

    raw: dict[str, Any] = {}
    if config_path is not None:
        try:
            text = config_path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - dosya sistemi hatası
            raise ConfigError(f"Cannot read config: {config_path} ({exc})") from exc
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Config is not valid YAML: {config_path}\n{exc}") from exc
        if parsed is None:
            parsed = {}
        if not isinstance(parsed, dict):
            raise ConfigError(f"Config root must be a mapping: {config_path}")
        raw = parsed

    merged = _deep_merge(copy.deepcopy(DEFAULTS), raw)
    _replace_scheme_if_redefined(merged, raw)
    _reject_unknown_keys(raw)
    return _build(merged, config_path)


def _replace_scheme_if_redefined(merged: dict[str, Any], raw: dict[str, Any]) -> None:
    """Katman kümesi yeniden tanımlandıysa izin tablosu **birleştirilmez**.

    Derin birleştirme burada yanlış davranırdı: kullanıcı `layers: [ui, core]`
    yazdığında varsayılan `allowed` içindeki `presentation` girdisi ayakta
    kalır ve şema kendi içinde tutarsız hale gelirdi.

    Kural: katmanları yeniden tanımlıyorsan izinleri de tanımlarsın. Böylece
    kullanıcının yazdığı her katman adı doğrulanır; sessizce atılan girdi
    olmaz.
    """
    scheme_raw = raw.get("arch", {}).get("scheme")
    if not isinstance(scheme_raw, dict) or "layers" not in scheme_raw:
        return
    merged["arch"]["scheme"]["allowed"] = copy.deepcopy(scheme_raw.get("allowed", {}))


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _reject_unknown_nested(raw: dict[str, Any]) -> None:
    """`arch.scheme`, `arch.conventions` ve `smells` içindeki anahtarlar.

    Bunlar iki seviye derinde olduğu için üst düzey döngü yakalayamaz. Katman
    ve koku adlarındaki yazım hataları sessiz kalırsa ihlaller hiç görünmez.
    """
    arch = raw.get("arch")
    if isinstance(arch, dict):
        for block in ("scheme", "conventions"):
            value = arch.get(block)
            if isinstance(value, dict):
                unknown = set(value) - set(DEFAULTS["arch"][block])
                if unknown:
                    raise ConfigError(
                        f"Unknown key under `arch.{block}`: {', '.join(sorted(unknown))}"
                    )

    smells = raw.get("smells")
    if isinstance(smells, dict):
        unknown = set(smells) - set(DEFAULTS["smells"])
        if unknown:
            raise ConfigError(f"Unknown smell rule: {', '.join(sorted(unknown))}")
        for rule, spec in smells.items():
            if not isinstance(spec, dict):
                raise ConfigError(f"`smells.{rule}` must be a mapping")
            unknown = set(spec) - set(DEFAULTS["smells"][rule])
            if unknown:
                raise ConfigError(
                    f"Unknown key under `smells.{rule}`: {', '.join(sorted(unknown))}"
                )


def _reject_unknown_keys(raw: dict[str, Any]) -> None:
    """Yazım hatalarını sessizce yutmamak için bilinmeyen anahtarları reddeder."""
    unknown_top = set(raw) - set(DEFAULTS)
    if unknown_top:
        raise ConfigError(
            f"Unknown config section: {', '.join(sorted(unknown_top))}. "
            f"Expected one of: {', '.join(sorted(DEFAULTS))}"
        )
    for section in ("provider", "scan", "advise", "metrics", "arch", "budget", "cache", "verify"):
        value = raw.get(section)
        if isinstance(value, dict):
            unknown = set(value) - set(DEFAULTS[section])
            if unknown:
                raise ConfigError(f"Unknown key under `{section}`: {', '.join(sorted(unknown))}")

    _reject_unknown_nested(raw)
    thresholds = raw.get("thresholds")
    if isinstance(thresholds, dict):
        # `by_layer` bir metrik değil, katman → metrik sözlüğüdür.
        by_layer = thresholds.get("by_layer")
        if by_layer is not None:
            if not isinstance(by_layer, dict):
                raise ConfigError("`thresholds.by_layer` must be a mapping of layer names")
            for layer, metrics in by_layer.items():
                if not isinstance(metrics, dict):
                    raise ConfigError(f"`thresholds.by_layer.{layer}` must be a mapping")
                for metric, spec in metrics.items():
                    if not isinstance(spec, dict):
                        raise ConfigError(
                            f"`thresholds.by_layer.{layer}.{metric}` must be a mapping"
                        )
                    unknown = set(spec) - set(_THRESHOLD_KEYS)
                    if unknown:
                        raise ConfigError(
                            f"Unknown key under `thresholds.by_layer.{layer}.{metric}`: "
                            f"{', '.join(sorted(unknown))}"
                        )

        for metric, spec in thresholds.items():
            if metric == "by_layer":
                continue
            if not isinstance(spec, dict):
                raise ConfigError(f"`thresholds.{metric}` must be a mapping (e.g. {{warn: 10}})")
            unknown = set(spec) - set(_THRESHOLD_KEYS)
            if unknown:
                raise ConfigError(
                    f"Unknown key under `thresholds.{metric}`: {', '.join(sorted(unknown))}"
                )


# --------------------------------------------------------------------------- #
# Doğrulama + inşa
# --------------------------------------------------------------------------- #


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def _as_int(value: Any, label: str, *, minimum: int = 1) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool), f"`{label}` must be an integer"
    )
    _require(value >= minimum, f"`{label}` must be at least {minimum} (got: {value})")
    return int(value)


def _as_float(value: Any, label: str, *, low: float, high: float) -> float:
    _require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"`{label}` must be a number",
    )
    _require(low <= value <= high, f"`{label}` must be between {low} and {high} (got: {value})")
    return float(value)


def _as_str_list(value: Any, label: str) -> tuple[str, ...]:
    _require(isinstance(value, list), f"`{label}` must be a list")
    _require(all(isinstance(item, str) for item in value), f"`{label}` must contain only strings")
    return tuple(value)


def _build(data: dict[str, Any], source: Path | None) -> Config:
    provider_raw = data["provider"]
    name = provider_raw["name"]
    _require(
        name in KNOWN_PROVIDERS,
        f"Unknown provider: {name}. Known providers: {', '.join(KNOWN_PROVIDERS)}",
    )
    model = provider_raw["model"]
    _require(model is None or isinstance(model, str), "`provider.model` must be a string or empty")
    base_url = provider_raw["base_url"]
    _require(
        base_url is None or isinstance(base_url, str),
        "`provider.base_url` must be a string or empty",
    )
    provider = ProviderConfig(
        name=name,
        model=model,
        base_url=base_url,
        timeout_seconds=_as_int(provider_raw["timeout_seconds"], "provider.timeout_seconds"),
        max_retries=_as_int(provider_raw["max_retries"], "provider.max_retries", minimum=0),
    )

    scan_raw = data["scan"]
    _require(isinstance(scan_raw["output_dir"], str), "`scan.output_dir` must be a string")
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
        if metric == "by_layer":
            continue
        thresholds[metric] = _threshold(spec, f"thresholds.{metric}")

    arch = _build_arch(data["arch"])

    by_layer: dict[str, dict[str, Threshold]] = {}
    for layer, metrics_spec in data["thresholds"].get("by_layer", {}).items():
        _require(
            layer in arch.scheme.layers,
            f"`thresholds.by_layer.{layer}`: unknown layer. "
            f"Declared layers: {', '.join(arch.scheme.layers)}",
        )
        by_layer[layer] = {
            metric: _threshold(spec, f"thresholds.by_layer.{layer}.{metric}")
            for metric, spec in metrics_spec.items()
        }

    smells_raw = data["smells"]
    smells = SmellsConfig(
        god_class_nom=_as_int(smells_raw["god_class"]["nom"], "smells.god_class.nom"),
        god_class_wmc=_as_int(smells_raw["god_class"]["wmc"], "smells.god_class.wmc"),
        god_class_lcom4=_as_int(smells_raw["god_class"]["lcom4"], "smells.god_class.lcom4"),
        data_class_max_nom=_as_int(
            smells_raw["data_class"]["max_nom"], "smells.data_class.max_nom"
        ),
        data_class_min_dam=_as_float(
            smells_raw["data_class"]["min_dam"], "smells.data_class.min_dam", low=0.0, high=1.0
        ),
        data_class_accessor_ratio=_as_float(
            smells_raw["data_class"]["accessor_ratio"],
            "smells.data_class.accessor_ratio",
            low=0.0,
            high=1.0,
        ),
        feature_envy_ratio=_as_float(
            smells_raw["feature_envy"]["ratio"], "smells.feature_envy.ratio", low=1.0, high=100.0
        ),
        feature_envy_min_accesses=_as_int(
            smells_raw["feature_envy"]["min_accesses"],
            "smells.feature_envy.min_accesses",
            minimum=2,
        ),
        long_method_loc=_as_int(smells_raw["long_method"]["loc"], "smells.long_method.loc"),
    )

    budget_raw = data["budget"]
    budget = BudgetConfig(
        max_calls_per_run=_as_int(budget_raw["max_calls_per_run"], "budget.max_calls_per_run"),
        max_tokens_per_call=_as_int(
            budget_raw["max_tokens_per_call"], "budget.max_tokens_per_call", minimum=100
        ),
    )

    cache_raw = data["cache"]
    _require(isinstance(cache_raw["enabled"], bool), "`cache.enabled` must be true or false")
    _require(isinstance(cache_raw["dir"], str), "`cache.dir` must be a string")
    cache = CacheConfig(enabled=cache_raw["enabled"], directory=cache_raw["dir"])

    verify_raw = data["verify"]
    _require(
        isinstance(verify_raw["treat_suspicious_as_regression"], bool),
        "`verify.treat_suspicious_as_regression` must be true or false",
    )
    verify = VerifyConfig(
        treat_suspicious_as_regression=verify_raw["treat_suspicious_as_regression"]
    )

    return Config(
        provider=provider,
        scan=scan,
        advise=advise,
        metrics=metrics,
        thresholds=thresholds,
        by_layer_thresholds=by_layer,
        arch=arch,
        smells=smells,
        budget=budget,
        cache=cache,
        verify=verify,
        source_path=source,
    )


def _threshold(spec: Any, label: str) -> Threshold:
    """Tek bir eşik tanımını doğrular. Genel ve katman bazlı eşikler aynı kurala uyar."""
    _require(isinstance(spec, dict), f"`{label}` must be a mapping")
    _require("warn" in spec, f"`{label}` requires `warn`")
    warn = _as_float(spec["warn"], f"{label}.warn", low=0.0, high=1e9)
    critical: float | None = None
    if spec.get("critical") is not None:
        critical = _as_float(spec["critical"], f"{label}.critical", low=0.0, high=1e9)
        _require(
            critical > warn,
            f"`{label}`: critical ({critical}) must be greater than warn ({warn})",
        )
    return Threshold(warn=warn, critical=critical)


def _build_arch(raw: dict[str, Any]) -> ArchConfig:
    """Katman şemasını kurar ve iç tutarlılığını doğrular.

    Katman adları üç ayrı yerde geçer: şema, izin tablosu ve beyan. Birinde
    yazım hatası olursa katman sessizce `unknown` olur ve ihlaller kaybolur —
    bu yüzden hepsi birbirine karşı doğrulanır.
    """
    _require(isinstance(raw["enabled"], bool), "`arch.enabled` must be true or false")

    scheme_raw = raw["scheme"]
    layers = _as_str_list(scheme_raw["layers"], "arch.scheme.layers")
    _require(len(layers) == len(set(layers)), "`arch.scheme.layers` must not repeat a name")
    _require(bool(layers), "`arch.scheme.layers` must not be empty")

    allowed_raw = scheme_raw["allowed"]
    _require(isinstance(allowed_raw, dict), "`arch.scheme.allowed` must be a mapping")
    allowed: dict[str, tuple[str, ...]] = {}
    for source_layer, destinations in allowed_raw.items():
        _require(
            source_layer in layers,
            f"`arch.scheme.allowed.{source_layer}`: not in arch.scheme.layers",
        )
        targets = _as_str_list(destinations, f"arch.scheme.allowed.{source_layer}")
        for target in targets:
            _require(
                target in layers,
                f"`arch.scheme.allowed.{source_layer}`: unknown layer {target!r}",
            )
        allowed[source_layer] = targets

    _require(
        isinstance(scheme_raw["allow_skip"], bool),
        "`arch.scheme.allow_skip` must be true or false",
    )
    scheme = SchemeConfig(layers=layers, allowed=allowed, allow_skip=scheme_raw["allow_skip"])

    declared_raw = raw["layers"]
    _require(isinstance(declared_raw, dict), "`arch.layers` must be a mapping")
    declared: dict[str, tuple[str, ...]] = {}
    for layer, paths in declared_raw.items():
        _require(layer in layers, f"`arch.layers.{layer}`: not in arch.scheme.layers")
        declared[layer] = _as_str_list(paths, f"arch.layers.{layer}")

    conventions = raw["conventions"]
    extra_dirs = _layer_map(conventions["extra_dirs"], layers, "arch.conventions.extra_dirs")
    extra_suffixes = _layer_map(
        conventions["extra_suffixes"], layers, "arch.conventions.extra_suffixes"
    )

    return ArchConfig(
        enabled=raw["enabled"],
        scheme=scheme,
        declared=declared,
        extra_dirs=extra_dirs,
        extra_suffixes=extra_suffixes,
        min_confidence=_as_float(raw["min_confidence"], "arch.min_confidence", low=0.0, high=1.0),
    )


def _layer_map(raw: Any, layers: tuple[str, ...], label: str) -> dict[str, tuple[str, ...]]:
    _require(isinstance(raw, dict), f"`{label}` must be a mapping")
    result: dict[str, tuple[str, ...]] = {}
    for layer, values in raw.items():
        _require(layer in layers, f"`{label}.{layer}`: not in arch.scheme.layers")
        result[layer] = _as_str_list(values, f"{label}.{layer}")
    return result
