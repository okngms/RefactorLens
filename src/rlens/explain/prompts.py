"""`explain` prompt'u ve çıktı şeması.

`advise`'dan ayrı bir dosyadır ve bu ayrım bilinçlidir: deney protokolü
sürerken `advise/prompts.py` değişmez (`docs/v2-duzeltme-asama5.md`). Yorum
katmanını oraya bir mod olarak eklemek o dosyaya dokunmak olurdu.

Üç kural burada korunur:

* **Ham eşik sayıları prompt'a girmez.** `advise`'daki beyaz liste aynen
  kullanılır — kara liste değil, çünkü yeni bir kokunun varsayılan davranışı
  *sızdırmamak* olmalıdır. Eşikler bir kez `dcc_threshold` üzerinden tam
  böyle sızmıştı.
* **Derecelendirme yok.** "İyi", "kötü", "yüksek" gibi sıfatlar persentil
  ölçümüne dayanır ve o ölçüm henüz yapılmadı (`docs/v2-sertlestirme.md`
  Blok 1). `wmc: 50` eşiği Java'dan kalibre; ona dayanarak "yüksek" demek
  uydurma olur.
* **Öneri yok.** Teşhis ve öneri ayrıldığı için bu komut refactoring tarif
  etmez; o iş `advise`'da kalır.
"""

from __future__ import annotations

import json

from rlens.advise.prompts import EVIDENCE_KEYS, VALID_METRICS

#: Hesaplanamayan metriğin prompt'taki gösterimi. Sayı **uydurulmaz**: `0`
#: yazmak, modele gürültüyü kanıt kılığında vermek olurdu.
NOT_COMPUTED = "not computed"

SYSTEM_INSTRUCTION = """\
You are a Python static-analysis reader. You are given object-oriented design \
metrics measured from a code base. Your job is to say what those measurements \
describe — nothing more.

Rules you must follow:

1. Ground every statement in the measurements. Each statement must name at \
least one metric it rests on. Do not say anything the numbers do not support.
2. Do not restate the table. The reader already has every number. A finding \
must either rest on **two or more metrics** that point at the same structure, \
or span **two or more subjects** that share a pattern. "This class has 3 \
methods (NOM=3) and complexity 3 (WMC=3)" is the table, not a finding.
3. Describe, do not grade. Do not call a value high, low, limited, fragmented, \
moderate, poor, good, bad, healthy or concerning. You have not been told what \
counts as high, and the thresholds in use were calibrated for another language.
   Not this: "LCOM4=4 indicates low cohesion."
   This: "LCOM4=4 means its methods fall into four groups that share no \
attribute; DCC=0 means none of that is explained by outside collaborators."
4. Do not suggest changes. No refactoring advice, no "consider extracting", no \
priorities. Report what is measured; the reader decides what to do.
5. A metric reported as "not computed" was not computable. Never treat it as \
zero, and never describe it as low.
6. Say what the measurements cannot show. Metrics see class and function \
structure; logic in module-level functions is outside their reach.
7. Reply with a single JSON object and nothing else. No prose before or after, \
no markdown fences.
"""

_METRIC_GLOSSARY = {
    "NOM": "number of methods (dunders excluded)",
    "WMC": "sum of cyclomatic complexity over those methods",
    "LCOM4": "connected components in the method-attribute graph; 1 is cohesive",
    "DAM": "ratio of private attributes; 0.0 means none are private, 1.0 means all are",
    "DCC": "number of distinct project-internal classes referenced",
    "CAM": "cohesion among methods by parameter type, 0..1",
}


def output_schema() -> dict:
    """Modelden istenen JSON yapısı, örnek değerlerle.

    `metric_link` zorunludur ama doğrulaması sert değildir: bağlanmamış bir
    gözlem **silinmez**, `unlinked` etiketiyle raporda kalır. Silmek, modelin
    sözleşmeyi ne sıklıkla göz ardı ettiğini ölçülemez yapardı.
    """
    return {
        "summary": "One paragraph on what the measurements, taken together, describe.",
        "findings": [
            {
                "statement": (
                    "What two or more measurements jointly describe, "
                    "or what several subjects have in common."
                ),
                "subjects": ["module:Name", "module:Other"],
                "metric_link": ["LCOM4", "DCC"],
            }
        ],
        "not_shown": "What these measurements cannot see.",
    }


def format_metrics(metrics: dict) -> str:
    """Bir sınıfın ölçümlerini prompt satırına çevirir.

    `None` değerler `not computed` olarak basılır; sayıya çevrilmez.
    """
    parts = []
    for name in VALID_METRICS:
        if name not in metrics:
            continue
        value = metrics[name]
        parts.append(f"{name}={NOT_COMPUTED if value is None else value}")
    return ", ".join(parts)


def format_smell(label: str, evidence: dict) -> str:
    """Koku etiketini kanıtıyla biçimlendirir; eşikleri **basmaz**.

    Beyaz liste `advise` tarafından ödünç alınır. İki komutun aynı listeyi
    paylaşması kasıtlı: yeni bir koku eklendiğinde tek bir yerde izin verilir
    ve ikisi birden korunur.
    """
    fields = ", ".join(
        f"{key}={value}"
        for key, value in evidence.items()
        if key in EVIDENCE_KEYS and not isinstance(value, (dict, list))
    )
    return f"{label} ({fields})" if fields else label


def rank_classes(pairs: list[tuple[dict, dict]]) -> list[tuple[dict, dict]]:
    """Sınıfları prompt'a girme önceliğine göre sıralar.

    Kesme yapılacaksa **hangi** sınıfların düştüğü önemlidir. İlk koşuda kesme
    dosya sırasına göreydi: `examples/` alfabetik olarak `src/`ten önce geldiği
    için modele yalnızca fikstürler gitti ve araç kullanıcıya kendi test
    verisini anlattı.

    Sıralama `advise`ın hedef seçimiyle aynı mantığı izler: önce kokusu olan
    sınıflar, sonra gövdesi büyük olanlar.
    """
    return sorted(
        pairs,
        key=lambda pair: (-len(pair[1].get("smells") or []), -(pair[1].get("wmc") or 0)),
    )


def build_user_prompt(report: dict, *, max_classes: int = 25) -> str:
    """Tarama raporundan kullanıcı bloğunu kurar.

    Sınıf sayısı sınırlıdır: büyük bir kod tabanının tamamı bağlam penceresine
    sığmaz ve sığsa bile model her sınıf için tek cümle üreterek tabloyu
    tekrarlar. Kesme yapıldığında bu **prompt'ta söylenir**, yoksa model
    görmediği sınıflar hakkında da konuşmadığını bilmez.
    """
    lines: list[str] = []
    modules = report.get("modules", [])
    classes = [(m, c) for m in modules for c in m.get("classes", [])]

    lines.append("## Project")
    lines.append(f"root: {report.get('root', 'unknown')}")
    lines.append(f"{len(modules)} modules, {len(classes)} classes")

    shown = rank_classes(classes)[:max_classes]
    if len(classes) > len(shown):
        lines.append(
            f"(showing {len(shown)} of {len(classes)} classes, those carrying smells or "
            f"the largest bodies; the rest were omitted)"
        )

    lines.append("")
    lines.append("## Class measurements")
    for module, cls in shown:
        metrics = {
            "NOM": cls.get("nom"),
            "WMC": cls.get("wmc"),
            "LCOM4": cls.get("lcom4"),
            "DAM": cls.get("dam"),
            "DCC": cls.get("dcc"),
            "CAM": cls.get("cam"),
        }
        lines.append(f"- {module.get('module')}:{cls.get('name')} — {format_metrics(metrics)}")
        reason = cls.get("cam_skipped_reason")
        if reason:
            lines.append(f"    CAM not computed: {reason}")
        for smell in cls.get("smells", []):
            lines.append(f"    smell: {format_smell(smell['label'], smell.get('evidence', {}))}")

    violations = report.get("violations", [])
    if violations:
        lines.append("")
        lines.append("## Architectural violations")
        for violation in violations:
            tentative = " (tentative)" if violation.get("tentative") else ""
            lines.append(
                f"- {violation.get('code')} {violation.get('source')} → "
                f"{violation.get('target')}{tentative}"
            )

    lines.append("")
    lines.append("## Metric definitions")
    for name, gloss in _METRIC_GLOSSARY.items():
        lines.append(f"- {name}: {gloss}")

    lines.append("")
    lines.append("Reply with this JSON object:")
    lines.append(json.dumps(output_schema(), indent=2))
    return "\n".join(lines)
