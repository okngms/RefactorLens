"""`god_class` kapısı için aday yoğunluk ölçüleri (v2.2 §5b, K4).

`god_class` bugün NOM ≥ 20 ∧ WMC ≥ 50 ∧ LCOM4 ≥ 3 ister. LCOM4 metot çağrısını
bağ saydığı için ortak bir yardımcı metodu olan büyük sınıflar tek bileşen olur
ve kokudan kaçar (korpusta 159 büyük sınıfın 61'i). Bu betik kapının yerine
konabilecek iki literatür ölçüsünü korpusta ölçer; **aracı değiştirmez**.

    LCOM3-HM   Hitz ve Montazeri (1995): LCOM4'ün grafiği, yalnızca ortak
               attribute kenarlarıyla. Bileşen sayısı; yüksek = kötü. Adı
               Henderson-Sellers'ın LCOM3'üyle (LCOM*) çakışır, o başka bir
               formüldür.
    TCC        Bieman ve Kang (1995), Lanza ve Marinescu'nun (2006) God Class
               stratejisindeki kullanımıyla: en az bir attribute'u **doğrudan**
               paylaşan metot çifti / bütün metot çiftleri. 0..1; düşük = kötü.
               Bieman-Kang'ın özgün tanımı çağrı ağacı üzerinden dolaylı erişimi
               de sayar; o zaman ortak yardımcı yine her şeyi bağlar. Dolaylı
               değişken bu yüzden aday değildir.

İkisi de `lcom4` ile aynı düğüm kümesini kullanır: `class_methods`, adla
(property getter/setter tek düğüm), `accessed_attributes` ile.

Ek olarak her sınıf için **attribute'suz metot payı** (hiçbir `self.<attr>`'a
dokunmayan metotlar) ölçülür. Çürütme koşulunun girdisi: yeni kapı yalnızca
durumsuz sınıfları (ziyaretçi, sabit fonksiyon kümesi) yakalıyorsa "çok
sorumluluk" değil "durumsuzluk" ölçüyordur.

    python experiments/hardening/density_gate.py

Önce `corpus.py fetch`. Çıktı: `results/density-gate.json` ve
`results/density-gate-tables.md`; ikisi de tekrar üretildiğinde birebir aynı.
"""

from __future__ import annotations

import ast
import json
import tempfile
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from compare_radon import HERE, PROJECTS_FILE, load_projects
from corpus import PROJECT_TYPES, accuracy_set_mismatches, load_corpus, project_config
from coverage import class_nodes
from distribution import MIN_VALUES, median_of, percentile

from rlens.analysis.class_metrics import (
    accessed_attributes,
    called_methods,
    class_methods,
    self_parameter,
)

JSON_FILE = HERE / "results" / "density-gate.json"
TABLES_FILE = HERE / "results" / "density-gate-tables.md"

PERCENTILES = (5, 10, 25, 50, 75, 90, 95)
TCC_CANDIDATES = (0.05, 0.1, 0.2, 1 / 3)
LCOM3_CANDIDATES = (3, 5, 10)
STATELESS_SHARE = 0.5
"""Metotlarının en az yarısı hiçbir attribute'a dokunmayan sınıf "durumsuz" sayılır."""


# --------------------------------------------------------------------------- #
# Ölçüler — test edilir
# --------------------------------------------------------------------------- #


def attribute_sets(node: ast.ClassDef) -> dict[str, set[str]]:
    """Metot adı → dokunduğu attribute'lar. Aynı adlı tanımlar (getter/setter) birleşir."""
    methods = class_methods(node)
    known = {method.name for method in methods}
    sets: dict[str, set[str]] = {}
    for method in methods:
        sets.setdefault(method.name, set()).update(accessed_attributes(method, known))
    return sets


def lcom3_hm(sets: dict[str, set[str]]) -> int | None:
    """Yalnızca ortak attribute kenarlarıyla bileşen sayısı. Metot yoksa `None`."""
    if not sets:
        return None
    parent = {name: name for name in sets}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    owners: dict[str, list[str]] = {}
    for name, attributes in sets.items():
        for attribute in attributes:
            owners.setdefault(attribute, []).append(name)
    for names in owners.values():
        for other in names[1:]:
            parent[find(other)] = find(names[0])
    return len({find(name) for name in sets})


def tcc_direct(sets: dict[str, set[str]]) -> float | None:
    """Doğrudan ortak attribute paylaşan metot çifti payı. İkiden az metotta `None`."""
    names = sorted(sets)
    if len(names) < 2:
        return None
    pairs = list(combinations(names, 2))
    connected = sum(1 for a, b in pairs if sets[a] & sets[b])
    return round(connected / len(pairs), 4)


def stateless_share(sets: dict[str, set[str]]) -> float | None:
    """Hiçbir attribute'a dokunmayan metot payı."""
    if not sets:
        return None
    return round(sum(1 for attributes in sets.values() if not attributes) / len(sets), 4)


STATELESS_KINDS = ("stub", "no_receiver", "delegates", "self_unused")
"""Durumsuz metodun türü, bu öncelikle: gövdesi taslak; alıcısı yok
(`@staticmethod` ya da parametresiz); kardeş metodu çağırıyor; alıcısı var ama
hiç kullanılmıyor."""


def is_stub_body(method: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Docstring dışında yalnızca `pass`, `...`, `raise NotImplementedError` ya da `return`."""
    body = list(method.body)
    first = body[0] if body else None
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        body = body[1:]
    if not body:
        return True
    if len(body) != 1:
        return False
    statement = body[0]
    if isinstance(statement, ast.Pass):
        return True
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
        return statement.value.value is Ellipsis
    if isinstance(statement, ast.Return):
        return statement.value is None or (
            isinstance(statement.value, ast.Constant) and statement.value.value is None
        )
    if isinstance(statement, ast.Raise) and statement.exc is not None:
        target = statement.exc.func if isinstance(statement.exc, ast.Call) else statement.exc
        return isinstance(target, ast.Name) and target.id == "NotImplementedError"
    return False


def stateless_kinds(node: ast.ClassDef) -> dict[str, int]:
    """Hiçbir attribute'a dokunmayan metotların türe göre sayımı (adla, `lcom4` gibi).

    Aynı adı taşıyan tanımlardan biri bile attribute'a dokunuyorsa ad durumludur.
    Durumsuz bir adın türü, tanımlarından ilkinin türüdür.
    """
    methods = class_methods(node)
    known = {method.name for method in methods}
    sets = attribute_sets(node)
    kinds = dict.fromkeys(STATELESS_KINDS, 0)
    seen: set[str] = set()
    for method in methods:
        if sets[method.name] or method.name in seen:
            continue
        seen.add(method.name)
        if is_stub_body(method):
            kinds["stub"] += 1
        elif self_parameter(method) is None:
            kinds["no_receiver"] += 1
        elif called_methods(method, known):
            kinds["delegates"] += 1
        else:
            kinds["self_unused"] += 1
    return kinds


# --------------------------------------------------------------------------- #
# Kapılar
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LargeClass:
    """Boyut koşulunu (NOM, WMC) geçen bir sınıf ve aday ölçüleri."""

    name: str
    nom: int
    lcom4: int
    lcom3: int
    tcc: float | None
    stateless: float
    kinds: tuple[int, int, int, int] = (0, 0, 0, 0)

    def fires(self, gate: str, threshold: float) -> bool:
        if gate == "lcom4":
            return self.lcom4 >= threshold
        if gate == "lcom3":
            return self.lcom3 >= threshold
        return self.tcc is not None and self.tcc < threshold


def gate_summary(classes: list[LargeClass], gate: str, threshold: float, current: int) -> dict:
    """Bir kapının büyük sınıflardaki sonucu, bugünkü LCOM4 kapısına göre."""
    fired = [c for c in classes if c.fires(gate, threshold)]
    old = {c.name for c in classes if c.fires("lcom4", current)}
    new_only = [c for c in fired if c.name not in old]
    lost = [c for c in classes if c.name in old and not c.fires(gate, threshold)]
    return {
        "fired": len(fired),
        "new": len(new_only),
        "lost": len(lost),
        "new_stateless": sum(1 for c in new_only if c.stateless >= STATELESS_SHARE),
        "fired_stateless": sum(1 for c in fired if c.stateless >= STATELESS_SHARE),
        "new_examples": [c.name for c in sorted(new_only, key=lambda c: -c.nom)[:8]],
        "lost_examples": [c.name for c in sorted(lost, key=lambda c: -c.nom)[:8]],
    }


# --------------------------------------------------------------------------- #
# Toplama
# --------------------------------------------------------------------------- #


def main() -> int:
    from rlens.analysis.model import SCHEMA_VERSION
    from rlens.analysis.scanner import scan_project_with_sources
    from rlens.config import DEFAULTS

    corpus = load_corpus()
    problems = accuracy_set_mismatches(corpus, load_projects(PROJECTS_FILE))
    if problems:
        print("corpus.txt disagrees with projects.txt: " + "; ".join(problems))
        return 1
    missing = [project.name for project in corpus if not project.scan_root.is_dir()]
    if missing:
        print(f"not fetched: {', '.join(missing)} — run `corpus.py fetch` first")
        return 1

    rules = DEFAULTS["smells"]["god_class"]
    per_project: dict[str, dict] = {}
    large: list[LargeClass] = []
    mismatches = 0
    with tempfile.TemporaryDirectory() as workdir:
        for project in corpus:
            config = project_config(project, Path(workdir))
            result = scan_project_with_sources(project.scan_root, config)
            nodes = class_nodes(result.modules)
            tcc_values: list[float] = []
            lcom3_values: list[int] = []
            for module in result.report.modules:
                for cls in module.classes:
                    sets = attribute_sets(nodes[(cls.module, cls.name, cls.lineno)])
                    if len(sets) < 2:
                        continue
                    lcom3 = lcom3_hm(sets)
                    tcc = tcc_direct(sets)
                    tcc_values.append(tcc)
                    lcom3_values.append(lcom3)
                    # Çağrı kenarları yalnızca bileşen birleştirir: LCOM3-HM ≥ LCOM4.
                    if cls.lcom4 is None or lcom3 < cls.lcom4:
                        mismatches += 1
                    if cls.nom >= rules["nom"] and cls.wmc >= rules["wmc"]:
                        large.append(
                            LargeClass(
                                name=f"{project.name}:{cls.module}.{cls.name}",
                                nom=cls.nom,
                                lcom4=cls.lcom4,
                                lcom3=lcom3,
                                tcc=tcc,
                                stateless=stateless_share(sets),
                                kinds=tuple(
                                    stateless_kinds(
                                        nodes[(cls.module, cls.name, cls.lineno)]
                                    ).values()
                                ),
                            )
                        )
            per_project[project.name] = {
                "type": project.type,
                "classes": len(tcc_values),
                "eligible": len(tcc_values) >= MIN_VALUES,
                "tcc": {f"p{q}": percentile(tcc_values, q) for q in PERCENTILES},
                "lcom3": {f"p{q}": percentile(lcom3_values, q) for q in PERCENTILES},
                "tcc_below": {
                    f"{c:.3g}": round(sum(1 for v in tcc_values if v < c) / len(tcc_values), 4)
                    if tcc_values
                    else None
                    for c in TCC_CANDIDATES
                },
                "lcom3_at_least": {
                    str(c): round(sum(1 for v in lcom3_values if v >= c) / len(lcom3_values), 4)
                    if lcom3_values
                    else None
                    for c in LCOM3_CANDIDATES
                },
            }
            print(f"{project.name:<17} scanned", flush=True)

    if mismatches:
        print(f"LCOM3-HM below LCOM4 in {mismatches} classes: the graph rule disagrees")
        return 1

    eligible = [p for p in per_project.values() if p["eligible"]]

    def medians(key: str) -> dict:
        return {stat: median_of(p[key][stat] for p in eligible) for stat in eligible[0][key]}

    gates = {"lcom4 >= 3": gate_summary(large, "lcom4", rules["lcom4"], rules["lcom4"])}
    for c in LCOM3_CANDIDATES:
        gates[f"lcom3 >= {c}"] = gate_summary(large, "lcom3", c, rules["lcom4"])
    for c in TCC_CANDIDATES:
        gates[f"tcc < {c:.3g}"] = gate_summary(large, "tcc", c, rules["lcom4"])

    summary = {
        "schema_version": SCHEMA_VERSION,
        "min_values": MIN_VALUES,
        "stateless_share": STATELESS_SHARE,
        "distribution": {
            "projects": len(eligible),
            "tcc": medians("tcc"),
            "lcom3": medians("lcom3"),
            "tcc_below": medians("tcc_below"),
            "lcom3_at_least": medians("lcom3_at_least"),
        },
        "large_classes": len(large),
        "large_stateless": sum(1 for c in large if c.stateless >= STATELESS_SHARE),
        "stateless_kinds": {
            "methods": {
                kind: sum(c.kinds[i] for c in large) for i, kind in enumerate(STATELESS_KINDS)
            },
            "dominant": {
                kind: sum(
                    1
                    for c in large
                    if c.stateless >= STATELESS_SHARE
                    and sum(c.kinds)
                    and c.kinds[i] == max(c.kinds)
                )
                for i, kind in enumerate(STATELESS_KINDS)
            },
        },
        "gates": gates,
        "by_type": {
            kind: sum(1 for c in large if per_project[c.name.split(":")[0]]["type"] == kind)
            for kind in PROJECT_TYPES
        },
        "per_project": per_project,
    }
    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    JSON_FILE.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    TABLES_FILE.write_text(render_tables(summary), encoding="utf-8")
    print(render_tables(summary))
    return 0


# --------------------------------------------------------------------------- #
# Tablolar
# --------------------------------------------------------------------------- #


def _pct(value: float | None) -> str:
    return "-" if value is None else f"%{value * 100:.1f}"


def _num(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:g}" if float(value).is_integer() else f"{value:.3f}"


def render_tables(summary: dict) -> str:
    d = summary["distribution"]
    lines = [
        "<!-- Üretildi: experiments/hardening/density_gate.py. Elle düzenlemeyin. -->",
        "",
        f"Scan şeması {summary['schema_version']}. En az iki farklı adlı metodu olan sınıflar; "
        f"proje başına persentil, projelerin medyanı ({d['projects']} proje, "
        f"en az {summary['min_values']} sınıf).",
        "",
        "## Dağılım",
        "",
        "| Ölçü | " + " | ".join(d["tcc"]) + " |",
        "|---|" + "---:|" * len(d["tcc"]),
        "| TCC | " + " | ".join(_num(v) for v in d["tcc"].values()) + " |",
        "| LCOM3-HM | " + " | ".join(_num(v) for v in d["lcom3"].values()) + " |",
        "",
        "| Aday | sınıfların payı |",
        "|---|---:|",
    ]
    for key, value in d["tcc_below"].items():
        lines.append(f"| TCC < {key} | {_pct(value)} |")
    for key, value in d["lcom3_at_least"].items():
        lines.append(f"| LCOM3-HM >= {key} | {_pct(value)} |")
    lines += [
        "",
        f"## Kapılar — boyut koşulunu geçen {summary['large_classes']} sınıf",
        "",
        f"Durumsuz: metotlarının en az %{summary['stateless_share'] * 100:.0f}'si hiçbir "
        f"attribute'a dokunmuyor ({summary['large_stateless']} büyük sınıf). "
        "Yeni / kayıp: bugünkü `lcom4 >= 3` kapısına göre.",
        "",
        "| Kapı | ateşler | yeni | kayıp | yeni içinde durumsuz | ateşleyen içinde durumsuz |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, gate in summary["gates"].items():
        lines.append(
            f"| {key} | {gate['fired']} | {gate['new']} | {gate['lost']} | "
            f"{gate['new_stateless']} | {gate['fired_stateless']} |"
        )
    kinds = summary["stateless_kinds"]
    lines += [
        "",
        "## Durumsuz metotların türü — büyük sınıflar",
        "",
        "Metot: bütün büyük sınıflardaki durumsuz metot adları. Baskın: durumsuz "
        "sınıflardan kaçında bu tür en kalabalık (eşitlikte birden fazla türe sayılır).",
        "",
        "| Tür | metot | baskın olduğu durumsuz sınıf |",
        "|---|---:|---:|",
    ]
    for kind in STATELESS_KINDS:
        lines.append(f"| {kind} | {kinds['methods'][kind]} | {kinds['dominant'][kind]} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
