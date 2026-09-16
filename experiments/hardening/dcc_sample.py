"""DCC elle sayımı: örneklem ve çalışma kâğıdı.

Sertleştirme Blok 1, madde 2 (kuplaj). DCC'nin otomatik referansı yoktur;
isim tabanlı çözümün ne sıklıkla yanıldığı ancak sınıf sınıf kodu okuyarak
bilinir. Bu betik okumayı **hızlandırır, yerine geçmez**:

1. `sample` — referans setinden deterministik, katmanlı bir örneklem çeker.
   Her projeden üç sınıf: düşük (0-2), orta (3-6) ve yüksek (7+) DCC
   bandından birer tane. Yalnızca düşük bantlı bir örneklem yanlış pozitifleri,
   yalnızca yüksek bantlı olan yanlış negatifleri göremezdi. Bant boşsa en
   yakın dolu banttan çekilir ve bu kayda geçer.
2. `worksheet` — örneklemdeki her sınıf için DCC'nin saydığı her adı, adın
   modülde **nereden bağlandığıyla** birlikte listeler (aynı modülde sınıf,
   proje importu, harici import, yerel ad...). Bu bir **ipucudur**: son karar
   kodu okuyan kişinin `dcc-manual.csv`'ye yazdığıdır.

İpucu ile karar ayrı tutulur. İpucu otomatik bir çözücüdür; kararı ona
bırakmak, DCC'yi başka bir otomatik çözücüyle doğrulamak olurdu — elle sayımın
amacı tam da bunun dışına çıkmaktır.

Kullanım (önce `compare_radon.py fetch`):

    python experiments/hardening/dcc_sample.py sample
    python experiments/hardening/dcc_sample.py worksheet [--class requests:sessions:Session]
"""

from __future__ import annotations

import argparse
import ast
import json
import random
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from compare_radon import ALWAYS_EXCLUDED, HERE, Project, load_projects

from rlens.analysis.class_metrics import (
    _names_in_string_annotations,
    class_aliases,
    collect_class_names,
    dcc,
    iter_module_classes,
)
from rlens.analysis.imports import project_module_predicate, root_package_name
from rlens.analysis.parser import ParsedModule, parse_project

SAMPLE_FILE = HERE / "results" / "dcc-sample.json"

#: Örneklem tohumu. Değiştirilirse örneklem değişir ve elle sayım geçersizleşir.
SEED = 20260915

#: (ad, alt sınır, üst sınır) — üst sınır dahil; None sınırsız.
BANDS: tuple[tuple[str, int, int | None], ...] = (
    ("low", 0, 2),
    ("mid", 3, 6),
    ("high", 7, None),
)

# Bağlanma türleri (ipucu).
MODULE_CLASS = "module_class"
PROJECT_IMPORT = "project_import"
EXTERNAL_IMPORT = "external_import"
MODULE_ASSIGN = "module_assign"
MODULE_FUNCTION = "module_function"
UNBOUND = "unbound"


# --------------------------------------------------------------------------- #
# Örneklem
# --------------------------------------------------------------------------- #


def band_of(value: int) -> str:
    for name, low, high in BANDS:
        if value >= low and (high is None or value <= high):
            return name
    raise ValueError(value)  # pragma: no cover - BANDS tüm tamsayıları kapsar


def stratified_pick(
    candidates: list[tuple[str, int]], rng: random.Random
) -> list[tuple[str, str, str]]:
    """Her banttan bir aday. Dönüş: (anahtar, istenen bant, gerçek bant).

    Bant boşsa sıradaki banda (yüksekten düşüğe değil, listedeki komşuya)
    düşülür ve aynı sınıf iki kez seçilmez. Aday kümesi sıralanmış
    olmalıdır; yoksa aynı tohum farklı örneklem verir.
    """
    by_band: dict[str, list[str]] = {name: [] for name, _, _ in BANDS}
    for key, value in candidates:
        by_band[band_of(value)].append(key)

    names = [name for name, _, _ in BANDS]
    chosen: set[str] = set()
    picks: list[tuple[str, str, str]] = []
    for index, wanted in enumerate(names):
        order = [wanted] + [n for n in names[index + 1 :] + names[:index][::-1] if n != wanted]
        for band in order:
            pool = [key for key in by_band[band] if key not in chosen]
            if pool:
                key = rng.choice(pool)
                chosen.add(key)
                picks.append((key, wanted, band))
                break
    return picks


@dataclass
class ProjectContext:
    project: Project
    modules: list[ParsedModule]
    names: frozenset[str]
    is_project_module: Callable[[str], bool]

    @classmethod
    def load(cls, project: Project) -> ProjectContext:
        modules, _ = parse_project(project.scan_root, (".",), ALWAYS_EXCLUDED + project.excludes)
        names = collect_class_names([m.tree for m in modules])
        predicate = project_module_predicate(
            (m.module for m in modules), root_package=root_package_name(project.scan_root)
        )
        return cls(project, modules, names, predicate)

    def classes(self) -> Iterator[tuple[str, ParsedModule, ast.ClassDef, int]]:
        for module in self.modules:
            aliases = class_aliases(module.tree, self.names, self.is_project_module)
            for node in iter_module_classes(module.tree):
                key = f"{self.project.name}:{module.module}:{node.name}"
                yield key, module, node, dcc(node, self.names, aliases)


def build_sample() -> list[dict]:
    rng = random.Random(SEED)
    sample: list[dict] = []
    for project in load_projects():
        context = ProjectContext.load(project)
        candidates = sorted((key, value) for key, _, _, value in context.classes())
        for key, wanted, band in stratified_pick(candidates, rng):
            sample.append({"class": key, "band": wanted, "drawn_from": band})
    return sample


# --------------------------------------------------------------------------- #
# Çalışma kâğıdı — bağlanma ipucu
# --------------------------------------------------------------------------- #


def _module_scope(tree: ast.Module) -> Iterator[ast.stmt]:
    """Modül kapsamındaki ifadeler: `if`/`try` bloklarına iner, def'lere inmez."""
    stack: list[ast.stmt] = list(tree.body)
    while stack:
        statement = stack.pop()
        yield statement
        if isinstance(statement, (ast.If, ast.Try, ast.TryStar, ast.With)):
            for field in ("body", "orelse", "finalbody"):
                stack.extend(getattr(statement, field, []) or [])
            for handler in getattr(statement, "handlers", []) or []:
                stack.extend(handler.body)


def module_bindings(
    tree: ast.Module, is_project_module: Callable[[str], bool]
) -> dict[str, list[tuple[str, str]]]:
    """Modül düzeyinde her adın nereden bağlandığı: `{ad: [(tür, ayrıntı)]}`."""
    bindings: dict[str, list[tuple[str, str]]] = {}

    def add(name: str, kind: str, detail: str) -> None:
        bindings.setdefault(name, []).append((kind, detail))

    for statement in _module_scope(tree):
        if isinstance(statement, ast.ClassDef):
            add(statement.name, MODULE_CLASS, f"line {statement.lineno}")
        elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(statement.name, MODULE_FUNCTION, f"line {statement.lineno}")
        elif isinstance(statement, ast.ImportFrom):
            internal = statement.level > 0 or bool(
                statement.module and is_project_module(statement.module)
            )
            source = "." * statement.level + (statement.module or "")
            for alias in statement.names:
                kind = PROJECT_IMPORT if internal else EXTERNAL_IMPORT
                add(alias.asname or alias.name, kind, f"from {source} import {alias.name}")
        elif isinstance(statement, ast.Import):
            for alias in statement.names:
                kind = PROJECT_IMPORT if is_project_module(alias.name) else EXTERNAL_IMPORT
                add(alias.asname or alias.name.split(".")[0], kind, f"import {alias.name}")
        elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            value = ast.unparse(statement.value) if statement.value is not None else ""
            for target in targets:
                if isinstance(target, ast.Name):
                    add(target.id, MODULE_ASSIGN, value[:60])
    return bindings


def local_bindings(node: ast.ClassDef) -> set[str]:
    """Sınıfın içinde yerel olarak bağlanan adlar: parametre, atama, döngü, `as`."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.arg):
            names.add(child.arg)
        elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
            names.add(child.id)
        elif isinstance(child, ast.ExceptHandler) and child.name:
            names.add(child.name)
    return names


@dataclass
class Reference:
    name: str
    forms: list[str]
    """`name`, `attr:<nesne>`, `string`, `alias:<ad>` — adın sınıfta nasıl geçtiği."""
    binding: list[tuple[str, str]]
    locally_bound: bool

    @property
    def hint(self) -> str:
        """Otomatik ipucu. Karar değildir."""
        kinds = {kind for kind, _ in self.binding}
        attribute_only = all(form.startswith("attr:") for form in self.forms)
        if attribute_only:
            return "check_attribute"
        if self.locally_bound and not kinds & {MODULE_CLASS, PROJECT_IMPORT}:
            return "likely_fp_local_name"
        if EXTERNAL_IMPORT in kinds and not kinds & {MODULE_CLASS, PROJECT_IMPORT}:
            return "likely_fp_external"
        if kinds & {MODULE_CLASS, PROJECT_IMPORT}:
            return "likely_tp"
        return "check_unbound"


def references(
    node: ast.ClassDef,
    tree: ast.Module,
    names: frozenset[str],
    is_project_module: Callable[[str], bool],
) -> list[Reference]:
    """DCC'nin saydığı her ad, geçiş biçimleri ve bağlanma kaynağıyla."""
    aliases = class_aliases(tree, names, is_project_module)
    bindings = module_bindings(tree, is_project_module)
    local = local_bindings(node)
    forms: dict[str, list[str]] = {}

    def note(name: str, form: str) -> None:
        if name in names and name != node.name and form not in forms.setdefault(name, []):
            forms[name].append(form)

    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            note(child.id, "name")
            if child.id in aliases:
                note(aliases[child.id], f"alias:{child.id}")
        elif isinstance(child, ast.Attribute):
            note(child.attr, f"attr:{ast.unparse(child.value)[:30]}")
    for name in _names_in_string_annotations(node):
        note(name, "string")
        if name in aliases:
            note(aliases[name], f"alias:{name}")

    result: list[Reference] = []
    for name, seen in sorted(forms.items()):
        binding = list(bindings.get(name, []))
        for alias_name in (form.split(":", 1)[1] for form in seen if form.startswith("alias:")):
            binding.extend(bindings.get(alias_name, []))
        result.append(Reference(name, seen, binding, name in local))
    return result


def fn_candidates(
    node: ast.ClassDef,
    tree: ast.Module,
    names: frozenset[str],
    counted: set[str],
    definitions: dict[str, int],
) -> list[str]:
    """Yanlış negatif adayları: DCC'nin görmediği olası referanslar.

    * `string` — annotation dışındaki string'de proje sınıfı adı
      (`cast("Order", x)`, `TypeVar("T", bound="Order")`).
    * `via_alias` — modül düzeyi atamayla tanımlı ad (`OrderLike = Union[Order,
      Draft]`) sınıfta kullanılıyor ve değeri sayılmamış proje sınıfı içeriyor.
    * `same_name` — sayılan ad projede birden çok sınıfa ait; farklı iki sınıfa
      referans tek sayılmış olabilir.
    """
    candidates: list[str] = []
    annotation_strings = _names_in_string_annotations(node)
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            try:
                parsed = ast.parse(child.value.strip(), mode="eval")
            except SyntaxError:
                continue
            for inner in ast.walk(parsed):
                if (
                    isinstance(inner, ast.Name)
                    and inner.id in names
                    and inner.id not in counted
                    and inner.id not in annotation_strings
                    and inner.id != node.name
                ):
                    candidates.append(f"string:{inner.id}")
    used = {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}
    for statement in _module_scope(tree):
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)) or statement.value is None:
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        for target in targets:
            if not (isinstance(target, ast.Name) and target.id in used):
                continue
            hidden = {
                inner.id
                for inner in ast.walk(statement.value)
                if isinstance(inner, ast.Name)
                and inner.id in names
                and inner.id not in counted
                and inner.id != node.name
            }
            candidates.extend(f"via_alias:{target.id}->{name}" for name in sorted(hidden))
    candidates.extend(
        f"same_name:{name}x{definitions[name]}"
        for name in sorted(counted)
        if definitions.get(name, 0) > 1
    )
    return sorted(set(candidates))


@dataclass
class SampledClass:
    key: str
    band: str
    drawn_from: str
    path: str
    lineno: int
    length: int
    refs: list[Reference]
    candidates: list[str]


def iter_sample(only: str | None = None) -> Iterator[SampledClass]:
    sample = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
    projects = {project.name: project for project in load_projects()}
    contexts: dict[str, tuple[ProjectContext, dict[str, int]]] = {}
    for entry in sample:
        key = entry["class"]
        if only and key != only:
            continue
        project_name, module_name, class_name = key.split(":")
        if project_name not in contexts:
            context = ProjectContext.load(projects[project_name])
            definitions: dict[str, int] = {}
            for other in context.modules:
                for item in ast.walk(other.tree):
                    if isinstance(item, ast.ClassDef):
                        definitions[item.name] = definitions.get(item.name, 0) + 1
            contexts[project_name] = (context, definitions)
        context, definitions = contexts[project_name]
        module = next(m for m in context.modules if m.module == module_name)
        node = next(n for n in iter_module_classes(module.tree) if n.name == class_name)
        refs = references(node, module.tree, context.names, context.is_project_module)
        counted = {ref.name for ref in refs}
        yield SampledClass(
            key=key,
            band=entry["band"],
            drawn_from=entry["drawn_from"],
            path=module.relative_path,
            lineno=node.lineno,
            length=(node.end_lineno or node.lineno) - node.lineno + 1,
            refs=refs,
            candidates=fn_candidates(node, module.tree, context.names, counted, definitions),
        )


def worksheet(only: str | None = None) -> None:
    for item in iter_sample(only):
        print(
            f"\n## {item.key}  {item.path}:{item.lineno}  lines={item.length}  dcc={len(item.refs)}"
        )
        for ref in item.refs:
            binding = "; ".join(f"{k}({d})" for k, d in ref.binding) or "-"
            local = " LOCAL" if ref.locally_bound else ""
            forms = ",".join(ref.forms)[:44]
            print(f"  {ref.hint:<22} {ref.name:<26} {forms:<44} {binding[:70]}{local}")
        for candidate in item.candidates:
            print(f"  FN?  {candidate}")


# --------------------------------------------------------------------------- #
# Kararlar ve özet
# --------------------------------------------------------------------------- #

VERDICTS_FILE = HERE / "dcc-verdicts.json"
CSV_FILE = HERE / "results" / "dcc-manual.csv"
SUMMARY_FILE = HERE / "results" / "dcc-manual-summary.json"


class UnreviewedError(ValueError):
    """İpucu doğru pozitif olmayan bir referans ya da FN adayı karara bağlanmamış."""


def candidate_name(candidate: str) -> str:
    """`via_alias:X->Order` → `Order`; `same_name:Orderx2` → `Order`; `string:Order` → `Order`."""
    kind, _, rest = candidate.partition(":")
    if kind == "via_alias":
        return rest.split("->", 1)[1]
    if kind == "same_name":
        return rest.rsplit("x", 1)[0]
    return rest


def judge(items: list[SampledClass], verdicts: dict) -> tuple[list[dict], dict]:
    """Kararları referanslara uygular; eksik karar varsa `UnreviewedError`.

    Kural: ipucu `likely_tp` olmayan her referansın, ve her FN adayının,
    kararı yazılı olmalıdır. Karar dosyasında olup örneklemde karşılığı
    bulunmayan girdi de hatadır — bayat karar sessizce kalmasın.
    """
    rows: list[dict] = []
    missing: list[str] = []
    ref_verdicts = verdicts.get("references", {})
    fn_verdicts = verdicts.get("false_negatives", {})
    rejected = verdicts.get("rejected_candidates", {})
    seen_refs: set[tuple[str, str]] = set()

    for item in items:
        class_verdicts = ref_verdicts.get(item.key, {})
        for ref in item.refs:
            decision = class_verdicts.get(ref.name)
            if decision is None:
                if ref.hint != "likely_tp":
                    missing.append(f"{item.key} {ref.name} ({ref.hint})")
                    continue
                decision = {"verdict": "tp", "category": "direct", "note": ""}
            seen_refs.add((item.key, ref.name))
            rows.append(
                {
                    "class": item.key,
                    "band": item.band,
                    "name": ref.name,
                    "kind": "counted",
                    "hint": ref.hint,
                    "verdict": decision["verdict"],
                    "category": decision["category"],
                    "note": decision.get("note", ""),
                }
            )
        fn_names = {entry["name"] for entry in fn_verdicts.get(item.key, [])}
        for candidate in item.candidates:
            if candidate_name(candidate) not in fn_names and candidate not in rejected.get(
                item.key, {}
            ):
                missing.append(f"{item.key} {candidate} (FN candidate)")
        for entry in fn_verdicts.get(item.key, []):
            rows.append(
                {
                    "class": item.key,
                    "band": item.band,
                    "name": entry["name"],
                    "kind": "missed",
                    "hint": "",
                    "verdict": "fn",
                    "category": entry["category"],
                    "note": entry.get("note", ""),
                }
            )

    keys = {item.key for item in items}
    for class_key, names in ref_verdicts.items():
        for name in names:
            if class_key not in keys or (class_key, name) not in seen_refs:
                missing.append(f"{class_key} {name} (verdict without a counted reference)")
    for class_key in list(fn_verdicts) + list(rejected):
        if class_key not in keys:
            missing.append(f"{class_key} (verdict for a class not in the sample)")
    if missing:
        raise UnreviewedError("; ".join(missing))

    return rows, summarise_rows(rows, items)


def summarise_rows(rows: list[dict], items: list[SampledClass]) -> dict:
    tp = sum(1 for r in rows if r["verdict"] == "tp")
    fp = sum(1 for r in rows if r["verdict"] == "fp")
    fn = sum(1 for r in rows if r["verdict"] == "fn")
    by_class: dict[str, dict[str, int]] = {}
    for row in rows:
        counts = by_class.setdefault(row["class"], {"tp": 0, "fp": 0, "fn": 0})
        counts[row["verdict"]] += 1
    exact = sum(
        1
        for item in items
        if not by_class.get(item.key, {}).get("fp") and not by_class.get(item.key, {}).get("fn")
    )

    def categories(verdict: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in rows:
            if row["verdict"] == verdict:
                counts[row["category"]] = counts.get(row["category"], 0) + 1
        return dict(sorted(counts.items()))

    return {
        "classes": len(items),
        "counted_references": tp + fp,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "recall": round(tp / (tp + fn), 4) if tp + fn else None,
        "classes_exact": exact,
        "fp_categories": categories("fp"),
        "fn_categories": categories("fn"),
        "tp_categories": categories("tp"),
        "per_class": {
            item.key: {
                "band": item.band,
                "measured": len(item.refs),
                "true": len(item.refs)
                - by_class.get(item.key, {}).get("fp", 0)
                + by_class.get(item.key, {}).get("fn", 0),
            }
            for item in items
        },
    }


def write_summary() -> int:
    import csv

    items = list(iter_sample())
    verdicts = json.loads(VERDICTS_FILE.read_text(encoding="utf-8"))
    rows, summary = judge(items, verdicts)
    CSV_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CSV_FILE.open("w", newline="", encoding="utf-8") as handle:
        # Platformdan bağımsız LF: csv varsayılanı CRLF yazar, git am ise CR siler.
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "per_class"}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("sample", "worksheet", "summary"))
    parser.add_argument("--class", dest="only", default=None)
    parser.add_argument(
        "--force", action="store_true", help="overwrite an existing sample (invalidates verdicts)"
    )
    args = parser.parse_args(argv)
    if args.command == "sample":
        # Elle verilen kararlar örnekleme bağlıdır. Örneklemin sessizce yeniden
        # yazılması — ör. bir metrik düzeltmesi bantları kaydırdığında —
        # `dcc-verdicts.json`'ı başka sınıflara ait kılar.
        if SAMPLE_FILE.exists() and not args.force:
            print(f"{SAMPLE_FILE.name} exists; pass --force to redraw (verdicts become invalid)")
            return 1
        sample = build_sample()
        SAMPLE_FILE.parent.mkdir(parents=True, exist_ok=True)
        SAMPLE_FILE.write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")
        for entry in sample:
            print(f"{entry['band']:<5} {entry['drawn_from']:<5} {entry['class']}")
        return 0
    if args.command == "summary":
        return write_summary()
    worksheet(args.only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
