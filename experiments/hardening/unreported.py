"""Raporun görmediği kod: koşullu tanımlar (K5) ve sınıfsız modül kodu.

v2.2 §3 (modül düzeyi kohezyon) ve §5b (modül düzeyi kod ve koşullu
tanımlar). Bu betik bir ölçü önermez; kapsam belgesinin
(`docs/v2.2-sinifsiz-kod.md`) girdisi olan boşlukların büyüklüğünü ölçer.

    python experiments/hardening/unreported.py

Önce `corpus.py fetch`. Çıktı: `results/unreported.json`,
`results/unreported-tables.md`; tekrar üretildiğinde birebir aynı.

**Koşullu tanım:** modülün en üst düzeyinde değil, bir `if`/`try`/`with`/
`for`/`while`/`match` bloğunun içinde (herhangi bir derinlikte, ama bir
fonksiyon ya da sınıf gövdesine girmeden) tanımlanan fonksiyon ve sınıf. Rapor
bunları içermez (K5). Koşul türü en içteki bloğa göre:

    type_checking     `if TYPE_CHECKING:` (ya da `typing.TYPE_CHECKING`)
    import_fallback   `except ImportError` / `ModuleNotFoundError` bloğu olan `try`
    version_platform  testinde `sys.version_info`, `sys.platform`, `os.name`
                      ya da `platform` geçen `if`
    other_if          başka bir `if`
    other_try         başka bir `try`
    other             `with`, `for`, `while`, `match`
"""

from __future__ import annotations

import ast
import json
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from compare_radon import HERE, PROJECTS_FILE, load_projects
from corpus import (
    PROJECT_TYPES,
    _span,
    accuracy_set_mismatches,
    load_corpus,
    logic_sets,
    project_config,
)
from distribution import median_of

JSON_FILE = HERE / "results" / "unreported.json"
TABLES_FILE = HERE / "results" / "unreported-tables.md"

CONDITIONS = (
    "type_checking",
    "import_fallback",
    "version_platform",
    "other_if",
    "other_try",
    "other",
)
_DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_BLOCKS = (
    ast.If,
    ast.Try,
    ast.TryStar,
    ast.With,
    ast.AsyncWith,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Match,
)
_VERSION_NAMES = ("version_info", "platform", "os.name", "sys.platform")


# --------------------------------------------------------------------------- #
# Saf kurallar — test edilir
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ConditionalUnit:
    name: str
    kind: str
    """"function" ya da "class"."""
    condition: str
    lineno: int
    node: ast.AST


def _condition(block: ast.AST) -> str:
    if isinstance(block, ast.If):
        test = ast.unparse(block.test)
        if "TYPE_CHECKING" in test:
            return "type_checking"
        if any(name in test for name in _VERSION_NAMES):
            return "version_platform"
        return "other_if"
    if isinstance(block, ast.Try | ast.TryStar):
        for handler in block.handlers:
            caught = ast.unparse(handler.type) if handler.type is not None else ""
            if "ImportError" in caught or "ModuleNotFoundError" in caught:
                return "import_fallback"
        return "other_try"
    return "other"


def _children(block: ast.AST) -> list[ast.stmt]:
    statements: list[ast.stmt] = []
    for field in ("body", "orelse", "finalbody"):
        statements += getattr(block, field, []) or []
    for handler in getattr(block, "handlers", []) or []:
        statements += handler.body
    for case in getattr(block, "cases", []) or []:
        statements += case.body
    return statements


def conditional_units(tree: ast.Module) -> list[ConditionalUnit]:
    """Blok içindeki modül düzeyi tanımlar, kaynak sırasıyla."""
    found: list[ConditionalUnit] = []

    def visit(statements: list[ast.stmt], condition: str | None) -> None:
        for statement in statements:
            if isinstance(statement, _DEFINITIONS):
                if condition is not None:
                    kind = "class" if isinstance(statement, ast.ClassDef) else "function"
                    found.append(
                        ConditionalUnit(
                            statement.name, kind, condition, statement.lineno, statement
                        )
                    )
            elif isinstance(statement, _BLOCKS):
                visit(_children(statement), _condition(statement))

    visit(tree.body, None)
    return found


def _reported_names(tree: ast.Module) -> list[str]:
    """Raporun bugün içerdiği modül düzeyi birimlerin adları (`@overload` taslakları hariç)."""
    from rlens.analysis.class_metrics import iter_module_classes
    from rlens.analysis.func_metrics import iter_module_functions

    return [n.name for n in (*iter_module_functions(tree), *iter_module_classes(tree))]


def reported_duplicates(tree: ast.Module) -> set[str]:
    """Raporda **bugün** aynı modülde birden fazla birimle görünen adlar."""
    return {name for name, count in Counter(_reported_names(tree)).items() if count > 1}


def duplicate_names(tree: ast.Module) -> set[str]:
    """Koşullu tanımlar da rapora girseydi birden fazla birimle görünecek adlar."""
    names = _reported_names(tree) + [u.name for u in conditional_units(tree)]
    return {name for name, count in Counter(names).items() if count > 1}


# --------------------------------------------------------------------------- #
# Toplama
# --------------------------------------------------------------------------- #


def main() -> int:
    from rlens.analysis.model import SCHEMA_VERSION
    from rlens.analysis.scanner import scan_project_with_sources

    corpus = load_corpus()
    problems = accuracy_set_mismatches(corpus, load_projects(PROJECTS_FILE))
    if problems:
        print("corpus.txt disagrees with projects.txt: " + "; ".join(problems))
        return 1
    missing = [project.name for project in corpus if not project.scan_root.is_dir()]
    if missing:
        print(f"not fetched: {', '.join(missing)} — run `corpus.py fetch` first")
        return 1

    projects: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as workdir:
        for project in corpus:
            result = scan_project_with_sources(
                project.scan_root, project_config(project, Path(workdir))
            )
            conditions = dict.fromkeys(CONDITIONS, 0)
            kinds = Counter()
            duplicates = modules_with_duplicates = reported_dup = 0
            dup_examples: list[str] = []
            logic_total = unmeasured = conditional_lines = 0
            for module in result.modules:
                logic, measured = logic_sets(module.tree)
                units = conditional_units(module.tree)
                covered: set[int] = set()
                for unit in units:
                    conditions[unit.condition] += 1
                    kinds[unit.kind] += 1
                    covered |= _span(unit.node)
                dup = duplicate_names(module.tree)
                duplicates += len(dup)
                modules_with_duplicates += bool(dup)
                today = reported_duplicates(module.tree)
                reported_dup += len(today)
                if today and len(dup_examples) < 3:
                    dup_examples.append(f"{module.relative_path}: {', '.join(sorted(today))}")
                rest = logic - measured
                logic_total += len(logic)
                unmeasured += len(rest)
                conditional_lines += len(rest & covered)
            total_units = sum(conditions.values())
            projects[project.name] = {
                "type": project.type,
                "conditional_units": total_units,
                "functions": kinds["function"],
                "classes": kinds["class"],
                "conditions": conditions,
                "duplicate_names": duplicates,
                "reported_duplicates": reported_dup,
                "reported_duplicate_examples": dup_examples,
                "modules_with_duplicates": modules_with_duplicates,
                "logic_lines": logic_total,
                "unmeasured_share": round(unmeasured / logic_total, 4) if logic_total else None,
                "conditional_share_of_unmeasured": round(conditional_lines / unmeasured, 4)
                if unmeasured
                else None,
                "module_code_share": round((unmeasured - conditional_lines) / logic_total, 4)
                if logic_total
                else None,
            }
            print(f"{project.name:<17} scanned", flush=True)

    totals = dict.fromkeys(CONDITIONS, 0)
    for p in projects.values():
        for key, value in p["conditions"].items():
            totals[key] += value
    summary = {
        "schema_version": SCHEMA_VERSION,
        "conditional_units": sum(p["conditional_units"] for p in projects.values()),
        "conditions": totals,
        "duplicate_names": sum(p["duplicate_names"] for p in projects.values()),
        "reported_duplicates": sum(p["reported_duplicates"] for p in projects.values()),
        "median_unmeasured_share": median_of(p["unmeasured_share"] for p in projects.values()),
        "median_module_code_share": median_of(p["module_code_share"] for p in projects.values()),
        "median_conditional_share_of_unmeasured": median_of(
            p["conditional_share_of_unmeasured"] for p in projects.values()
        ),
        "by_type_module_code_share": {
            kind: median_of(p["module_code_share"] for p in projects.values() if p["type"] == kind)
            for kind in PROJECT_TYPES
        },
        "per_project": projects,
    }
    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    JSON_FILE.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    TABLES_FILE.write_text(render_tables(summary), encoding="utf-8")
    sys.stdout.reconfigure(errors="replace")
    print(render_tables(summary))
    return 0


def _pct(value: float | None) -> str:
    return "-" if value is None else f"%{value * 100:.1f}"


def render_tables(summary: dict) -> str:
    lines = [
        "<!-- Üretildi: experiments/hardening/unreported.py. Elle düzenlemeyin. -->",
        "",
        f"Scan şeması {summary['schema_version']}. Toplam {summary['conditional_units']} "
        f"koşullu tanım. Aynı modülde birden fazla birimle görünen ad: bugün raporda "
        f"{summary['reported_duplicates']}, koşullu tanımlar da girseydi "
        f"{summary['duplicate_names']}.",
        "",
        "Koşul türleri: " + ", ".join(f"{k} {v}" for k, v in summary["conditions"].items()),
        "",
        f"Projelerin medyanı: ölçülmeyen mantık {_pct(summary['median_unmeasured_share'])}; "
        f"bunun koşullu tanımlardan gelen payı "
        f"{_pct(summary['median_conditional_share_of_unmeasured'])}; sınıfsız modül kodu "
        f"(ölçülmeyen − koşullu) {_pct(summary['median_module_code_share'])}.",
        "",
        "| Proje | tür | koşullu tanım | fonk. | sınıf | TYPE_CHECKING | import yedeği "
        "| sürüm/platform | diğer | çakışan ad (bugün / koşullularla) | ölçülmeyen | koşullu payı "
        "| sınıfsız kod |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, p in summary["per_project"].items():
        c = p["conditions"]
        other = c["other_if"] + c["other_try"] + c["other"]
        lines.append(
            f"| {name} | {p['type']} | {p['conditional_units']} | {p['functions']} | "
            f"{p['classes']} | {c['type_checking']} | {c['import_fallback']} | "
            f"{c['version_platform']} | {other} | "
            f"{p['reported_duplicates']} / {p['duplicate_names']} | "
            f"{_pct(p['unmeasured_share'])} | {_pct(p['conditional_share_of_unmeasured'])} | "
            f"{_pct(p['module_code_share'])} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
