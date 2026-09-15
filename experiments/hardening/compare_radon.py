"""CC çapraz doğrulaması: RefactorLens ile radon, fonksiyon fonksiyon.

Sertleştirme Blok 1, madde 2. Kabul kriteri: referans setinde CC farkı
yalnızca **belgelenmiş tanım farklarından** oluşur; sınıflandırılmamış fark 0.

Nasıl sınıflandırılır? Her fonksiyon için iki tanımın ayrıldığı yapılar
sayılır (`definition_deltas`). radon'un değeri bizimkine bu farkların
toplamı eklenerek **tahmin edilir**. Tahmin tutarsa fark açıklanmıştır;
tutmazsa sınıflandırılmamıştır ve ya bizim uygulamamızda ya radon'da bir hata
vardır — elle incelenir.

Tanım farkları (`docs/04 §2.3` ile radon 6.0.1 `ComplexityVisitor`):

    try_else        try/else          radon +1, biz 0 (`else` dal açmaz)
    loop_else       for/while-else    radon +1, biz 0
    assert          assert            radon +1, biz 0
    assert_contents assert içi        radon içine inmez; biz `and/or`,
                                      ternary, comprehension sayarız
    match_wildcard  case _ / case x   radon düşer, biz her case'i sayarız
    except_star     except* handler   radon TryStar'ı hiç tanımaz, biz sayarız

Bu betik aynı zamanda **kapsama** farkını raporlar: radon'un ölçüp raporumuzun
içermediği fonksiyonlar (dunder metotlar, `@overload` taslakları, modül
düzeyinde `if` altında tanımlı sınıf/fonksiyonlar, iç içe sınıf metotları).
Bunlar CC değeri farkı değildir; ayrı sayılır.

Kullanım:

    python experiments/hardening/compare_radon.py fetch
    python experiments/hardening/compare_radon.py compare [--only requests,click]

`fetch` projeleri `experiments/hardening/.cache/` altına commit hash'iyle
indirir (git'e girmez). `compare` sonucu
`experiments/hardening/results/cc-radon.json` dosyasına yazar ve özet tabloyu
basar. radon paket bağımlılığı değildir; yalnızca bu betik ister
(`pip install radon==6.0.1`).
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from rlens.analysis.class_metrics import class_methods, iter_module_classes
from rlens.analysis.func_metrics import (
    cyclomatic_complexity,
    is_overload_stub,
    iter_module_functions,
)
from rlens.analysis.parser import parse_project

HERE = Path(__file__).resolve().parent
PROJECTS_FILE = HERE / "projects.txt"
CACHE_DIR = HERE / ".cache"
RESULTS_FILE = HERE / "results" / "cc-radon.json"

#: Her projede dışlanan dizinler; `projects.txt` bunlara ekler.
ALWAYS_EXCLUDED = ("tests",)

CATEGORIES = (
    "try_else",
    "loop_else",
    "assert",
    "assert_contents",
    "match_wildcard",
    "except_star",
)

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef
_NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


# --------------------------------------------------------------------------- #
# Proje listesi
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Project:
    name: str
    repo: str
    tag: str
    commit: str
    scope: str
    excludes: tuple[str, ...] = ()

    @property
    def checkout(self) -> Path:
        return CACHE_DIR / self.name

    @property
    def scan_root(self) -> Path:
        return self.checkout / self.scope


def load_projects(path: Path = PROJECTS_FILE) -> list[Project]:
    """`projects.txt`'yi okur. Yorum ve boş satırlar atlanır."""
    projects: list[Project] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 5:
            raise ValueError(f"projects.txt: expected at least 5 columns, got: {raw!r}")
        name, repo, tag, commit, scope, *excludes = parts
        if len(commit) != 40:
            raise ValueError(f"projects.txt: {name}: commit must be a full 40-char hash")
        projects.append(Project(name, repo, tag, commit, scope, tuple(excludes)))
    return projects


# --------------------------------------------------------------------------- #
# Tanım farkı sınıflandırıcı — radon gerektirmez, test edilebilir
# --------------------------------------------------------------------------- #


def _own_scope(nodes: list[ast.AST]) -> Iterator[ast.AST]:
    """Verilen düğümler ve alt ağaçları; iç içe def/class'a inmeden.

    Lambda'ya inilir: iki araç da lambda gövdesini dıştaki fonksiyona yazar.
    """
    stack = [node for node in nodes if not isinstance(node, _NESTED)]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(
            child for child in ast.iter_child_nodes(node) if not isinstance(child, _NESTED)
        )


def _rlens_points(nodes: list[ast.AST]) -> int:
    """Bizim tanımımızla bu alt ağaçlardaki karar noktası sayısı (taban 1 hariç)."""
    points = 0
    for child in _own_scope(nodes):
        if isinstance(
            child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler)
        ):
            points += 1
        elif isinstance(child, ast.BoolOp):
            points += len(child.values) - 1
        elif isinstance(child, ast.comprehension):
            points += 1 + len(child.ifs)
        elif isinstance(child, ast.match_case):
            points += 1
    return points


def _is_radon_wildcard(case: ast.match_case) -> bool:
    """radon'un joker testi, birebir: `getattr(pattern, "pattern", False) is None`.

    Bu yalnızca `case _:` değil, yakalayıcı `case x:` desenini de kapsar.
    """
    return getattr(case.pattern, "pattern", False) is None


def definition_deltas(node: FunctionNode) -> dict[str, int]:
    """radon − RefactorLens farkının tanım kaynaklı bileşenleri.

    Pozitif: radon fazla sayar. Negatif: biz fazla sayarız. Dönen sözlükte
    yalnızca sıfırdan farklı kategoriler bulunur.
    """
    deltas: Counter[str] = Counter()
    asserts: list[ast.Assert] = []

    for child in _own_scope(list(node.body)):
        if isinstance(child, ast.Try) and child.orelse:
            deltas["try_else"] += 1
        elif isinstance(child, (ast.For, ast.AsyncFor, ast.While)) and child.orelse:
            deltas["loop_else"] += 1
        elif isinstance(child, ast.Assert):
            deltas["assert"] += 1
            asserts.append(child)
        elif isinstance(child, ast.Match):
            if any(_is_radon_wildcard(case) for case in child.cases):
                deltas["match_wildcard"] -= 1
        elif isinstance(child, ast.TryStar):
            deltas["except_star"] -= len(child.handlers)

    # radon `visit_Assert` içinde `generic_visit` çağırmaz: assert'in alt
    # ağacındaki hiçbir şey sayılmaz. İç içe assert olamayacağı için çift
    # sayım yoktur.
    for statement in asserts:
        inside = _rlens_points([statement])
        if inside:
            deltas["assert_contents"] -= inside

    return {name: value for name, value in deltas.items() if value}


# --------------------------------------------------------------------------- #
# Karşılaştırma
# --------------------------------------------------------------------------- #


@dataclass
class FunctionResult:
    path: str
    qualname: str
    lineno: int
    radon: int
    rlens: int
    deltas: dict[str, int]
    reported: bool
    """Bu fonksiyon RefactorLens raporunda yer alıyor mu (kapsama)."""

    @property
    def predicted(self) -> int:
        return self.rlens + sum(self.deltas.values())

    @property
    def explained(self) -> bool:
        return self.predicted == self.radon


@dataclass
class ProjectResult:
    name: str
    files: int
    skipped: int
    functions: list[FunctionResult] = field(default_factory=list)
    unmatched: int = 0
    """radon'un bildirdiği ama AST'de bulunamayan blok — 0 olmalı."""
    not_reported: Counter[str] = field(default_factory=Counter)


def reported_functions(tree: ast.Module) -> set[int]:
    """RefactorLens raporunun içerdiği fonksiyon düğümlerinin kimlikleri."""
    ids = {id(node) for node in iter_module_functions(tree)}
    for cls in iter_module_classes(tree):
        ids.update(id(method) for method in class_methods(cls))
    return ids


def _not_reported_reason(node: FunctionNode, tree: ast.Module) -> str:
    if is_overload_stub(node):
        return "overload_stub"
    if node.name.startswith("__") and node.name.endswith("__"):
        return "dunder_method"
    top_level_classes = {id(item) for item in tree.body if isinstance(item, ast.ClassDef)}
    for item in ast.walk(tree):
        if isinstance(item, ast.ClassDef) and node in item.body:
            return "top_level_class_other" if id(item) in top_level_classes else "nested_class"
    return "not_top_level"


def _radon_blocks(source: str):
    """radon'un fonksiyon ve metot blokları: (qualname, lineno, complexity)."""
    from radon.complexity import cc_visit
    from radon.visitors import Class

    for block in cc_visit(source):
        if isinstance(block, Class):
            continue
        qualname = f"{block.classname}.{block.name}" if block.is_method else block.name
        yield qualname, block.lineno, block.complexity


def compare_project(project: Project) -> ProjectResult:
    modules, skipped = parse_project(project.scan_root, (".",), ALWAYS_EXCLUDED + project.excludes)
    result = ProjectResult(project.name, files=len(modules), skipped=len(skipped))

    for module in modules:
        tree = module.tree
        by_position: dict[tuple[str, int], FunctionNode] = {
            (node.name, node.lineno): node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        reported = reported_functions(tree)

        for qualname, lineno, radon_cc in _radon_blocks(module.source):
            node = by_position.get((qualname.rsplit(".", 1)[-1], lineno))
            if node is None:
                result.unmatched += 1
                continue
            is_reported = id(node) in reported
            if not is_reported:
                result.not_reported[_not_reported_reason(node, tree)] += 1
            result.functions.append(
                FunctionResult(
                    path=module.relative_path,
                    qualname=qualname,
                    lineno=lineno,
                    radon=radon_cc,
                    rlens=cyclomatic_complexity(node),
                    deltas=definition_deltas(node),
                    reported=is_reported,
                )
            )
    return result


def summarise(results: list[ProjectResult], projects: list[Project]) -> dict:
    commits = {project.name: project.commit for project in projects}
    import radon

    summary: dict = {"radon_version": radon.__version__, "projects": [], "unclassified": []}
    totals: Counter[str] = Counter()
    for result in results:
        functions = result.functions
        differing = [f for f in functions if f.radon != f.rlens]
        unclassified = [f for f in functions if not f.explained]
        by_category_functions: Counter[str] = Counter()
        by_category_points: Counter[str] = Counter()
        for function in differing:
            for name, value in function.deltas.items():
                by_category_functions[name] += 1
                by_category_points[name] += value
        entry = {
            "name": result.name,
            "commit": commits[result.name],
            "files": result.files,
            "skipped_files": result.skipped,
            "functions": len(functions),
            "reported_functions": sum(1 for f in functions if f.reported),
            "equal": len(functions) - len(differing),
            "differing": len(differing),
            "unclassified": len(unclassified),
            "unmatched_radon_blocks": result.unmatched,
            "category_functions": dict(sorted(by_category_functions.items())),
            "category_points": dict(sorted(by_category_points.items())),
            "not_reported": dict(sorted(result.not_reported.items())),
        }
        summary["projects"].append(entry)
        for key in ("files", "functions", "reported_functions", "equal", "differing"):
            totals[key] += entry[key]
        totals["unclassified"] += len(unclassified)
        totals["unmatched_radon_blocks"] += result.unmatched
        summary["unclassified"].extend(
            {
                "project": result.name,
                "path": f.path,
                "function": f.qualname,
                "line": f.lineno,
                "radon": f.radon,
                "rlens": f.rlens,
                "predicted": f.predicted,
                "deltas": f.deltas,
            }
            for f in unclassified
        )
    summary["totals"] = dict(totals)
    return summary


def print_table(summary: dict) -> None:
    header = f"{'project':<11} {'funcs':>6} {'equal':>6} {'diff':>5} {'unclass':>7}  categories"
    print(header)
    print("-" * len(header))
    for entry in summary["projects"]:
        categories = ", ".join(f"{k}={v}" for k, v in entry["category_functions"].items())
        print(
            f"{entry['name']:<11} {entry['functions']:>6} {entry['equal']:>6} "
            f"{entry['differing']:>5} {entry['unclassified']:>7}  {categories or '-'}"
        )
    totals = summary["totals"]
    print("-" * len(header))
    print(
        f"{'total':<11} {totals['functions']:>6} {totals['equal']:>6} "
        f"{totals['differing']:>5} {totals['unclassified']:>7}"
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def fetch(project: Project) -> None:
    """Projeyi yalnızca dondurulmuş commit'te, sığ olarak indirir."""
    target = project.checkout
    head = target / ".git"
    if head.exists():
        current = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if current == project.commit:
            print(f"{project.name}: cached")
            return
    target.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{project.repo}"
    for command in (
        ["git", "init", "-q"],
        ["git", "remote", "remove", "origin"],
        ["git", "remote", "add", "origin", url],
        ["git", "fetch", "-q", "--depth", "1", "origin", project.commit],
        ["git", "checkout", "-q", "FETCH_HEAD"],
    ):
        # İlk indirmede `origin` yoktur; `remote remove` hatası beklenir ve susturulur.
        optional = command[1:3] == ["remote", "remove"]
        subprocess.run(
            ["git", "-C", str(target), *command[1:]],
            check=not optional,
            capture_output=optional,
        )
    print(f"{project.name}: {project.commit[:12]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("fetch", "compare"))
    parser.add_argument("--only", default="", help="comma-separated project names")
    args = parser.parse_args(argv)

    projects = load_projects()
    if args.only:
        wanted = set(args.only.split(","))
        projects = [project for project in projects if project.name in wanted]

    if args.command == "fetch":
        for project in projects:
            fetch(project)
        return 0

    missing = [project.name for project in projects if not project.scan_root.is_dir()]
    if missing:
        print(f"not fetched: {', '.join(missing)} — run `fetch` first", file=sys.stderr)
        return 1

    results = [compare_project(project) for project in projects]
    summary = summarise(results, projects)
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print_table(summary)
    return 0 if summary["totals"]["unclassified"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
