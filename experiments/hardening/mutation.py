"""`analysis` paketinde mutation testing: sertleştirme Blok 4, madde 3.

    python experiments/hardening/mutation.py [--workers 8] [--only class_metrics]

**Neden kendi betiğimiz.** Plan `mutmut` diyordu; mutmut 3 Windows'ta yalnızca
WSL içinde çalışıyor ve bu makinede WSL'de Python yok. Aracın kendisi gibi
yalnızca `ast` kullanan küçük bir üreteç yazıldı. Skor mutmut'unkiyle birebir
karşılaştırılamaz (operatör kümesi farklı); kendi içinde tekrar üretilebilir.

**Nasıl.** `src/rlens` her işçi için geçici bir dizine kopyalanır; özgün
dosyalara hiç dokunulmaz. Her mutant bir dosyada tek bir AST düğümünü
değiştirir, dosya `ast.unparse` ile yazılır ve `pytest tests -x` o kopyaya
karşı koşar (`PYTHONPATH` kopyayı gösterir, `pythonpath` ayarı boşaltılır).
Önce **taban koşusu**: hiçbir değişiklik yapılmamış ama `unparse` edilmiş
paket testleri geçmeli; geçmezse sonuç anlamsızdır ve betik durur.

Operatörler: `<`↔`<=`, `>`↔`>=`, `==`↔`!=`, `in`↔`not in`, `is`↔`is not`;
`+`↔`-`, `*`→`+`; `and`↔`or`; `not x`→`x`; tamsayı sabit `n`→`n+1`;
`True`↔`False`; `return x`→`return None`.

Sonuç `results/mutation.json`: dosya başına öldürülen/hayatta kalan/zaman
aşımı ve hayatta kalan her mutantın yeri. Süre ortama bağlıdır, dosyaya
yazılmaz.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PACKAGE = REPO / "src" / "rlens"
TARGET = PACKAGE / "analysis"
RESULTS = HERE / "results" / "mutation.json"
#: Kesilen koşuların ara sonuçları; git dışı.
JOURNAL = HERE / ".mutation-journal.jsonl"
TIMEOUT = 180

_COMPARE_SWAP = {
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
}
_BINOP_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Add}


@dataclass(frozen=True)
class Site:
    file: str
    index: int
    """Aynı dosyada, `sites` yürüyüşündeki sıra; mutant bununla yeniden bulunur."""
    lineno: int
    kind: str
    detail: str


def _is_docstring_or_annotation(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    return (
        isinstance(parent, (ast.arg, ast.AnnAssign)) and getattr(parent, "annotation", None) is node
    )


def candidates(tree: ast.Module) -> list[tuple[ast.AST, str, str, int | None]]:
    """(düğüm, tür, açıklama, alt indeks) listesi; sıra `ast.walk` sırasıdır."""
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    found: list[tuple[ast.AST, str, str, int | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for position, op in enumerate(node.ops):
                if type(op) in _COMPARE_SWAP:
                    swapped = _COMPARE_SWAP[type(op)].__name__
                    found.append((node, "compare", f"{type(op).__name__}->{swapped}", position))
        elif isinstance(node, ast.BinOp) and type(node.op) in _BINOP_SWAP:
            swapped = _BINOP_SWAP[type(node.op)].__name__
            found.append((node, "binop", f"{type(node.op).__name__}->{swapped}", None))
        elif isinstance(node, ast.BoolOp):
            other = "Or" if isinstance(node.op, ast.And) else "And"
            found.append((node, "boolop", f"{type(node.op).__name__}->{other}", None))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            found.append((node, "not", "drop not", None))
        elif (
            isinstance(node, ast.Constant)
            and type(node.value) in (int, bool)
            and not _is_docstring_or_annotation(node, parents)
        ):
            detail = (
                f"{node.value}->{not node.value}"
                if isinstance(node.value, bool)
                else f"{node.value}->{node.value + 1}"
            )
            found.append((node, "constant", detail, None))
        elif (
            isinstance(node, ast.Return)
            and node.value is not None
            and not (isinstance(node.value, ast.Constant) and node.value.value is None)
        ):
            found.append((node, "return", "return None", None))
    return found


def sites(path: Path) -> list[Site]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        Site(path.name, index, getattr(node, "lineno", 0), kind, detail)
        for index, (node, kind, detail, _) in enumerate(candidates(tree))
    ]


def mutate(source: str, index: int) -> str:
    tree = ast.parse(source)
    node, kind, _, position = candidates(tree)[index]
    if kind == "compare":
        node.ops[position] = _COMPARE_SWAP[type(node.ops[position])]()
    elif kind == "binop":
        node.op = _BINOP_SWAP[type(node.op)]()
    elif kind == "boolop":
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif kind == "not":
        replacement = copy.deepcopy(node.operand)
        _replace(tree, node, replacement)
    elif kind == "constant":
        node.value = (not node.value) if isinstance(node.value, bool) else node.value + 1
    elif kind == "return":
        node.value = ast.Constant(value=None)
    return ast.unparse(ast.fix_missing_locations(tree)) + "\n"


def _replace(tree: ast.AST, old: ast.AST, new: ast.AST) -> None:
    for parent in ast.walk(tree):
        for field, value in ast.iter_fields(parent):
            if value is old:
                setattr(parent, field, new)
                return
            if isinstance(value, list):
                for position, item in enumerate(value):
                    if item is old:
                        value[position] = new
                        return


def run_tests(workdir: Path) -> str:
    """'passed', 'failed' ya da 'timeout'."""
    env = {**os.environ, "PYTHONPATH": str(workdir / "src"), "PYTHONIOENCODING": "utf-8"}
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-x",
        "-q",
        "-p",
        "no:cacheprovider",
        "-o",
        "pythonpath=",
    ]
    try:
        done = subprocess.run(
            command, cwd=REPO, env=env, capture_output=True, timeout=TIMEOUT, check=False
        )
    except subprocess.TimeoutExpired:
        return "timeout"
    return "passed" if done.returncode == 0 else "failed"


def prepare(workdir: Path) -> None:
    shutil.copytree(
        PACKAGE, workdir / "src" / "rlens", ignore=shutil.ignore_patterns("__pycache__")
    )
    # Taban: `unparse` edilmiş dosyalar (yorumlar gider, anlam kalmalı).
    for path in (workdir / "src" / "rlens" / "analysis").glob("*.py"):
        path.write_text(ast.unparse(ast.parse(path.read_text(encoding="utf-8"))) + "\n", "utf-8")


def check_isolation(workdir: Path) -> None:
    """Testler gerçekten kopyayı mı içe aktarıyor?"""
    env = {**os.environ, "PYTHONPATH": str(workdir / "src")}
    done = subprocess.run(
        [sys.executable, "-c", "import rlens.analysis as a; print(a.__file__)"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    if not Path(done.stdout.strip()).is_relative_to(workdir):
        raise SystemExit(f"tests would import the original package: {done.stdout.strip()}")


def load_journal() -> dict[str, str]:
    """Önceki (kesilmiş) koşuların sonuçları. Anahtar dosyanın içerik özetini
    taşır; kaynak değiştiyse eski sonuç eşleşmez ve mutant yeniden koşar."""
    if not JOURNAL.exists():
        return {}
    entries = {}
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            entries[record["key"]] = record["outcome"]
    return entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--only", default="", help="comma-separated module names")
    args = parser.parse_args(argv)

    files = sorted(p for p in TARGET.glob("*.py") if p.name != "__init__.py")
    if args.only:
        wanted = {f"{name}.py" for name in args.only.split(",")}
        files = [p for p in files if p.name in wanted]
    work = [site for path in files for site in sites(path)]
    print(f"{len(work)} mutants in {len(files)} files, {args.workers} workers", flush=True)

    with tempfile.TemporaryDirectory() as root:
        workdirs = [Path(root) / f"w{i}" for i in range(args.workers)]
        for workdir in workdirs:
            prepare(workdir)
        check_isolation(workdirs[0])
        if run_tests(workdirs[0]) != "passed":
            print("baseline failed: the unparsed package does not pass its own tests")
            return 1

        originals = {path.name: path.read_text(encoding="utf-8") for path in files}
        digests = {
            name: hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            for name, text in originals.items()
        }
        journal = load_journal()
        free = list(workdirs)

        def one(site: Site) -> tuple[Site, str]:
            workdir = free.pop()
            try:
                target = workdir / "src" / "rlens" / "analysis" / site.file
                baseline = target.read_text(encoding="utf-8")
                target.write_text(mutate(originals[site.file], site.index), encoding="utf-8")
                try:
                    return site, run_tests(workdir)
                finally:
                    target.write_text(baseline, encoding="utf-8")
            finally:
                free.append(workdir)

        def key(site: Site) -> str:
            return f"{site.file}:{site.index}:{digests[site.file]}"

        outcomes: list[tuple[Site, str]] = [
            (site, journal[key(site)]) for site in work if key(site) in journal
        ]
        pending = [site for site in work if key(site) not in journal]
        print(f"{len(outcomes)} already in the journal, {len(pending)} to run", flush=True)
        with ThreadPoolExecutor(max_workers=args.workers) as pool, JOURNAL.open("a") as log:
            for done, (site, outcome) in enumerate(pool.map(one, pending), start=1):
                outcomes.append((site, outcome))
                # Her sonuç anında yazılır: uzun koşu kesilirse kaldığı yerden sürer.
                log.write(json.dumps({"key": key(site), "outcome": outcome}) + "\n")
                log.flush()
                if done % 25 == 0:
                    print(f"{done}/{len(pending)}", flush=True)

    per_file: dict[str, dict[str, int]] = {}
    survivors = []
    for site, outcome in outcomes:
        counts = per_file.setdefault(site.file, {"killed": 0, "survived": 0, "timeout": 0})
        key = {"failed": "killed", "passed": "survived", "timeout": "timeout"}[outcome]
        counts[key] += 1
        if outcome == "passed":
            line = originals[site.file].splitlines()[site.lineno - 1].strip() if site.lineno else ""
            survivors.append({**asdict(site), "line": line})

    total = len(outcomes)
    detected = sum(c["killed"] + c["timeout"] for c in per_file.values())
    summary = {
        "note": "own ast-based generator; not comparable to mutmut scores",
        "mutants": total,
        "detected": detected,
        "score": round(detected / total, 4) if total else None,
        "per_file": dict(sorted(per_file.items())),
        "survivors": sorted(survivors, key=lambda s: (s["file"], s["index"])),
    }
    print(json.dumps({k: v for k, v in summary.items() if k != "survivors"}, indent=2))
    if not args.only:
        RESULTS.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
