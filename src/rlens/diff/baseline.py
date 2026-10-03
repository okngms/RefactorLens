"""Bulgular ve baseline dosyası: ratchet'in kabul ettiği küme (`docs/02` §8).

Bir bulgu üç türden biridir; kimlikleri `verify` ile aynıdır:

* `violation <kod> <kaynak → hedef>` — mimari ihlal,
* `smell <etiket> @ <hedef>` — koku,
* `threshold <modül:Ad> <METRİK>` — eşik aşımı (sınıf: NOM, WMC, LCOM4, DCC;
  fonksiyon ve metot: CC, PARAMS, NESTING). Framework giriş noktasının
  parametre sayısı bulgu değildir (K6; `advise` ile aynı kural).

Baseline, mevcut bulguları kabul eder: ratchet yalnızca **yeni** bulguda CI'ı
kırar. Dosya projeyle birlikte commit'lenmek içindir.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from rlens import __version__
from rlens.config import Config
from rlens.verify.diff import smell_keys, violation_keys

BASELINE_FILE = ".rlens-baseline.json"
BASELINE_SCHEMA_VERSION = 1

_CLASS = {
    "nom": ("NOM", "nom"),
    "wmc": ("WMC", "wmc"),
    "lcom4": ("LCOM4", "lcom4"),
    "dcc": ("DCC", "dcc"),
}
_FUNCTION = {
    "cyclomatic_complexity": ("CC", "cyclomatic_complexity"),
    "param_count": ("PARAMS", "max_params"),
    "max_nesting": ("NESTING", "max_nesting"),
}


def _over(config: Config, key: str, value, layer: str | None) -> bool:
    threshold = config.threshold_for(key, layer)
    return value is not None and threshold is not None and threshold.level(value) is not None


def _function_findings(subject: str, function: dict, config: Config, layer) -> set[str]:
    found = set()
    for field, (label, key) in _FUNCTION.items():
        if field == "param_count" and function.get("entry_point"):
            continue
        if _over(config, key, function.get(field), layer):
            found.add(f"threshold {subject} {label}")
    return found


def findings(report: dict, config: Config) -> set[str]:
    """Bir tarama raporunun bütün bulguları."""
    found = {f"violation {key}" for key in violation_keys(report)}
    found |= {f"smell {key}" for key in smell_keys(report)}
    for module in report.get("modules", []):
        name = module["module"]
        for function in module.get("functions", []):
            subject = f"{name}:{function['name']}"
            found |= _function_findings(subject, function, config, module.get("layer"))
        for cls in module.get("classes", []):
            subject = f"{name}:{cls['name']}"
            for field, (label, key) in _CLASS.items():
                if _over(config, key, cls.get(field), cls.get("layer")):
                    found.add(f"threshold {subject} {label}")
            for method in cls.get("methods", []):
                method_subject = f"{subject}.{method['name']}"
                found |= _function_findings(method_subject, method, config, cls.get("layer"))
    return found


def write_baseline(directory: Path, accepted: set[str]) -> Path:
    path = Path(directory) / BASELINE_FILE
    payload = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "rlens_version": __version__,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "accepted": sorted(accepted),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_baseline(path: Path) -> set[str]:
    from rlens.apply.worktree import ApplyError

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ApplyError(f"Could not read the baseline {path}: {exc}") from exc
    if payload.get("schema_version") != BASELINE_SCHEMA_VERSION:
        raise ApplyError(
            f"{path} has baseline schema {payload.get('schema_version')}; this rlens reads "
            f"{BASELINE_SCHEMA_VERSION}. Regenerate it with `rlens baseline update`."
        )
    return set(payload.get("accepted", []))
