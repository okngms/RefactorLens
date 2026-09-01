"""Faz 5 / B parçası: önerileri uygula ve tahminleri puanla.

A parçası modellerin ne söylediğini ölçtü. Bu parça söylediklerinin **doğru
olup olmadığını** ölçer, ve bunun için önerinin gerçekten uygulanması gerekir.

Akış üç adımdır çünkü ortadaki adım insana aittir:

    prepare  →  (siz kodu düzenlersiniz)  →  measure  →  summarise

**Neden taze kopya?** Fikstür değiştirilirse sonraki vakalar kirlenir ve altın
değer testleri kırılır. Her vaka kendi kopyasında yaşar, ölçüm bitince kopya
atılabilir.

**Neden diff saklanır?** "En dar yorumla uyguladım" bir iddiadır; kanıtı
uygulanan değişikliğin kendisidir. Proje kopyası commit edilmez (hacimli ve
tekrarlı), ama diff edilir.

**Neden davranış testleri zorunlu?** Metrikler iyileşirken kod bozulabilir —
ölçüldü, üç metrik iyileşirken altı test kırıldı. Testler geçmezse vaka
`broken` etiketlenir ve metrik deltası geçersiz sayılır.

Kullanım:

    python experiments/run_verify.py prepare --model openai/gpt-oss-120b \\
                                             --target god:OrderManager
    # ... experiments/cases/<slug>/project/ altındaki kodu düzenleyin ...
    python experiments/run_verify.py measure --model openai/gpt-oss-120b \\
                                             --target god:OrderManager --applied 1
    python experiments/run_verify.py summarise
"""

from __future__ import annotations

import argparse
import difflib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from rlens.analysis.scanner import scan_project  # noqa: E402
from rlens.config import load_config  # noqa: E402
from rlens.report.verify import verify_markdown  # noqa: E402
from rlens.verify.diff import diff_reports  # noqa: E402
from rlens.verify.prediction import check_predictions  # noqa: E402

FIXTURE = REPO_ROOT / "examples" / "messy_project"
RUNS = REPO_ROOT / "experiments" / "runs"
CASES = REPO_ROOT / "experiments" / "cases"

#: Protokol: her zaman ilk tekrar kullanılır.
#: "En iyi görüneni seç" yanlılığını engellemek için önceden sabitlenmiştir.
PROTOCOL_REPETITION = 1


def slug(value: str) -> str:
    return value.replace("/", "_").replace(":", "_")


def case_dir(model: str, target: str) -> Path:
    return CASES / f"{slug(model)}__{slug(target)}"


def advice_source(model: str, target: str, repetition: int) -> Path:
    return RUNS / slug(model) / slug(target) / f"rep{repetition}.json"


def python_files(root: Path) -> dict[str, str]:
    """Karşılaştırma için proje kaynaklarını okur (testler hariç)."""
    files = {}
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        if relative.startswith("tests/"):
            continue
        files[relative] = path.read_text(encoding="utf-8")
    return files


# --------------------------------------------------------------------------- #
# prepare
# --------------------------------------------------------------------------- #


def suggestion_markdown(advice: dict, model: str, repetition: int) -> str:
    """Uygulanacak öneriyi okunur biçimde yazar."""
    lines = [
        f"# Case: {advice['target']}",
        "",
        f"- **Model:** `{model}`",
        f"- **Repetition:** {repetition}",
        "",
        "> Apply **one** suggestion, under the narrowest possible interpretation.",
        "> Improve nothing the text does not explicitly ask for.",
        "",
        "## Diagnosis",
        "",
        advice.get("diagnosis", "(none)"),
        "",
    ]
    for index, suggestion in enumerate(advice.get("suggestions", []), start=1):
        predictions = ", ".join(
            f"{e['metric']} {e['direction']}" for e in suggestion.get("expected_effect", [])
        )
        lines += [
            f"## {index}. {suggestion.get('title', '(untitled)')}",
            "",
            f"- **Evidence:** {', '.join(suggestion.get('rationale_metric_link', [])) or '—'}",
            f"- **Predicted effect:** {predictions or 'none stated'}",
            "",
            suggestion.get("sketch", ""),
            "",
        ]
    if advice.get("risk_notes"):
        lines += ["## Risks", "", advice["risk_notes"], ""]
    return "\n".join(lines)


def prepare(model: str, target: str, repetition: int) -> int:
    source = advice_source(model, target, repetition)
    if not source.is_file():
        print(f"No advice run at {source}")
        print("Run experiments/run_advice.py first.")
        return 1

    destination = case_dir(model, target)
    if destination.exists():
        print(f"Case already prepared: {destination}")
        print("Delete it to start over, or run `measure` if you have applied a change.")
        return 1

    project = destination / "project"
    project.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXTURE, project)
    shutil.rmtree(project / "reports", ignore_errors=True)

    document = json.loads(source.read_text(encoding="utf-8"))
    advice = document["advices"][0]

    config = load_config(search_from=project)
    baseline = scan_project(project, config).to_dict()
    (destination / "baseline.json").write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (destination / "advice.json").write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (destination / "SUGGESTION.md").write_text(
        suggestion_markdown(advice, model, repetition), encoding="utf-8"
    )

    print(f"Case prepared: {destination}")
    print()
    print(f"  1. Read       {destination / 'SUGGESTION.md'}")
    print(f"  2. Edit       {project}")
    print(
        "  3. Run        python experiments/run_verify.py measure "
        f"--model {model} --target {target} --applied N"
    )
    print()
    print("Apply ONE suggestion, narrowest interpretation. Change nothing else.")
    return 0


# --------------------------------------------------------------------------- #
# measure
# --------------------------------------------------------------------------- #


def run_behaviour_tests(project: Path) -> tuple[bool, str]:
    """Fikstürün davranış testleri. Geçmezse vaka geçersizdir."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(project / "tests"), "-q"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    tail = (result.stdout or result.stderr).strip().splitlines()
    return result.returncode == 0, tail[-1] if tail else "(no output)"


def build_diff(project: Path) -> str:
    """Uygulanan değişikliğin unified diff'i — 'en dar yorum' iddiasının kanıtı."""
    before = python_files(FIXTURE)
    after = python_files(project)
    chunks: list[str] = []
    for name in sorted(set(before) | set(after)):
        old = before.get(name, "").splitlines(keepends=True)
        new = after.get(name, "").splitlines(keepends=True)
        if old == new:
            continue
        chunks.extend(difflib.unified_diff(old, new, fromfile=f"a/{name}", tofile=f"b/{name}"))
    return "".join(chunks)


def measure(model: str, target: str, applied: list[int]) -> int:
    destination = case_dir(model, target)
    project = destination / "project"
    if not project.is_dir():
        print(f"Case not prepared: {destination}")
        return 1

    changes = build_diff(project)
    if not changes:
        print("No change detected in the project copy. Apply the suggestion first.")
        return 1

    passed, summary = run_behaviour_tests(project)
    print(f"behaviour tests: {'PASS' if passed else 'FAIL'} — {summary}")

    config = load_config(search_from=project)
    baseline = json.loads((destination / "baseline.json").read_text(encoding="utf-8"))
    current = scan_project(project, config).to_dict()
    delta = diff_reports(baseline, current)

    document = json.loads((destination / "advice.json").read_text(encoding="utf-8"))
    predictions = check_predictions(document, delta, applied={target: applied})

    (destination / "applied.diff").write_text(changes, encoding="utf-8")
    (destination / "result.md").write_text(verify_markdown(delta, predictions), encoding="utf-8")
    (destination / "result.json").write_text(
        json.dumps(
            {
                "model": model,
                "target": target,
                "applied": applied,
                "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "behaviour_tests_passed": passed,
                "behaviour_tests_summary": summary,
                "status": "ok" if passed else "broken",
                "delta": delta.to_dict(),
                "predictions": predictions.to_dict(),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    for score in predictions.scores:
        print(f"{score.index}. {score.title}")
        for check in score.checks:
            mark = {"hit": "HIT ", "miss": "MISS", "unverifiable": "----"}[check.outcome]
            actual = check.actual or check.reason
            print(f"   {mark}  {check.metric:<8} predicted {check.predicted:<5} → {actual}")
        accuracy = "n/a" if score.accuracy is None else f"{score.accuracy:.0%}"
        print(f"   accuracy: {score.hits}/{score.verifiable} ({accuracy})")

    if not passed:
        print("\nStatus: BROKEN — the metric delta is void and reported as such.")
    print(f"\nWritten to {destination}")
    return 0


# --------------------------------------------------------------------------- #
# summarise
# --------------------------------------------------------------------------- #


def summarise(out: Path | None) -> int:
    results = []
    for path in sorted(CASES.glob("*/result.json")):
        results.append(json.loads(path.read_text(encoding="utf-8")))

    if not results:
        print("No measured cases yet.")
        return 1

    lines = [
        "# Prediction accuracy (phase 5, part B)",
        "",
        f"- **Cases:** {len(results)}",
        "",
        "> Each case applies **one** suggestion under the narrowest possible "
        "interpretation, always repetition 1. Cases whose behaviour tests fail "
        "are marked `broken`: their metric delta is void, because a refactoring "
        "that improves the numbers while breaking the code is a regression.",
        "",
        "| Model | Target | Status | Hits | Misses | Unverifiable | Accuracy |",
        "|---|---|---|---|---|---|---|",
    ]

    valid_hits = valid_total = 0
    for result in results:
        predictions = result["predictions"]
        accuracy = predictions["accuracy"]
        shown = "n/a" if accuracy is None else f"{accuracy:.0%}"
        if result["status"] == "ok":
            valid_hits += predictions["hits"]
            valid_total += predictions["hits"] + predictions["misses"]
        lines.append(
            f"| `{result['model']}` | `{result['target']}` | {result['status']} | "
            f"{predictions['hits']} | {predictions['misses']} | "
            f"{predictions['unverifiable']} | {shown} |"
        )

    overall = f"{valid_hits / valid_total:.0%}" if valid_total else "n/a"
    lines += [
        "",
        "## Overall (valid cases only)",
        "",
        f"- Verifiable predictions: {valid_total}",
        f"- Correct: {valid_hits}",
        f"- **Accuracy: {overall}**",
        "",
        "## Per-metric breakdown",
        "",
        "| Metric | Predicted | Correct | Accuracy |",
        "|---|---|---|---|",
    ]

    per_metric: dict[str, list[int]] = {}
    for result in results:
        if result["status"] != "ok":
            continue
        for score in result["predictions"]["suggestions"]:
            for check in score["checks"]:
                if check["outcome"] == "unverifiable":
                    continue
                bucket = per_metric.setdefault(check["metric"], [0, 0])
                bucket[0] += 1
                bucket[1] += check["outcome"] == "hit"

    for metric, (total, correct) in sorted(per_metric.items()):
        lines.append(f"| {metric} | {total} | {correct} | {correct / total:.0%} |")

    broken = [r for r in results if r["status"] != "ok"]
    if broken:
        lines += ["", "## Broken cases", ""]
        for result in broken:
            lines.append(
                f"- `{result['model']}` / `{result['target']}`: {result['behaviour_tests_summary']}"
            )

    report = "\n".join(lines) + "\n"
    print(report)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"written to {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare", help="Copy the fixture and show the suggestion.")
    p.add_argument("--model", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--repetition", type=int, default=PROTOCOL_REPETITION)

    m = sub.add_parser("measure", help="Run tests, re-measure, score the prediction.")
    m.add_argument("--model", required=True)
    m.add_argument("--target", required=True)
    m.add_argument(
        "--applied",
        type=int,
        nargs="+",
        required=True,
        help="Which suggestion number(s) you applied, counting from 1.",
    )

    s = sub.add_parser("summarise", help="Aggregate every measured case.")
    s.add_argument("--out", type=Path, default=None)

    args = parser.parse_args()

    if args.command == "prepare":
        return prepare(args.model, args.target, args.repetition)
    if args.command == "measure":
        return measure(args.model, args.target, args.applied)
    return summarise(args.out)


if __name__ == "__main__":
    raise SystemExit(main())
