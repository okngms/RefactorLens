"""Eşik kararı girdisi: aday eşiklerin korpusta işaretlediği pay.

Sertleştirme Blok 1b, eşik kararı (`docs/v2-tanim-kararlari.md` K8). Dağılım
tablosu mevcut eşiklerin nereye düştüğünü gösterdi; bu betik **adayları** ölçer:

1. **LCOM4 uyarı/kritik adayları.** Her aday için eşiği karşılayan pay, iki
   paydayla: hesaplanmış bütün değerler (diğer metriklerle aynı payda) ve
   yalnızca bilgi taşıyan değerler (tek adlı metotlu sınıflar hariç,
   `coverage.py`). İkincisi duyarlılık için.
2. **Kullanıcının gördüğü etki.** En az bir sınıf eşiğini aşan sınıfların payı
   (terminalin "over threshold" sayımı ve `advise` hedef havuzu) mevcut
   varsayılanlarla ve LCOM4 adaylarıyla; yalnızca LCOM4 yüzünden işaretlenen pay.
3. **`too_many_params` ve yalnızca-anahtar parametreler.** Kokuyu alan
   fonksiyonlardan kaçı, yalnızca-anahtar parametreler sayılmasaydı eşiğin
   altında kalırdı. PARAMS tanımını değiştirmek şema artışıdır; bu yalnızca
   o seçeneğin ne kazandıracağını ölçer.

    python experiments/hardening/thresholds.py

Önce `corpus.py fetch`. Çıktı: `results/threshold-candidates.json` (tekrar
üretildiğinde birebir aynı) ve `results/threshold-candidates-tables.md`.
Ağırlıklandırma dağılım tablosuyla aynı: proje başına pay, projelerin medyanı;
payda en az `MIN_VALUES` olan proje katılır.
"""

from __future__ import annotations

import ast
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from compare_radon import HERE, PROJECTS_FILE, load_projects
from corpus import PROJECT_TYPES, accuracy_set_mismatches, load_corpus, project_config
from coverage import class_nodes, lcom4_is_trivial
from distribution import MIN_VALUES, exceedance, median_of

JSON_FILE = HERE / "results" / "threshold-candidates.json"
TABLES_FILE = HERE / "results" / "threshold-candidates-tables.md"

LCOM4_CANDIDATES = (2, 3, 4, 5, 6, 7, 8, 9, 10)


# --------------------------------------------------------------------------- #
# Saf kurallar — test edilir
# --------------------------------------------------------------------------- #


def flagged(values: dict[str, float | None], thresholds: dict[str, float]) -> set[str]:
    """Eşiğini karşılayan metrikler. Kural `Threshold.level` ile aynı: `değer >= warn`."""
    return {
        metric
        for metric, warn in thresholds.items()
        if values.get(metric) is not None and values[metric] >= warn
    }


def keyword_only_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Yalnızca-anahtar parametre sayısı (`*` ya da `*args` sonrası adlı parametreler)."""
    return len(node.args.kwonlyargs)


@dataclass
class ProjectSample:
    lcom4_computed: list[int] = field(default_factory=list)
    lcom4_informative: list[int] = field(default_factory=list)
    class_values: list[dict[str, float | None]] = field(default_factory=list)
    too_many_params: int = 0
    rescued_by_kwonly: int = 0
    functions: int = 0


def class_flag_shares(
    sample: ProjectSample, thresholds: dict[str, float], lcom4_warn: int
) -> dict[str, float | None]:
    """En az bir eşiği aşan sınıf payı ve yalnızca LCOM4 yüzünden aşan pay."""
    rules = {**thresholds, "lcom4": lcom4_warn}
    total = len(sample.class_values)
    if not total:
        return {"any": None, "only_lcom4": None}
    any_flag = only_lcom4 = 0
    for values in sample.class_values:
        hits = flagged(values, rules)
        if hits:
            any_flag += 1
        if hits == {"lcom4"}:
            only_lcom4 += 1
    return {"any": round(any_flag / total, 4), "only_lcom4": round(only_lcom4 / total, 4)}


def summarise_project(sample: ProjectSample, thresholds: dict[str, float]) -> dict:
    lcom4 = {}
    for candidate in LCOM4_CANDIDATES:
        lcom4[str(candidate)] = {
            "computed": exceedance(sample.lcom4_computed, candidate),
            "informative": exceedance(sample.lcom4_informative, candidate),
            **class_flag_shares(sample, thresholds, candidate),
        }
    return {
        "classes": len(sample.class_values),
        "lcom4_computed": len(sample.lcom4_computed),
        "lcom4_informative": len(sample.lcom4_informative),
        "lcom4": lcom4,
        "functions": sample.functions,
        "too_many_params": sample.too_many_params,
        "rescued_by_kwonly": sample.rescued_by_kwonly,
    }


def aggregate(summaries: list[dict], candidate: int) -> dict:
    """Aday başına projelerin medyanı; her payda kendi uygunluk kuralıyla."""
    key = str(candidate)
    computed = [s for s in summaries if s["lcom4_computed"] >= MIN_VALUES]
    informative = [s for s in summaries if s["lcom4_informative"] >= MIN_VALUES]
    classes = [s for s in summaries if s["classes"] >= MIN_VALUES]
    return {
        "computed": median_of(s["lcom4"][key]["computed"] for s in computed),
        "computed_projects": len(computed),
        "informative": median_of(s["lcom4"][key]["informative"] for s in informative),
        "informative_projects": len(informative),
        "any_class_flagged": median_of(s["lcom4"][key]["any"] for s in classes),
        "only_lcom4": median_of(s["lcom4"][key]["only_lcom4"] for s in classes),
        "class_projects": len(classes),
    }


def kwonly_summary(summaries: list[dict]) -> dict:
    """`too_many_params`: yalnızca-anahtar parametreler sayılmasaydı kaybolacak pay."""
    firing = [s for s in summaries if s["too_many_params"]]
    total = sum(s["too_many_params"] for s in summaries)
    rescued = sum(s["rescued_by_kwonly"] for s in summaries)
    return {
        "firings": total,
        "rescued": rescued,
        "pooled_share": round(rescued / total, 4) if total else None,
        "median_share": median_of(s["rescued_by_kwonly"] / s["too_many_params"] for s in firing),
    }


# --------------------------------------------------------------------------- #
# Toplama
# --------------------------------------------------------------------------- #


def function_nodes(parsed_modules) -> dict[tuple[str, int, str], ast.AST]:
    """(modül, satır, ad) → fonksiyon düğümü."""
    return {
        (module.module, node.lineno, node.name): node
        for module in parsed_modules
        for node in ast.walk(module.tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def collect(result, class_thresholds: dict[str, float], params_warn: int) -> ProjectSample:
    classes = class_nodes(result.modules)
    functions = function_nodes(result.modules)
    sample = ProjectSample()
    for module in result.report.modules:
        reports = list(module.functions)
        for cls in module.classes:
            reports.extend(cls.methods)
            values = {metric: getattr(cls, metric) for metric in class_thresholds}
            values["lcom4"] = cls.lcom4
            sample.class_values.append(values)
            if cls.lcom4 is not None:
                sample.lcom4_computed.append(cls.lcom4)
                if not lcom4_is_trivial(classes[(cls.module, cls.name, cls.lineno)]):
                    sample.lcom4_informative.append(cls.lcom4)
        for function in reports:
            sample.functions += 1
            # `too_many_params` kuralı (`smells.py`): eşik ve giriş noktası değil.
            if function.param_count >= params_warn and function.entry_point is None:
                sample.too_many_params += 1
                node = functions[(module.module, function.lineno, function.name)]
                if function.param_count - keyword_only_count(node) < params_warn:
                    sample.rescued_by_kwonly += 1
    return sample


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

    defaults = DEFAULTS["thresholds"]
    class_thresholds = {metric: defaults[metric]["warn"] for metric in ("nom", "wmc", "dcc")}
    params_warn = defaults["max_params"]["warn"]

    per_project: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as workdir:
        for project in corpus:
            config = project_config(project, Path(workdir))
            result = scan_project_with_sources(project.scan_root, config)
            sample = collect(result, class_thresholds, params_warn)
            smell_count = sum(
                1 for smell in result.report.iter_smells() if smell["label"] == "too_many_params"
            )
            if smell_count != sample.too_many_params:
                print(
                    f"{project.name}: too_many_params rule disagrees with the report "
                    f"({sample.too_many_params} vs {smell_count})"
                )
                return 1
            per_project[project.name] = {"type": project.type} | summarise_project(
                sample, class_thresholds
            )
            print(f"{project.name:<17} scanned", flush=True)

    names_by_type = {kind: [p.name for p in corpus if p.type == kind] for kind in PROJECT_TYPES}
    summaries = list(per_project.values())
    summary = {
        "schema_version": SCHEMA_VERSION,
        "min_values": MIN_VALUES,
        "class_thresholds": class_thresholds,
        "lcom4": {
            str(c): {
                "all": aggregate(summaries, c),
                "by_type": {
                    kind: aggregate([per_project[n] for n in names], c)
                    for kind, names in names_by_type.items()
                },
            }
            for c in LCOM4_CANDIDATES
        },
        "kwonly": kwonly_summary(summaries),
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


def render_tables(summary: dict) -> str:
    rules = ", ".join(f"{k.upper()} >= {v:g}" for k, v in summary["class_thresholds"].items())
    lines = [
        "<!-- Üretildi: experiments/hardening/thresholds.py. Elle düzenlemeyin. -->",
        "",
        f"Scan şeması {summary['schema_version']}. Proje başına pay, projelerin medyanı; "
        f"paydası en az {summary['min_values']} olan projeler.",
        "",
        "## LCOM4 adayları",
        "",
        f"Sınıf payları diğer sınıf eşikleri mevcut değerindeyken ({rules}).",
        "",
        "| LCOM4 >= | hesaplanan içinde | bilgi taşıyan içinde | en az bir eşik aşan sınıf "
        "| yalnız LCOM4 yüzünden |",
        "|---:|---:|---:|---:|---:|",
    ]
    for candidate, row in summary["lcom4"].items():
        a = row["all"]
        lines.append(
            f"| {candidate} | {_pct(a['computed'])} ({a['computed_projects']}) | "
            f"{_pct(a['informative'])} ({a['informative_projects']}) | "
            f"{_pct(a['any_class_flagged'])} | {_pct(a['only_lcom4'])} |"
        )
    lines += [
        "",
        "## LCOM4 adayları — tür bazında, hesaplanan içinde",
        "",
        "| LCOM4 >= | " + " | ".join(PROJECT_TYPES) + " |",
        "|---:|" + "---:|" * len(PROJECT_TYPES),
    ]
    for candidate, row in summary["lcom4"].items():
        by_type = row["by_type"]
        cells = " | ".join(
            f"{_pct(by_type[kind]['computed'])} ({by_type[kind]['computed_projects']})"
            for kind in PROJECT_TYPES
        )
        lines.append(f"| {candidate} | {cells} |")
    k = summary["kwonly"]
    lines += [
        "",
        "## `too_many_params` ve yalnızca-anahtar parametreler",
        "",
        "| Koku | yalnızca-anahtar sayılmasa kaybolur | havuz payı | proje medyanı |",
        "|---:|---:|---:|---:|",
        f"| {k['firings']} | {k['rescued']} | {_pct(k['pooled_share'])} | "
        f"{_pct(k['median_share'])} |",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
