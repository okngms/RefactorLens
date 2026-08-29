"""En sorunlu N hedefin seçimi.

`advise` her sınıfa bakmaz: bir LLM çağrısı hem yavaş hem maliyetlidir ve
sorunsuz koda öneri istemek gürültü üretir. Bu modül eşik ihlallerine göre bir
sıralama kurar ve yalnızca ilk N hedefi seçer.

**Kritik tasarım kararı: ham eşik sayıları buradan çıkmaz.** Hedefler yalnızca
ihlal *seviyesini* (`warn` / `critical`) taşır. Modelin "LCOM4'ü 2'nin altına
indir" gibi bir sayıyı bilmesi, tasarımı düzeltmek yerine sayıyı tatmin etmeyi
öğrenmesine yol açar — projenin uyardığı Goodhart tuzağı tam olarak budur.
Model neyin sorunlu olduğunu bilir, eşiğin kaç olduğunu bilmez.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rlens.analysis.model import ClassReport, FunctionReport, ProjectReport
from rlens.config import Config
from rlens.report.terminal import class_violations, function_violations

#: İhlal seviyelerinin puan ağırlıkları.
#: `critical` üç kat sayılır: bir metriği ciddi biçimde aşan sınıf, üç metriği
#: kıl payı aşandan daha acildir.
_LEVEL_WEIGHTS = {"warn": 1, "critical": 3}


@dataclass(frozen=True)
class AdviceTarget:
    """`advise` için seçilmiş tek bir hedef (sınıf veya modül düzeyi fonksiyon)."""

    kind: str
    """`"class"` veya `"function"`."""

    module: str
    name: str
    lineno: int

    violations: dict[str, str] = field(default_factory=dict)
    """Metrik adı → `"warn"` / `"critical"`. Eşik **sayıları** burada yoktur."""

    metrics: dict[str, float | int | None] = field(default_factory=dict)
    """Ölçülen değerler. `None` "hesaplanamadı" demektir."""

    score: int = 0

    @property
    def qualified_name(self) -> str:
        return f"{self.module}:{self.name}"

    @property
    def severity(self) -> str:
        """Hedefin en ağır ihlal seviyesi."""
        return "critical" if "critical" in self.violations.values() else "warn"


def score_violations(violations: dict[str, str]) -> int:
    """İhlal sözlüğünü tek bir aciliyet puanına indirger."""
    return sum(_LEVEL_WEIGHTS.get(level, 0) for level in violations.values())


def _class_metrics(report: ClassReport) -> dict[str, float | int | None]:
    return {
        "NOM": report.nom,
        "WMC": report.wmc,
        "LCOM4": report.lcom4,
        "DCC": report.dcc,
        "DAM": report.dam,
        "CAM": report.cam,
    }


def _function_metrics(report: FunctionReport) -> dict[str, float | int | None]:
    return {
        "CC": report.cyclomatic_complexity,
        "LOC": report.loc,
        "PARAMS": report.param_count,
        "NESTING": report.max_nesting,
    }


def _complexity_of(target: AdviceTarget) -> int:
    """Eşit puanlı hedefler arasında sıralama ölçütü."""
    value = target.metrics.get("WMC") if target.kind == "class" else target.metrics.get("CC")
    return int(value or 0)


def collect_targets(report: ProjectReport, config: Config) -> list[AdviceTarget]:
    """En az bir eşiği aşan tüm hedefler, puanlarıyla birlikte.

    Sınıflar ve modül düzeyi fonksiyonlar birlikte değerlendirilir. Metotlar
    ayrı hedef sayılmaz: bir metot sorunluysa, bağlamı sınıfıdır ve öneri sınıf
    üzerinden verilmelidir.
    """
    targets: list[AdviceTarget] = []

    for module in report.modules:
        for cls in module.classes:
            violations = class_violations(cls, config)
            if violations:
                targets.append(
                    AdviceTarget(
                        kind="class",
                        module=module.module,
                        name=cls.name,
                        lineno=cls.lineno,
                        violations=violations,
                        metrics=_class_metrics(cls),
                        score=score_violations(violations),
                    )
                )

        for fn in module.functions:
            violations = function_violations(fn, config)
            if violations:
                targets.append(
                    AdviceTarget(
                        kind="function",
                        module=module.module,
                        name=fn.name,
                        lineno=fn.lineno,
                        violations=violations,
                        metrics=_function_metrics(fn),
                        score=score_violations(violations),
                    )
                )

    return targets


def rank_targets(targets: list[AdviceTarget]) -> list[AdviceTarget]:
    """Hedefleri aciliyete göre sıralar.

    Sıra: puan (azalan) → karmaşıklık (azalan) → nitelikli ad (artan).

    Son ölçüt kararlılık içindir: aynı proje iki kez taranınca aynı hedefler
    aynı sırada seçilmelidir, yoksa iki `advise` çalıştırmasını karşılaştırmak
    imkânsızlaşır.
    """
    return sorted(
        targets,
        key=lambda t: (-t.score, -_complexity_of(t), t.qualified_name),
    )


def select_targets(
    report: ProjectReport,
    config: Config,
    top_n: int | None = None,
) -> list[AdviceTarget]:
    """En sorunlu ilk N hedefi döndürür.

    Args:
        report: Tamamlanmış tarama raporu.
        config: Eşikler ve `advise.top_n` buradan okunur.
        top_n: Config'i geçersiz kılan sınır (CLI bayrağı için).
    """
    limit = top_n if top_n is not None else config.advise.top_n
    return rank_targets(collect_targets(report, config))[:limit]
