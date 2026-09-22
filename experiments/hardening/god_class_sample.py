"""`god_class` için kör etiketli örneklem: kohezyon kapısını sınamanın tek yolu.

v2.2 §5b. Python için kohezyonu yansıtan hazır bir god class etiketi yok
(PySmell'in Large Class etiketi boyutu kodluyor; `stateless-gate.md`). Kapının
"birden fazla sorumluluk" iddiası ancak kendi etiketlerimizle sınanabilir.

    python experiments/hardening/god_class_sample.py sample     # bir kez
    python experiments/hardening/god_class_sample.py summary    # kararlar dolunca

**Körlük.** `sample` iki dosya yazar:

* `god-class-sample.json` — etiketleyenin göreceği tek dosya: proje, dosya,
  satır, sınıf adı. **Metrik yok, kapı sonucu yok.**
* `results/god-class-strata.json` — her örneğin tabakası (bugünkü kapı, R4).
  Etiketleme bitene kadar açılmaz. Körlük dürüstlüğe dayanır; dosyanın
  varlığı bunu değiştirmez, yalnızca `summary`'nin ihtiyacıdır.

Kararlar `god-class-verdicts.json`'a yazılır (`sample` boş şablonu üretir,
var olanı ezmez). Kılavuz: `god-class-labeling.md`.

**Tabakalar.** Boyut koşulunu geçen sınıflar (K10 taslak arayüzleri hariç:
onlar tanımla karara bağlandı) iki kapıya göre dört hücreye ayrılır: bugünkü
kapı (LCOM4 ≥ 3) × R4 (durumlu metotlarda LCOM3-HM ≥ eşik,
`stateless-gate.json`). Her hücreden sabit tohumla `PER_CELL` sınıf. Hücreler
eşit örneklendiği için kapının kesinliği ve duyarlılığı hücre büyüklükleriyle
ağırlıklandırılarak tahmin edilir.

**`summary`** tek bir karar eksikse ya da örneklemle uyuşmuyorsa sonuç üretmez.
"""

from __future__ import annotations

import argparse
import json
import random
import tempfile
from pathlib import Path

from compare_radon import HERE
from corpus import load_corpus, project_config
from coverage import class_nodes
from stateless_gate import CURRENT_LCOM4, lcom3_stateful

from rlens.analysis.class_metrics import stub_method_share
from rlens.analysis.smells import INTERFACE_STUB_SHARE

SAMPLE_FILE = HERE / "god-class-sample.json"
VERDICTS_FILE = HERE / "god-class-verdicts.json"
STRATA_FILE = HERE / "results" / "god-class-strata.json"
SUMMARY_FILE = HERE / "results" / "god-class-summary.json"
STATELESS_RESULTS = HERE / "results" / "stateless-gate.json"

SEED = 20260922
PER_CELL = 8
VERDICTS = ("god", "not_god", "unsure")
CELLS = ("both", "current_only", "r4_only", "neither")


# --------------------------------------------------------------------------- #
# Saf kurallar — test edilir
# --------------------------------------------------------------------------- #


def cell_of(current: bool, r4: bool) -> str:
    if current and r4:
        return "both"
    if current:
        return "current_only"
    if r4:
        return "r4_only"
    return "neither"


def stratified_pick(population: list[dict], per_cell: int, seed: int) -> list[dict]:
    """Her hücreden `per_cell` örnek; hücre küçükse tamamı. Sıra deterministik."""
    rng = random.Random(seed)
    picked: list[dict] = []
    for cell in CELLS:
        members = sorted(
            (item for item in population if item["cell"] == cell), key=lambda i: i["id"]
        )
        picked.extend(members if len(members) <= per_cell else rng.sample(members, per_cell))
    return picked


def blind_view(item: dict) -> dict:
    """Etiketleyenin göreceği alanlar: kimlik ve konum, başka bir şey değil."""
    return {key: item[key] for key in ("id", "project", "file", "line", "class")}


def verdict_problems(sample: list[dict], verdicts: dict) -> list[str]:
    """Kararların eksik ya da bayat olduğu örnekler; boşsa özet üretilebilir."""
    problems: list[str] = []
    for item in sample:
        entry = verdicts.get(item["id"])
        if entry is None:
            problems.append(f"{item['id']}: no verdict entry")
            continue
        if entry.get("class") != item["class"] or entry.get("file") != item["file"]:
            problems.append(f"{item['id']}: verdict is for a different class")
        if entry.get("verdict") not in VERDICTS:
            problems.append(f"{item['id']}: verdict must be one of {', '.join(VERDICTS)}")
        elif entry["verdict"] == "god" and len(entry.get("responsibilities", [])) < 2:
            problems.append(f"{item['id']}: a god verdict must name at least two responsibilities")
    extra = sorted(set(verdicts) - {item["id"] for item in sample})
    problems.extend(f"{key}: verdict for a class not in the sample" for key in extra)
    return problems


def weighted_scores(strata: dict, cell_sizes: dict[str, int], verdicts: dict, gate: str) -> dict:
    """Kapının kesinlik ve duyarlılığı, hücre büyüklükleriyle ağırlıklı.

    Hücrede etiketlenmiş (unsure hariç) örneklerin "god" payı, hücrenin
    tamamına genellenir. `gate` "current" ya da "r4": hangi hücrelerin o kapıda
    ateşlediği `CELLS` adından okunur.
    """
    fires = {
        "current": {"both", "current_only"},
        "r4": {"both", "r4_only"},
    }[gate]
    god_estimate: dict[str, float] = {}
    labelled: dict[str, int] = {}
    for cell in CELLS:
        decided = [
            verdicts[key]["verdict"]
            for key, stratum in strata.items()
            if stratum == cell and verdicts[key]["verdict"] != "unsure"
        ]
        labelled[cell] = len(decided)
        god_estimate[cell] = (
            cell_sizes[cell] * sum(1 for v in decided if v == "god") / len(decided)
            if decided
            else 0.0
        )
    fired = sum(cell_sizes[c] for c in fires)
    true_positive = sum(god_estimate[c] for c in fires)
    all_god = sum(god_estimate.values())
    return {
        "precision": round(true_positive / fired, 4) if fired else None,
        "recall": round(true_positive / all_god, 4) if all_god else None,
        "labelled_per_cell": labelled,
    }


# --------------------------------------------------------------------------- #
# Komutlar
# --------------------------------------------------------------------------- #


def build_population() -> tuple[list[dict], int]:
    from rlens.analysis.scanner import scan_project_with_sources
    from rlens.config import DEFAULTS

    stateless = json.loads(STATELESS_RESULTS.read_text(encoding="utf-8"))
    r4_threshold = stateless["candidates"]["R4"]["threshold"]
    rules = DEFAULTS["smells"]["god_class"]
    population: list[dict] = []
    with tempfile.TemporaryDirectory() as workdir:
        for project in load_corpus():
            result = scan_project_with_sources(
                project.scan_root, project_config(project, Path(workdir))
            )
            nodes = class_nodes(result.modules)
            paths = {m.module: m.path for m in result.report.modules}
            for module in result.report.modules:
                for cls in module.classes:
                    if cls.nom < rules["nom"] or cls.wmc < rules["wmc"]:
                        continue
                    node = nodes[(cls.module, cls.name, cls.lineno)]
                    if (stub_method_share(node) or 0) >= INTERFACE_STUB_SHARE:
                        continue
                    r4 = (lcom3_stateful(node) or 0) >= r4_threshold
                    population.append(
                        {
                            "id": f"{project.name}:{cls.module}:{cls.name}:{cls.lineno}",
                            "project": project.name,
                            "file": paths[cls.module],
                            "line": cls.lineno,
                            "class": cls.name,
                            "cell": cell_of(cls.lcom4 >= CURRENT_LCOM4, r4),
                        }
                    )
    return population, r4_threshold


def sample(force: bool) -> int:
    if SAMPLE_FILE.exists() and not force:
        print(f"{SAMPLE_FILE.name} exists; pass --force to redraw (verdicts become invalid)")
        return 1
    population, r4_threshold = build_population()
    picked = stratified_pick(population, PER_CELL, SEED)
    cell_sizes = {cell: sum(1 for i in population if i["cell"] == cell) for cell in CELLS}
    SAMPLE_FILE.write_text(
        json.dumps([blind_view(i) for i in picked], indent=2) + "\n", encoding="utf-8"
    )
    STRATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    STRATA_FILE.write_text(
        json.dumps(
            {
                "seed": SEED,
                "per_cell": PER_CELL,
                "r4_threshold": r4_threshold,
                "cell_sizes": cell_sizes,
                "strata": {i["id"]: i["cell"] for i in picked},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if not VERDICTS_FILE.exists():
        template = {
            i["id"]: {
                "class": i["class"],
                "file": i["file"],
                "verdict": None,
                "responsibilities": [],
                "note": "",
            }
            for i in picked
        }
        VERDICTS_FILE.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    print(f"{len(picked)} classes sampled from {len(population)}; cells {cell_sizes}")
    return 0


def summary() -> int:
    items = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
    verdicts = json.loads(VERDICTS_FILE.read_text(encoding="utf-8"))
    problems = verdict_problems(items, verdicts)
    if problems:
        print("verdicts incomplete or stale; no summary written:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    strata = json.loads(STRATA_FILE.read_text(encoding="utf-8"))
    result = {
        "labelled": len(items),
        "verdicts": {v: sum(1 for e in verdicts.values() if e["verdict"] == v) for v in VERDICTS},
        "current": weighted_scores(strata["strata"], strata["cell_sizes"], verdicts, "current"),
        "r4": weighted_scores(strata["strata"], strata["cell_sizes"], verdicts, "r4"),
    }
    SUMMARY_FILE.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("sample", "summary"))
    parser.add_argument(
        "--force", action="store_true", help="overwrite an existing sample (invalidates verdicts)"
    )
    args = parser.parse_args(argv)
    return sample(args.force) if args.command == "sample" else summary()


if __name__ == "__main__":
    raise SystemExit(main())
