"""Metriklerden türetilen koku etiketleri.

**LLM kullanılmaz.** Kurallar literatür eşiklerinden uyarlanmıştır (Lanza &
Marinescu deseni: birden fazla metriğin birlikte eşik aşması) ve config ile
değiştirilebilir.

**Neden etiket?** Modele `DCC=8` demek bir sayı vermektir; `god_class adayı`
demek bir durum vermektir. v1 bulgusu modellerin metriği yanlış kapsamda
düşündüğünü gösterdi; etiket bu boşluğu doldurmayı hedefler.

**Neden `data_class` var?** v1'de LCOM4'ün veri taşıyıcı sınıfları
cezalandırdığı belgelendi: `Customer` için LCOM4=4 çıkıyor, oysa sınıf temiz.
Etiket bu yanlış pozitifi nötrler — sayı değişmez, **yorumu** değişir.

Her etiket `evidence` taşır: hangi metrik, hangi eşik. Gerekçesiz etiket,
kullanıcının doğrulayamayacağı bir iddiadır.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from rlens.analysis.class_metrics import class_methods
from rlens.analysis.interface import public_interface
from rlens.analysis.model import ClassReport, FunctionReport
from rlens.config import Config, SmellsConfig

GOD_CLASS = "god_class"
DATA_CLASS = "data_class"
FEATURE_ENVY = "feature_envy_candidate"
LONG_METHOD = "long_method"
TOO_MANY_PARAMS = "too_many_params"
LAYER_MISFIT = "layer_misfit"

#: `layer_misfit` yalnızca katman ataması bu güvenin üstündeyse verilir.
MISFIT_MIN_CONFIDENCE = 0.7


@dataclass(frozen=True)
class Smell:
    """Bir koku etiketi ve gerekçesi."""

    label: str
    target: str
    evidence: dict[str, object] = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "target": self.target,
            "evidence": dict(self.evidence),
            "note": self.note,
        }


def _meets(value: float | None, threshold: float) -> bool:
    """`None` (hesaplanamadı) hiçbir eşiği karşılamaz."""
    return value is not None and value >= threshold


def detect_god_class(report: ClassReport, rules: SmellsConfig) -> Smell | None:
    """NOM, WMC ve LCOM4 **birlikte** eşiği aşarsa.

    Üç koşul birden aranır: tek başına yüksek NOM büyük ama düzenli bir sınıfı,
    tek başına yüksek LCOM4 ise bir veri taşıyıcısını yakalardı.
    """
    if not (
        _meets(report.nom, rules.god_class_nom)
        and _meets(report.wmc, rules.god_class_wmc)
        and _meets(report.lcom4, rules.god_class_lcom4)
    ):
        return None
    return Smell(
        label=GOD_CLASS,
        target=report.qualified_name,
        evidence={
            "nom": report.nom,
            "wmc": report.wmc,
            "lcom4": report.lcom4,
            "thresholds": {
                "nom": rules.god_class_nom,
                "wmc": rules.god_class_wmc,
                "lcom4": rules.god_class_lcom4,
            },
        },
        note="all three conditions hold; one high metric alone is not enough",
    )


def detect_data_class(node: ast.ClassDef, report: ClassReport, rules: SmellsConfig) -> Smell | None:
    """Küçük, basit, çoğunlukla erişimcilerden oluşan veri taşıyıcısı.

    Bu etiketin asıl işi LCOM4'ü **bağlama oturtmaktır**. FINDINGS-1'de
    belgelendiği gibi LCOM4, alan başına bir erişimcisi olan sınıfları
    kohezyonsuz gösterir. Sayı doğrudur; sorunu olduğu yorumu yanlıştır.
    """
    interface = public_interface(node)
    ratio = interface.accessor_ratio
    conditions = (
        report.nom is not None
        and report.nom <= rules.data_class_max_nom
        and report.wmc is not None
        and report.wmc <= report.nom + 2
        and _meets(report.dam, rules.data_class_min_dam)
        and ratio is not None
        and ratio >= rules.data_class_accessor_ratio
    )
    if not conditions:
        return None

    note = "a data holder; a high LCOM4 here is expected and not a defect"
    return Smell(
        label=DATA_CLASS,
        target=report.qualified_name,
        evidence={
            "nom": report.nom,
            "wmc": report.wmc,
            "dam": report.dam,
            "accessor_ratio": ratio,
            "accessors": list(interface.accessors),
            "lcom4": report.lcom4,
        },
        note=note,
    )


def _receiver(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    positional = node.args.posonlyargs + node.args.args
    return positional[0].arg if positional else None


def detect_feature_envy(node: ast.ClassDef, module: str, rules: SmellsConfig) -> list[Smell]:
    """Kendi durumundan çok başka **tek** bir nesnenin durumuna dokunan metot.

    İsim tabanlıdır, dolayısıyla her zaman `candidate`: `order.total` ifadesinin
    hangi sınıfa ait olduğunu tip bilgisi olmadan kesin bilemeyiz. Etiket bunu
    adında taşır.

    "Tek bir nesne" şartı önemlidir: üç farklı nesneye birer kez dokunan metot
    koordinasyon yapıyordur, kıskançlık değil.

    Asgari erişim sayısı da şarttır. Oran tek başına yetmez: `self`'e bir,
    parametreye iki kez dokunan beş satırlık bir metot oran testini geçer ama
    kıskanç değildir. Literatür kuralı (Lanza & Marinescu) "birkaç yabancı
    attribute" der; iki eşik birlikte çalışır.
    """
    found: list[Smell] = []
    for method in class_methods(node):
        receiver = _receiver(method)
        if receiver is None:
            continue

        own = 0
        others: dict[str, int] = {}
        for child in ast.walk(method):
            if not (isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name)):
                continue
            name = child.value.id
            if name == receiver:
                own += 1
            else:
                others[name] = others.get(name, 0) + 1

        if not others:
            continue
        target_name, count = max(others.items(), key=lambda item: (item[1], item[0]))
        if count < rules.feature_envy_min_accesses:
            continue
        ratio = count / max(own, 1)
        if ratio < rules.feature_envy_ratio:
            continue

        found.append(
            Smell(
                label=FEATURE_ENVY,
                target=f"{module}:{node.name}.{method.name}",
                evidence={
                    "envied": target_name,
                    "accesses_to_other": count,
                    "accesses_to_self": own,
                    "ratio": round(ratio, 2),
                    "thresholds": {
                        "ratio": rules.feature_envy_ratio,
                        "min_accesses": rules.feature_envy_min_accesses,
                    },
                },
                note="name-based; always a candidate, never a confirmed smell",
            )
        )
    return found


def detect_function_smells(report: FunctionReport, owner: str, config: Config) -> list[Smell]:
    """`long_method` ve `too_many_params`.

    `long_method` iki koşul ister: uzun **ve** dallanmalı. Uzun ama düz bir
    fonksiyon (uzun bir eşleme tablosu gibi) sorun değildir.
    """
    rules = config.smells
    found: list[Smell] = []
    complexity_threshold = config.thresholds.get("cyclomatic_complexity")
    params_threshold = config.thresholds.get("max_params")

    if (
        complexity_threshold is not None
        and _meets(report.cyclomatic_complexity, complexity_threshold.warn)
        and _meets(report.loc, rules.long_method_loc)
    ):
        found.append(
            Smell(
                label=LONG_METHOD,
                target=f"{owner}.{report.name}",
                evidence={
                    "cc": report.cyclomatic_complexity,
                    "loc": report.loc,
                    "thresholds": {
                        "cc": complexity_threshold.warn,
                        "loc": rules.long_method_loc,
                    },
                },
                note="long and branching; length alone is not the problem",
            )
        )

    if params_threshold is not None and _meets(report.param_count, params_threshold.warn):
        found.append(
            Smell(
                label=TOO_MANY_PARAMS,
                target=f"{owner}.{report.name}",
                evidence={
                    "params": report.param_count,
                    "threshold": params_threshold.warn,
                },
            )
        )
    return found


def detect_layer_misfit(
    report: ClassReport,
    layer: str | None,
    layer_confidence: float,
    violating_modules: set[str],
    config: Config,
) -> Smell | None:
    """Katmanına uymayan sınıf: hem ihlal kaynağı hem de kuplajı eşik üstü.

    İki koşul birden aranır. Tek başına ihlal modül düzeyi bir olgudur ve
    sınıfın kendisi masum olabilir; tek başına yüksek DCC ise bazı katmanlarda
    tasarım gereğidir.

    **Yalnızca güvenilir katman atamalarında.** Çıkarılmış ve düşük güvenli bir
    katmandan koku üretmek, tahmin üstüne tahmin kurmak olurdu.
    """
    if not layer or layer == "unknown" or layer_confidence < MISFIT_MIN_CONFIDENCE:
        return None
    if report.module not in violating_modules:
        return None

    threshold = config.threshold_for("dcc", layer)
    if threshold is None or not _meets(report.dcc, threshold.warn):
        return None

    return Smell(
        label=LAYER_MISFIT,
        target=report.qualified_name,
        evidence={
            "layer": layer,
            "dcc": report.dcc,
            "dcc_threshold": threshold.warn,
            "module_has_violation": True,
        },
        note="its module breaks a layer rule and its coupling is above the "
        "threshold for that layer",
    )


def detect_class_smells(
    node: ast.ClassDef,
    report: ClassReport,
    config: Config,
    *,
    layer: str | None = None,
    layer_confidence: float = 0.0,
    violating_modules: set[str] | None = None,
) -> list[Smell]:
    """Bir sınıfın tüm koku etiketleri, metotları dahil."""
    rules = config.smells
    found: list[Smell] = []

    god = detect_god_class(report, rules)
    if god:
        found.append(god)

    data = detect_data_class(node, report, rules)
    if data:
        found.append(data)

    found.extend(detect_feature_envy(node, report.module, rules))

    for method in report.methods:
        found.extend(detect_function_smells(method, report.qualified_name, config))

    misfit = detect_layer_misfit(
        report, layer, layer_confidence, violating_modules or set(), config
    )
    if misfit:
        found.append(misfit)

    return found
