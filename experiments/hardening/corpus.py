"""Kalibrasyon korpusu: yükleme, indirme, envanter.

Sertleştirme Blok 1b, madde 1. `corpus.txt` Blok 1'in doğruluk setini
(`projects.txt`) kapsar ve tür bazında genişletir. Eşikler bu korpusun
dağılımından türetilecek; bu betik o dağılımın **girdisini** hazırlar.

    python experiments/hardening/corpus.py fetch
    python experiments/hardening/corpus.py inventory [--only a,b]

`inventory`, her projeyi `rlens scan`'in kendisiyle tarar (`scan_project`) ve
proje başına dosya/modül/sınıf/fonksiyon sayısını, ayrıştırılamayan dosyaları
ve koku sayılarını `results/corpus-inventory.json`'a yazar. Tarama süresi
ortama bağlı olduğundan ayrı dosyadadır (`results/corpus-timing.json`); sayım
dosyası tekrar üretildiğinde birebir aynı çıkmalıdır.

**Config tuzağı.** `.cache/` bu deponun içinde durur. `load_config` config'i
yukarı doğru arar ve RefactorLens'in kendi `rlens.yaml`'ını bulur
(`include: ["src/"]`); bir referans projeyi onunla taramak sessizce boş rapor
üretir. Bu betik config'i proje başına açıkça yazar: varsayılan config artı
yalnızca `corpus.txt`'teki ek dışlamalar (`project_config`).
"""

from __future__ import annotations

import argparse
import ast
import json
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from compare_radon import HERE, PROJECTS_FILE, Project, fetch, load_projects

CORPUS_FILE = HERE / "corpus.txt"
INVENTORY_FILE = HERE / "results" / "corpus-inventory.json"
TIMING_FILE = HERE / "results" / "corpus-timing.json"

PROJECT_TYPES = ("library", "cli", "web_app", "ml_research")


@dataclass(frozen=True)
class CorpusProject(Project):
    type: str = "library"

    def as_project(self) -> Project:
        return Project(self.name, self.repo, self.tag, self.commit, self.scope, self.excludes)


def load_corpus(path: Path = CORPUS_FILE) -> list[CorpusProject]:
    """`corpus.txt`'yi okur ve doğrular: tür, tam hash, benzersiz ad."""
    projects: list[CorpusProject] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 6:
            raise ValueError(f"corpus.txt: expected at least 6 columns, got: {raw!r}")
        name, kind, repo, tag, commit, scope, *excludes = parts
        if kind not in PROJECT_TYPES:
            raise ValueError(f"corpus.txt: {name}: unknown type {kind!r}")
        if len(commit) != 40:
            raise ValueError(f"corpus.txt: {name}: commit must be a full 40-char hash")
        projects.append(CorpusProject(name, repo, tag, commit, scope, tuple(excludes), kind))
    names = [project.name for project in projects]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"corpus.txt: duplicate names: {', '.join(duplicates)}")
    return projects


def accuracy_set_mismatches(corpus: list[CorpusProject], accuracy: list[Project]) -> list[str]:
    """`projects.txt`'teki her proje korpusta birebir aynı mı.

    Doğruluk sonuçları (Blok 1) belirli commit ve kapsama bağlıdır. Korpusta
    aynı ad farklı bir commit ya da kapsamla dururken kalibrasyon yapılırsa,
    iki bloğun sayıları sessizce farklı kodu anlatır.
    """
    by_name = {project.name: project for project in corpus}
    problems: list[str] = []
    for project in accuracy:
        match = by_name.get(project.name)
        if match is None:
            problems.append(f"{project.name}: missing from corpus")
        elif match.as_project() != project:
            problems.append(f"{project.name}: differs from projects.txt")
    return problems


def project_config(project: Project, workdir: Path):
    """Varsayılan config + yalnızca bu projenin ek dışlamaları.

    Listeler config birleştirmesinde bütünüyle değiştirilir; ek dışlamalar
    varsayılan listeye **eklenir**, yoksa `tests/` ve `migrations/` kaybolurdu.
    """
    import yaml

    from rlens.config import DEFAULTS, load_config

    excludes = list(DEFAULTS["scan"]["exclude"]) + [f"{name}/" for name in project.excludes]
    path = workdir / f"{project.name}.rlens.yaml"
    path.write_text(yaml.safe_dump({"scan": {"exclude": excludes}}), encoding="utf-8")
    config = load_config(path)
    if list(config.scan.include) != ["."]:
        raise RuntimeError(f"{project.name}: unexpected include {config.scan.include}")
    return config


def _span(node: ast.AST) -> set[int]:
    start = node.lineno
    decorators = getattr(node, "decorator_list", None)
    if decorators:
        start = min(start, *(decorator.lineno for decorator in decorators))
    return set(range(start, (node.end_lineno or node.lineno) + 1))


def _is_literal(value: ast.expr) -> bool:
    try:
        ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError, RecursionError):
        return False
    return True


def line_coverage(tree: ast.Module) -> tuple[int, int]:
    """(mantık satırı, ölçülen mantık satırı) sayıları; kümeler `logic_sets`'te."""
    logic, measured = logic_sets(tree)
    return len(logic), len(logic & measured)


def logic_sets(tree: ast.Module) -> tuple[set[int], set[int]]:
    """(mantık satırları, raporun birimlerinin kapsadığı satırlar) — bir modül için.

    **Mantık satırı:** herhangi bir ifadenin kapladığı satır; üç şey hariç:
    `import` satırları, birim dışındaki **serbest string ifadeleri** (modül
    docstring'i ve pydantic'in `x: int` altına yazdığı attribute docstring'leri
    gibi; hiçbir etkileri yoktur) ve birim dışındaki **düz veri atamaları**
    (değeri `ast.literal_eval` ile okunabilen `X = {...}`). Boş satır
    ve yorum hiçbir ifadeye ait olmadığı için zaten girmez.

    Veri atamaları neden hariç: ilk sürüm onları mantık sayıyordu ve netbox'ı
    %48 ölçülmüş gösterdi — ölçülmeyen 130 bin satırın 127 bini tek bir BM liman
    kodu tablosuydu (`extras/data/un_locode.py`). Bir sabit tablo metriklerin
    kaçırdığı karmaşıklık değildir. Modül düzeyindeki çağrılar (httpie'nin
    yüzlerce `parser.add_argument(...)`'ı) ve döngüler ise mantıktır ve kalır.

    **Ölçülen:** raporun içerdiği birimlerin — modülün en üst düzeyindeki
    fonksiyon ve sınıflar, dekoratörleriyle — kapsadığı satırlar. `if`/`try`
    altında tanımlı fonksiyonlar raporda yok (bkz. metric-accuracy §1 kapsama),
    burada da ölçülmemiş sayılır.

    Soru: RefactorLens'in hiçbir metriğinin görmediği kod ne kadar? Betik
    tarzı kodda (`train.py` en üst düzeyde yazılmış eğitim döngüsü) bu oran
    yüksektir ve oradaki karmaşıklık raporda iz bırakmaz.
    """
    from rlens.analysis.class_metrics import iter_module_classes
    from rlens.analysis.func_metrics import iter_module_functions

    code: set[int] = set()
    excluded: set[int] = set()
    data: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt):
            code |= _span(node)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            excluded |= _span(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            if _is_literal(node.value):
                data |= _span(node)
        elif (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            data |= _span(node)
    measured: set[int] = set()
    for unit in [*iter_module_functions(tree), *iter_module_classes(tree)]:
        measured |= _span(unit)

    # Birim içindeki veri ve string birimin parçasıdır; yalnızca dışarıdaki hariç.
    logic = code - excluded - (data - measured)
    return logic, measured


def skip_category(reason: str) -> str:
    """`syntax error (line 12): ...` → `syntax error`; sayım satır numarasından bağımsız olsun."""
    return reason.split("(", 1)[0].split(":", 1)[0].strip()


def summarise_report(report, modules=()) -> dict:
    """Bir tarama raporundan sayımlar. Metrik değerleri değil — onlar dağılım tablosunun işi."""
    logic = measured = 0
    for module in modules:
        module_logic, module_measured = line_coverage(module.tree)
        logic += module_logic
        measured += module_measured
    classes = list(report.iter_classes())
    module_functions = sum(len(module.functions) for module in report.modules)
    methods = sum(len(cls.methods) for cls in classes)
    smells = Counter(smell["label"] for smell in report.iter_smells())
    skipped = Counter(skip_category(entry["reason"]) for entry in report.skipped_files)
    return {
        "modules": len(report.modules),
        "classes": len(classes),
        "module_functions": module_functions,
        "methods": methods,
        "skipped_files": dict(sorted(skipped.items())),
        "smells": dict(sorted(smells.items())),
        "arch_enabled": report.arch_enabled,
        "logic_lines": logic,
        "measured_logic_share": round(measured / logic, 4) if logic else None,
    }


def inventory(projects: list[CorpusProject]) -> tuple[dict, dict]:
    from rlens.analysis.scanner import scan_project_with_sources

    counts: dict = {"projects": {}}
    timing: dict = {"note": "wall-clock seconds; environment-dependent", "projects": {}}
    with tempfile.TemporaryDirectory() as workdir:
        for project in projects:
            config = project_config(project, Path(workdir))
            started = time.perf_counter()
            result = scan_project_with_sources(project.scan_root, config)
            elapsed = time.perf_counter() - started
            summary = summarise_report(result.report, result.modules)
            entry = {"type": project.type, "commit": project.commit, **summary}
            counts["projects"][project.name] = entry
            timing["projects"][project.name] = round(elapsed, 1)
            print(
                f"{project.name:<17} {project.type:<12} modules={entry['modules']:>5} "
                f"classes={entry['classes']:>5} functions={entry['module_functions']:>5} "
                f"methods={entry['methods']:>6} measured={entry['measured_logic_share']:>6.1%} "
                f"{elapsed:>6.1f}s",
                flush=True,
            )

    by_type: dict[str, Counter[str]] = {}
    for entry in counts["projects"].values():
        bucket = by_type.setdefault(entry["type"], Counter())
        bucket["projects"] += 1
        for key in ("modules", "classes", "module_functions", "methods", "logic_lines"):
            bucket[key] += entry[key]
        bucket["measured_lines"] += round(entry["measured_logic_share"] * entry["logic_lines"])
    counts["by_type"] = {}
    for kind in PROJECT_TYPES:
        if kind in by_type:
            bucket = dict(by_type[kind])
            lines = bucket.pop("measured_lines")
            bucket["measured_logic_share"] = round(lines / bucket["logic_lines"], 4)
            counts["by_type"][kind] = bucket
    return counts, timing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("fetch", "inventory"))
    parser.add_argument("--only", default="")
    args = parser.parse_args(argv)

    corpus = load_corpus()
    problems = accuracy_set_mismatches(corpus, load_projects(PROJECTS_FILE))
    if problems:
        print("corpus.txt disagrees with projects.txt: " + "; ".join(problems))
        return 1
    if args.only:
        wanted = set(args.only.split(","))
        corpus = [project for project in corpus if project.name in wanted]

    if args.command == "fetch":
        for project in corpus:
            fetch(project.as_project())
        return 0

    missing = [project.name for project in corpus if not project.scan_root.is_dir()]
    if missing:
        print(f"not fetched: {', '.join(missing)} — run `fetch` first")
        return 1
    counts, timing = inventory(corpus)
    if not args.only:
        INVENTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        INVENTORY_FILE.write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8")
        TIMING_FILE.write_text(json.dumps(timing, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
