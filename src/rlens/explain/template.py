"""`explain --no-llm`: ölçümleri insan diline çeviren şablon katmanı.

`docs/v2.1-explain.md` Blok 2. Bu bir **çeviri** katmanıdır, yorum değil:
raporda yazan sayıyı ve tanımını söyler, ötesine geçmez. API çağrısı yok,
çıktı deterministik.

Üç kural:

* **Derecelendirme yok.** "yüksek", "düşük", "iyi" gibi sıfatlar kullanılmaz
  (`explainer.GRADED_TERMS`); eşikler Python korpusunda kalibre edildi ama bir
  sayının "kötü" olduğu iddiası kalibrasyonun söylediği şey değildir.
* **`null` "0" değildir.** Hesaplanamayan metrik cümleye girmez; nedeniyle
  birlikte ayrı listelenir.
* **Prompt'a bağlanmaz.** Eşik sayıları burada insana gösterilir (terminal zaten
  `[WARN]` basıyor). Bu modülün çıktısı hiçbir yoldan modele gitmez; prompt
  modülleri bu modülü import etmez (testle sabit). Eşikler bir kez bir kokunun
  kanıt alanı üzerinden sızmıştı.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from rlens.config import Config

#: Metrik tanımları: yalnızca neyin sayıldığı, yorum yok.
DEFINITIONS = {
    "NOM": "the number of methods defined on the class, dunders excluded",
    "WMC": "the sum of cyclomatic complexity over those methods",
    "LCOM4": "the number of method groups that share no attribute and do not call one another",
    "DCC": "the number of distinct project classes this class refers to",
    "CC": "one plus the number of branch points in the function",
    "PARAMS": "the number of parameters, the receiver excluded",
    "NESTING": "the deepest block nesting in the function",
}

#: (rapor alanı, gösterim adı, config anahtarı) — sınıf ve fonksiyon eşikleri.
CLASS_THRESHOLDS = (
    ("nom", "NOM", "nom"),
    ("wmc", "WMC", "wmc"),
    ("lcom4", "LCOM4", "lcom4"),
    ("dcc", "DCC", "dcc"),
)
FUNCTION_THRESHOLDS = (
    ("cyclomatic_complexity", "CC", "cyclomatic_complexity"),
    ("param_count", "PARAMS", "max_params"),
    ("max_nesting", "NESTING", "max_nesting"),
)

_CAM_REASONS = {
    "insufficient_annotations": "annotation coverage below threshold",
    "no_annotated_parameters": "no annotated parameters",
}
_LEVEL_WORDS = {"warn": "warning", "critical": "critical"}


@dataclass(frozen=True)
class Sentence:
    subject: str
    kind: str
    """"threshold" ya da "smell"."""
    metrics: tuple[str, ...]
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "kind": self.kind,
            "metrics": list(self.metrics),
            "text": self.text,
        }


@dataclass(frozen=True)
class TemplateReading:
    summary: tuple[str, ...]
    sentences: tuple[Sentence, ...]
    not_computed: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": list(self.summary),
            "sentences": [sentence.to_dict() for sentence in self.sentences],
            "not_computed": list(self.not_computed),
        }


# --------------------------------------------------------------------------- #
# Biçim yardımcıları
# --------------------------------------------------------------------------- #


def _num(value: Any) -> str:
    if isinstance(value, float):
        return f"{round(value, 2):g}"
    return str(value)


def _count(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


# --------------------------------------------------------------------------- #
# Koku kalıpları — her biri kanıt alanlarını çevirir
# --------------------------------------------------------------------------- #


def _god_class(target: str, e: dict) -> str:
    t = e.get("thresholds", {})
    return (
        f"{target} is flagged god_class: NOM {_num(e['nom'])} (threshold {_num(t['nom'])}), "
        f"WMC {_num(e['wmc'])} (threshold {_num(t['wmc'])}) and LCOM4 {_num(e['lcom4'])} "
        f"(threshold {_num(t['lcom4'])}) all meet their limits."
    )


def _data_class(target: str, e: dict) -> str:
    accessors = ", ".join(e.get("accessors", []))
    return (
        f"{target} is flagged data_class: {_count(e['nom'], 'method', 'methods')}, "
        f"WMC {_num(e['wmc'])}, DAM {_num(e['dam'])}, and {e['accessor_ratio']:.0%} of its "
        f"public methods are accessors ({accessors}). An LCOM4 of {_num(e['lcom4'])} is "
        "expected here: accessors of different fields share no state."
    )


def _feature_envy(target: str, e: dict) -> str:
    t = e.get("thresholds", {})
    return (
        f"{target} touches {e['envied']} {_count(e['accesses_to_other'], 'time', 'times')} "
        f"and its own class {_count(e['accesses_to_self'], 'time', 'times')} "
        f"(ratio {_num(e['ratio'])}, threshold {_num(t['ratio'])})."
    )


def _long_method(target: str, e: dict) -> str:
    t = e.get("thresholds", {})
    return (
        f"{target} is flagged long_method: CC {_num(e['cc'])} (threshold {_num(t['cc'])}) "
        f"and {_num(e['loc'])} lines of code (threshold {_num(t['loc'])})."
    )


def _too_many_params(target: str, e: dict) -> str:
    t = e.get("thresholds", {})
    return f"{target} takes {_num(e['params'])} parameters (threshold {_num(t['params'])})."


def _layer_misfit(target: str, e: dict) -> str:
    t = e.get("thresholds", {})
    return (
        f"{target} sits in the {e['layer']} layer, its module breaks a layer rule, and its "
        f"DCC is {_num(e['dcc'])} (threshold for this layer {_num(t['dcc'])})."
    )


#: Koku etiketi → (kalıp, ilgili metrikler).
SMELL_TEMPLATES: dict[str, tuple[Callable[[str, dict], str], tuple[str, ...]]] = {
    "god_class": (_god_class, ("NOM", "WMC", "LCOM4")),
    "data_class": (_data_class, ("NOM", "WMC", "DAM", "LCOM4")),
    "feature_envy_candidate": (_feature_envy, ()),
    "long_method": (_long_method, ("CC", "LOC")),
    "too_many_params": (_too_many_params, ("PARAMS",)),
    "layer_misfit": (_layer_misfit, ("DCC",)),
}


def _smell_sentence(smell: dict) -> Sentence:
    label = smell["label"]
    target = smell["target"]
    template = SMELL_TEMPLATES.get(label)
    if template is None:
        return Sentence(target, "smell", (), f"{target} is flagged {label}.")
    render, metrics = template
    return Sentence(target, "smell", metrics, render(target, smell.get("evidence", {})))


# --------------------------------------------------------------------------- #
# Eşik bulguları
# --------------------------------------------------------------------------- #


def _threshold_sentence(subject: str, label: str, value: Any, threshold, extra: str = ""):
    level = threshold.level(value)
    if level is None:
        return None
    limit = threshold.critical if level == "critical" else threshold.warn
    text = (
        f"{subject}: {label} is {_num(value)}, at or above the {_LEVEL_WORDS[level]} "
        f"threshold ({_num(limit)}). {label} is {DEFINITIONS[label]}.{extra}"
    )
    return Sentence(subject, "threshold", (label,), text)


def _function_sentences(subject: str, function: dict, config: Config) -> list[Sentence]:
    found = []
    for field_name, label, key in FUNCTION_THRESHOLDS:
        threshold = config.thresholds.get(key)
        if threshold is None or function.get(field_name) is None:
            continue
        extra = ""
        if label == "PARAMS" and function.get("entry_point"):
            extra = (
                f" It is a {function['entry_point']} entry point, so the parameters are its "
                "interface and no too_many_params is reported."
            )
        sentence = _threshold_sentence(subject, label, function[field_name], threshold, extra)
        if sentence:
            found.append(sentence)
    return found


# --------------------------------------------------------------------------- #
# Çeviri
# --------------------------------------------------------------------------- #


def _collect_sentences(modules, config):
    """Modül, fonksiyon, sınıf ve metotları gezer; cümleleri ve sayaçları döndürür."""
    sentences: list[Sentence] = []
    smell_counts: Counter[str] = Counter()
    nulls: Counter[str] = Counter()
    cam_reasons: Counter[str] = Counter()
    classes = functions = 0

    for module in modules:
        name = module["module"]
        for function in module.get("functions", []):
            functions += 1
            sentences += _function_sentences(f"{name}.{function['name']}", function, config)
        for smell in module.get("smells", []):
            smell_counts[smell["label"]] += 1
            sentences.append(_smell_sentence(smell))
        for cls in module.get("classes", []):
            classes += 1
            subject = f"{cls['module']}:{cls['name']}"
            for field_name, label, key in CLASS_THRESHOLDS:
                value = cls.get(field_name)
                if value is None:
                    nulls[label] += 1
                    continue
                threshold = config.threshold_for(key, cls.get("layer"))
                if threshold is None:
                    continue
                sentence = _threshold_sentence(subject, label, value, threshold)
                if sentence:
                    sentences.append(sentence)
            if cls.get("dam") is None:
                nulls["DAM"] += 1
            if cls.get("cam") is None:
                cam_reasons[cls.get("cam_skipped_reason") or "unknown"] += 1
            for method in cls.get("methods", []):
                functions += 1
                method_subject = f"{subject}.{method['name']}"
                sentences += _function_sentences(method_subject, method, config)
            for smell in cls.get("smells", []):
                smell_counts[smell["label"]] += 1
                sentences.append(_smell_sentence(smell))
    return sentences, smell_counts, nulls, cam_reasons, classes, functions


def _build_summary(modules, classes, functions, findings, smell_counts, payload):
    """Proje düzeyi iki özet satırı."""
    breakdown = ", ".join(f"{label} {count}" for label, count in sorted(smell_counts.items()))
    summary = [
        f"{_count(len(modules), 'module', 'modules')}, {_count(classes, 'class', 'classes')} "
        f"and {_count(functions, 'function or method', 'functions and methods')} measured "
        f"(scan schema {payload.get('schema_version')}, rlens {payload.get('rlens_version')}).",
        f"{_count(findings, 'threshold finding', 'threshold findings')} and "
        f"{_count(sum(smell_counts.values()), 'smell', 'smells')}"
        + (f": {breakdown}." if breakdown else "."),
    ]
    return summary


def _build_not_computed(nulls, cam_reasons):
    """Hesaplanamayan metrikler, nedenleriyle."""
    not_computed = []
    reasons = {"LCOM4": "no methods", "DCC": "not resolvable", "DAM": "no attributes"}
    for label in ("LCOM4", "DCC", "DAM"):
        if nulls[label]:
            not_computed.append(
                f"{label} was not computed for {_count(nulls[label], 'class', 'classes')} "
                f"({reasons[label]})."
            )
    for reason, count in sorted(cam_reasons.items()):
        not_computed.append(
            f"CAM was not computed for {_count(count, 'class', 'classes')} "
            f"({_CAM_REASONS.get(reason, reason)})."
        )
    for label in ("NOM", "WMC"):
        if nulls[label]:
            not_computed.append(
                f"{label} was not computed for {_count(nulls[label], 'class', 'classes')}."
            )
    return not_computed


def translate(payload: dict, config: Config) -> TemplateReading:
    """Bir tarama raporunu (sözlük) şablon cümlelerine çevirir."""
    modules = payload.get("modules", [])
    sentences, smell_counts, nulls, cam_reasons, classes, functions = _collect_sentences(
        modules, config
    )
    order = {"threshold": 0, "smell": 1}
    sentences.sort(key=lambda s: (s.subject, order[s.kind], s.text))
    findings = sum(1 for s in sentences if s.kind == "threshold")
    summary = _build_summary(modules, classes, functions, findings, smell_counts, payload)
    not_computed = _build_not_computed(nulls, cam_reasons)
    return TemplateReading(tuple(summary), tuple(sentences), tuple(not_computed))
