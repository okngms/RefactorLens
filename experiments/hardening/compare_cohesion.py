"""Kohezyon çapraz doğrulaması: LCOM4 ile `cohesion` aracı, sıralama korelasyonu.

Sertleştirme Blok 1, madde 2 (kohezyon). İki araç **aynı şeyi ölçmez**, bu
yüzden mutlak değer değil sıra karşılaştırılır:

    LCOM4 (bizde)   metot–attribute grafiğinin bağlantılı bileşen sayısı.
                    1 = tek parça; yüksek = kötü. Dunder metotlar hariç.
    cohesion 1.2.0  sum(metodun kullandığı sınıf değişkeni) /
                    (sınıf değişkeni sayısı × metot sayısı) × 100.
                    Yüksek = iyi. `__init__` dahil her `def` metottur.

Beklenti: **negatif** korelasyon (LCOM4 artarken cohesion yüzdesi düşer).
Korelasyonun büyüklüğü iki tanımın ne kadar örtüştüğünü söyler; tam örtüşme
beklenmez. Asıl değer, sıralamada en çok ayrışan sınıflardır — onlar elle
okunur ve sapma "tanım farkı" ya da "uygulama hatası" diye sınıflandırılır.

**Karşılaştırmaya giren sınıflar.** İki değer de tanımlı ve dejenere değilse:
LCOM4'te en az iki **farklı adlı** metot (tek metotlu sınıfın LCOM4'ü 1'dir, bir
şey ayırt etmez; property getter/setter aynı adı taşır ve LCOM4 grafiğinde tek
düğümdür, bu yüzden NOM değil ad sayılır) ve `cohesion`'da en az bir sınıf
değişkeni (yoksa araç 0.0 döndürür —
"hesaplanamaz" ile "sıfır kohezyon"u ayırmaz). Eşleşme dosya + sınıf adı +
satır numarasıyla yapılır; `cohesion` sınıfları modül içinde yalnızca adla
tuttuğu için aynı modülde aynı adlı sınıflar ezilir, bunlar ayrıca sayılır.

Kullanım (önce `compare_radon.py fetch`, `pip install cohesion==1.2.0`):

    python experiments/hardening/compare_cohesion.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from compare_radon import ALWAYS_EXCLUDED, HERE, load_projects

from rlens.analysis.class_metrics import (
    accessed_attributes,
    called_methods,
    class_methods,
    iter_module_classes,
    lcom4,
)
from rlens.analysis.parser import parse_project

RESULTS_FILE = HERE / "results" / "cohesion-spearman.json"

#: Elle incelenecek en çok ayrışan sınıf sayısı.
TOP_DEVIATIONS = 25

# Sapma kategorileri — hepsi iki tanımın bilinen farkları.
HUB_ATTRIBUTES = "hub_attributes"
ISOLATED_METHODS = "isolated_methods"
CALL_EDGES = "call_edges"
UNEXPLAINED = "unexplained"

#: Düşük yoğunluk sınırı (cohesion yüzdesi).
LOW_DENSITY = 25.0


@dataclass(frozen=True)
class Pair:
    project: str
    path: str
    name: str
    lineno: int
    lcom4: int
    cohesion: float
    category: str = UNEXPLAINED


def average_ranks(values: list[float]) -> list[float]:
    """Eşit değerlere ortalama sıra (1'den başlar) — Spearman'ın bağ kuralı."""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        shared = (position + end) / 2 + 1
        for index in order[position : end + 1]:
            ranks[index] = shared
        position = end + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman ρ: ortalama sıralar üzerinde Pearson. Varyans yoksa `None`."""
    if len(xs) != len(ys):
        raise ValueError("length mismatch")
    if len(xs) < 3:
        return None
    rx, ry = average_ranks(xs), average_ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx == 0 or vy == 0:
        return None
    return round(cov / (vx * vy) ** 0.5, 4)


def deviations(pairs: list[Pair]) -> list[tuple[float, Pair]]:
    """Sıralamada en çok ayrışan sınıflar.

    Her iki ölçüyü "kötülük" yönüne çevirip yüzdelik sıraya dönüştürür (LCOM4
    yüksek = kötü; cohesion düşük = kötü) ve farkın mutlak değerine göre sıralar.
    """
    if not pairs:
        return []
    n = len(pairs)
    bad_lcom = average_ranks([float(p.lcom4) for p in pairs])
    bad_coh = average_ranks([-p.cohesion for p in pairs])
    scored = [(round(abs(bad_lcom[i] - bad_coh[i]) / n, 4), pairs[i]) for i in range(n)]
    return sorted(
        scored, key=lambda item: (-item[0], item[1].project, item[1].path, item[1].lineno)
    )


def attribute_components(node) -> int:
    """LCOM4'ün grafiği, **yalnızca attribute kenarlarıyla** (çağrılar hariç).

    LCOM4 iki metodu ortak attribute ya da doğrudan çağrı ile bağlar. Bu fonksiyon
    çağrıları çıkarır: sonuç LCOM4'ten büyükse, sınıfı bir arada tutan
    attribute'lar değil metot çağrılarıdır.
    """
    methods = class_methods(node)
    known = {method.name for method in methods}
    parent = {name: name for name in known}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    owners: dict[str, list[str]] = {}
    for method in methods:
        for attribute in accessed_attributes(method, known):
            owners.setdefault(attribute, []).append(method.name)
    for names in owners.values():
        for name in names[1:]:
            parent[find(name)] = find(names[0])
    return len({find(name) for name in known})


def explain(node, pair_lcom4: int, cohesion_value: float) -> str:
    """Bir sapmanın hangi tanım farkından geldiği; bulunamazsa `unexplained`.

    * `isolated_methods` — LCOM4 > 1 ve hiçbir attribute'a dokunmayan, hiçbir
      metodu çağırmayan ve çağrılmayan metotlar var. LCOM4'te her biri ayrı
      bileşendir; `cohesion` onları yalnızca yoğunluğu düşüren metotlar sayar.
    * `call_edges` — LCOM4 = 1, yoğunluk düşük ve **çağrılar çıkarılınca sınıf
      dağılıyor** (`attribute_components` > 1). Ortak bir yardımcı metot her
      metodu bağlıyor; `cohesion` çağrıları hiç görmez.
    * `hub_attributes` — LCOM4 = 1, yoğunluk düşük, çağrılar olmadan da tek
      parça: birkaç ortak attribute her metodu birleştirir.

    Kategori bir gözleme dayanır, varsayıma değil: `call_edges` ile
    `hub_attributes` ayrımı grafiğin çağrısız hâli ölçülerek yapılır. İlk
    sürüm bunu ölçmeden "attribute varsa hub" diyordu ve 18 sınıfın çoğunu
    yanlış etiketledi.
    """
    methods = class_methods(node)
    known = {method.name for method in methods}
    attrs = {m.name: accessed_attributes(m, known) for m in methods}
    calls = {m.name: called_methods(m, known) for m in methods}
    called = set().union(*calls.values()) if calls else set()
    if pair_lcom4 > 1:
        isolated = [n for n in known if not attrs.get(n) and not calls.get(n) and n not in called]
        return ISOLATED_METHODS if isolated else UNEXPLAINED
    if cohesion_value < LOW_DENSITY:
        return CALL_EDGES if attribute_components(node) > 1 else HUB_ATTRIBUTES
    return UNEXPLAINED


def god_class_gate(modules, rules) -> dict:
    """`god_class` kokusunun LCOM4 koşulu yüzünden kaçırdığı sınıflar.

    Boyut koşullarını (NOM, WMC) geçen ama `lcom4` eşiğinin altında kalan
    sınıflar; ve bunlardan çağrı kenarları çıkarılınca eşiği geçecek olanlar.
    Bu bir hata sayımı değil: LCOM4'ün tanımı çağrıyı bağ sayar. Soru, bu
    tanımın `god_class` için doğru kapı olup olmadığıdır (Blok 1b girdisi).

    `fired` kapının metrik koşulunu sayar. K10'dan beri metot adlarının en az
    yarısı taslak olan sınıf kokuyu almaz; onlar `interfaces`'ta ayrıca
    sayılır, böylece `fired - interfaces` raporların `god_class` sayısıdır.
    """
    from rlens.analysis.class_metrics import nom, stub_method_share, wmc
    from rlens.analysis.smells import INTERFACE_STUB_SHARE

    size = gated = gated_by_calls = fired = interfaces = 0
    examples: list[str] = []
    for module in modules:
        for node in iter_module_classes(module.tree):
            if nom(node) < rules["nom"] or wmc(node) < rules["wmc"]:
                continue
            size += 1
            value = lcom4(node)
            if value >= rules["lcom4"]:
                fired += 1
                if stub_method_share(node) >= INTERFACE_STUB_SHARE:
                    interfaces += 1
                continue
            gated += 1
            if attribute_components(node) >= rules["lcom4"]:
                gated_by_calls += 1
                if len(examples) < 5:
                    examples.append(
                        f"{module.relative_path}:{node.name} nom={nom(node)} lcom4={value}"
                    )
    return {
        "size_qualified": size,
        "fired": fired,
        "interfaces": interfaces,
        "gated_by_lcom4": gated,
        "gated_only_because_of_call_edges": gated_by_calls,
        "examples": examples,
    }


def collect(project) -> tuple[list[Pair], dict[str, int], list]:
    from cohesion.module import Module

    modules, _ = parse_project(project.scan_root, (".",), ALWAYS_EXCLUDED + project.excludes)
    pairs: list[Pair] = []
    excluded = {"single_method": 0, "no_class_variables": 0, "name_shadowed": 0}
    for module in modules:
        structure = Module(module.tree).structure
        for node in iter_module_classes(module.tree):
            entry = structure.get(node.name)
            if entry is None or entry["lineno"] != node.lineno:
                excluded["name_shadowed"] += 1
                continue
            if len({method.name for method in class_methods(node)}) < 2:
                excluded["single_method"] += 1
                continue
            if not entry["variables"]:
                excluded["no_class_variables"] += 1
                continue
            probe = Module.__new__(Module)
            probe.structure = {node.name: entry}
            lcom4_value = lcom4(node)
            cohesion_value = probe.class_cohesion_percentage(node.name)
            pairs.append(
                Pair(
                    project=project.name,
                    path=module.relative_path,
                    name=node.name,
                    lineno=node.lineno,
                    lcom4=lcom4_value,
                    cohesion=cohesion_value,
                    category=explain(node, lcom4_value, cohesion_value),
                )
            )
    return pairs, excluded, modules


def main() -> int:
    import cohesion

    report: dict = {"cohesion_version": getattr(cohesion, "__version__", "1.2.0"), "projects": {}}
    everything: list[Pair] = []
    from rlens.config import DEFAULTS

    rules = DEFAULTS["smells"]["god_class"]
    gate_totals: dict[str, int] = {}
    for project in load_projects():
        pairs, excluded, modules = collect(project)
        gate = god_class_gate(modules, rules)
        report["projects"][project.name] = {
            "compared": len(pairs),
            "excluded": excluded,
            "spearman": spearman([p.lcom4 for p in pairs], [p.cohesion for p in pairs]),
            "god_class_gate": gate,
        }
        for key, value in gate.items():
            if key != "examples":
                gate_totals[key] = gate_totals.get(key, 0) + value
        everything.extend(pairs)
    report["god_class_gate"] = {"rules": rules, **gate_totals}

    report["total"] = {
        "compared": len(everything),
        "spearman": spearman([p.lcom4 for p in everything], [p.cohesion for p in everything]),
    }
    report["top_deviations"] = [
        {
            "score": score,
            "project": pair.project,
            "path": pair.path,
            "class": pair.name,
            "line": pair.lineno,
            "lcom4": pair.lcom4,
            "cohesion": pair.cohesion,
            "category": pair.category,
        }
        for score, pair in deviations(everything)[:TOP_DEVIATIONS]
    ]

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"{'project':<11} {'compared':>8} {'rho':>8}  excluded")
    for name, entry in report["projects"].items():
        rho = entry["spearman"]
        print(
            f"{name:<11} {entry['compared']:>8} "
            f"{rho if rho is not None else '-':>8}  {entry['excluded']}"
        )
    print(f"{'total':<11} {report['total']['compared']:>8} {report['total']['spearman']:>8}")
    print(f"\ngod_class gate: {report['god_class_gate']}")
    for name, entry in report["projects"].items():
        for example in entry["god_class_gate"]["examples"]:
            print(f"  {name:<10} {example}")
    top = report["top_deviations"]
    categories: dict[str, int] = {}
    for item in top:
        categories[item["category"]] = categories.get(item["category"], 0) + 1
    report["top_deviation_categories"] = dict(sorted(categories.items()))
    RESULTS_FILE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\ntop {len(top)} deviations: {report['top_deviation_categories']}")
    for item in top:
        print(
            f"  {item['score']:.3f} {item['category']:<17} {item['project']:<10} "
            f"{item['path']}:{item['line']} {item['class']}  "
            f"lcom4={item['lcom4']} cohesion={item['cohesion']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
