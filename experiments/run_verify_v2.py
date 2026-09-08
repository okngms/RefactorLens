"""Faz 5b: 5a önerilerini uygula ve tahminleri puanla.

5a önerileri **okudu**. Bu parça onları uygular ve okumakla cevaplanamayan üç
şeyi sorar:

1. Tahmin tuttu mu? (`confidence` de var, dolayısıyla kalibrasyon ölçülebilir)
2. Öneri, adresliyorum dediği **ihlali gerçekten kapattı mı**? v2'nin yeni
   ölçümü; v1 bu soruyu soramıyordu.
3. Hiçbir metriğin göstermediği bir şey kötüleşti mi? Davranış kapısı ve
   Goodhart kontrolü bunu sorar — ve 5a **ikisinin de sessiz kalacağı** bir
   vaka buldu.

Akış üç adımdır çünkü ortadaki adım insana aittir:

    prepare  →  (siz kodu düzenlersiniz)  →  measure  →  summarise

Protokol `docs/v2-5b-protokol.md`'de kilitlidir: her zaman rep1, her zaman
öneri 1, en dar yorum, ve her uygulamadan sonra davranış testleri.

v1'in `run_verify.py`'si FINDINGS-1'in kaydıdır ve dokunulmaz.

Kullanım:

    python experiments/run_verify_v2.py prepare --condition arch \\
        --model openai/gpt-oss-120b --target src.domain.entities:Customer
    # ... experiments/v2/cases/<slug>/project/ altındaki kodu düzenleyin ...
    python experiments/run_verify_v2.py measure --condition arch \\
        --model openai/gpt-oss-120b --target src.domain.entities:Customer --applied 1
    python experiments/run_verify_v2.py summarise
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
from rlens.verify import goodhart as goodhart_module  # noqa: E402
from rlens.verify.calibration import collect_points  # noqa: E402
from rlens.verify.diff import diff_reports  # noqa: E402
from rlens.verify.prediction import check_predictions  # noqa: E402

FIXTURE = REPO_ROOT / "examples" / "layered_project"
RUNS = REPO_ROOT / "experiments" / "v2" / "runs"
CASES = REPO_ROOT / "experiments" / "v2" / "cases"

#: Protokol: hangi hücreler uygulanır. `docs/v2-5b-protokol.md`.
#:
#: Değişen eksen `metric-rules` (H2); mimari bağlam **sabit açık**, çünkü 5a
#: onun öneriyi değiştirdiğini gösterdi ve farklı öneriler üzerinden tahmin
#: karşılaştırmak iki etkiyi birbirine karıştırırdı.
CONDITIONS = ("arch", "arch_rules")

#: `qwen` dışarıda: 5a verisi eksik ve kayıp sistematikti.
MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")

TARGETS = (
    "src.services.order_service:OrderService",
    "src.domain.entities:Customer",
    "src.api.report_view:ReportView",
)

#: Her zaman ilk tekrar, her zaman ilk öneri.
PROTOCOL_REPETITION = 1


def slug(value: str) -> str:
    return value.replace("/", "_").replace(":", "_")


def case_dir(condition: str, model: str, target: str) -> Path:
    return CASES / f"{condition}__{slug(model)}__{slug(target)}"


def advice_source(condition: str, model: str, target: str, repetition: int) -> Path:
    return RUNS / condition / slug(model) / slug(target) / f"rep{repetition}.json"


def python_files(root: Path) -> dict[str, str]:
    """Karşılaştırma için proje kaynakları. Testler ayrı ele alınır."""
    files = {}
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        files[relative] = path.read_text(encoding="utf-8")
    return files


# --------------------------------------------------------------------------- #
# prepare
# --------------------------------------------------------------------------- #


def suggestion_markdown(payload: dict, condition: str) -> str:
    advice = payload["advices"][0]
    lines = [
        f"# Case: {advice['target']}",
        "",
        f"- **Condition:** {condition} "
        f"(arch-context {payload.get('arch_context')}, "
        f"metric-rules {payload.get('metric_rules')})",
        f"- **Model:** `{payload.get('model')}`",
        f"- **Repetition:** {PROTOCOL_REPETITION}",
        "",
        "> Apply **suggestion 1**, under the narrowest possible interpretation.",
        "> Improve nothing the text does not explicitly ask for.",
        "",
        "## Diagnosis",
        "",
        advice.get("diagnosis", "(none)"),
        "",
    ]
    for index, suggestion in enumerate(advice.get("suggestions", []), start=1):
        predictions = ", ".join(
            f"{e['metric']} {e['direction']}"
            + (f" ({e['confidence']:.2f})" if e.get("confidence") is not None else "")
            for e in suggestion.get("expected_effect", [])
        )
        lines += [
            f"## {index}. {suggestion.get('title', '(untitled)')}",
            "",
            f"- **Status:** {suggestion.get('status', 'linked')}",
            f"- **Evidence:** {', '.join(suggestion.get('rationale_metric_link', [])) or '—'}",
            f"- **Predicted effect:** {predictions or 'none stated'}",
        ]
        if suggestion.get("addresses_smells"):
            lines.append(f"- **Addresses:** {', '.join(suggestion['addresses_smells'])}")
        if suggestion.get("target_layer_after"):
            lines.append(f"- **Destination layer:** {suggestion['target_layer_after']}")
        lines += ["", suggestion.get("sketch", ""), ""]

    if advice.get("risk_notes"):
        lines += ["## Risks", "", advice["risk_notes"], ""]
    return "\n".join(lines)


def prepare(condition: str, model: str, target: str, repetition: int) -> int:
    source = advice_source(condition, model, target, repetition)
    if not source.is_file():
        print(f"No advice run at {source}")
        return 1

    destination = case_dir(condition, model, target)
    if destination.exists():
        print(f"Case already prepared: {destination}")
        print("Delete it to start over, or run `measure`.")
        return 1

    project = destination / "project"
    project.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXTURE, project)
    shutil.rmtree(project / "reports", ignore_errors=True)
    shutil.rmtree(project / ".rlens-cache", ignore_errors=True)

    payload = json.loads(source.read_text(encoding="utf-8"))
    config = load_config(search_from=project)
    baseline = scan_project(project, config).to_dict()

    (destination / "baseline.json").write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (destination / "advice.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (destination / "SUGGESTION.md").write_text(
        suggestion_markdown(payload, condition), encoding="utf-8"
    )

    open_violations = [
        v
        for v in baseline.get("violations", [])
        if v.get("source", "").startswith(target.split(":")[0])
    ]

    print(f"Case prepared: {destination}")
    print()
    print(f"  1. Read       {destination / 'SUGGESTION.md'}")
    print(f"  2. Edit       {project}")
    print(
        f"  3. Run        python experiments/run_verify_v2.py measure "
        f"--condition {condition} --model {model} --target {target} --applied 1"
    )
    if open_violations:
        print()
        print(f"  Open violations on this module ({len(open_violations)}):")
        for violation in open_violations:
            print(f"    {violation['code']} {violation['source']} → {violation['target']}")
    print()
    print("Apply suggestion 1, narrowest interpretation. Change nothing else.")
    return 0


# --------------------------------------------------------------------------- #
# measure
# --------------------------------------------------------------------------- #


def run_behaviour_tests(project: Path) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(project / "tests"), "-q"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    tail = (result.stdout or result.stderr).strip().splitlines()
    return result.returncode == 0, tail[-1] if tail else "(no output)"


def build_diff(project: Path) -> tuple[str, bool]:
    """Uygulanan değişikliğin diff'i ve testlerin değişip değişmediği.

    v1'de diff `tests/` klasörünü atlıyordu ve çağrı yeri güncellemesi kayda
    girmiyordu. Burada testler de diff'e dahildir; hangi değişikliğin kaynakta
    hangisinin testte olduğu ayrıca raporlanır.
    """
    before = python_files(FIXTURE)
    after = python_files(project)
    chunks: list[str] = []
    tests_changed = False

    for name in sorted(set(before) | set(after)):
        old = before.get(name, "").splitlines(keepends=True)
        new = after.get(name, "").splitlines(keepends=True)
        if old == new:
            continue
        if name.startswith("tests/"):
            tests_changed = True
        chunks.extend(difflib.unified_diff(old, new, fromfile=f"a/{name}", tofile=f"b/{name}"))
    return "".join(chunks), tests_changed


def measure(condition: str, model: str, target: str, applied: list[int]) -> int:
    destination = case_dir(condition, model, target)
    project = destination / "project"
    if not project.is_dir():
        print(f"Case not prepared: {destination}")
        return 1

    changes, tests_changed = build_diff(project)
    if not changes:
        print("No change detected. Apply the suggestion first.")
        return 1

    passed, summary = run_behaviour_tests(project)
    print(f"behaviour tests: {'PASS' if passed else 'FAIL'} — {summary}")

    config = load_config(search_from=project)
    baseline = json.loads((destination / "baseline.json").read_text(encoding="utf-8"))
    current = scan_project(project, config).to_dict()
    delta = diff_reports(baseline, current)

    document = json.loads((destination / "advice.json").read_text(encoding="utf-8"))
    predictions = check_predictions(document, delta, applied={target: applied})
    suspicions = goodhart_module.detect(baseline, current, delta.entities)
    calibration = collect_points(predictions)

    (destination / "applied.diff").write_text(changes, encoding="utf-8")
    (destination / "result.md").write_text(
        verify_markdown(delta, predictions, suspicions, calibration), encoding="utf-8"
    )
    (destination / "result.json").write_text(
        json.dumps(
            {
                "condition": condition,
                "model": model,
                "target": target,
                "applied": applied,
                "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "behaviour_tests_passed": passed,
                "behaviour_tests_summary": summary,
                "tests_were_modified": tests_changed,
                "status": "ok" if passed else "broken",
                "delta": delta.to_dict(),
                "predictions": predictions.to_dict(),
                "goodhart": suspicions.to_dict(),
                "calibration": calibration.to_dict(),
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
            confidence = "" if check.confidence is None else f"  ({check.confidence:.2f})"
            print(
                f"   {mark}  {check.metric:<8} predicted {check.predicted:<5} "
                f"→ {actual}{confidence}"
            )
        accuracy = "n/a" if score.accuracy is None else f"{score.accuracy:.0%}"
        print(f"   accuracy: {score.hits}/{score.verifiable} ({accuracy})")

    if delta.violations.removed or delta.violations.added:
        print()
        for item in delta.violations.removed:
            print(f"   CLOSED   {item}")
        for item in delta.violations.added:
            print(f"   OPENED   {item}")
    elif delta.violations.kept:
        print(f"\n   {len(delta.violations.kept)} violation(s) unchanged")

    if suspicions.any_suspicious:
        print("\nSuspicious: metrics improved while the interface shrank.")
    if not passed:
        print("\nStatus: BROKEN — the metric delta is void.")
    if tests_changed:
        print("\nNote: the behaviour tests were modified; recorded in result.json.")
    print(f"\nWritten to {destination}")
    return 0


# --------------------------------------------------------------------------- #
# summarise
# --------------------------------------------------------------------------- #


def load_results() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8")) for path in sorted(CASES.glob("*/result.json"))
    ]


def collect_calibration(results: list[dict], condition: str | None):
    """Ölçülmüş vakalardan kalibrasyon noktalarını yeniden kurar.

    Vaka başına saklanan Brier'ları ortalamak yanlış olurdu: kovalar vaka
    sınırında sıfırlanır ve ECE hesaplanamaz. Ham `(güven, sonuç)` çiftleri
    havuzlanır.

    `broken` vakalar dışarıdadır — metrik deltası geçersizse tahminin doğru
    sayılması da geçersizdir.
    """
    from rlens.verify.calibration import CalibrationPoint, calibrate

    points, missing = [], 0
    for result in results:
        if result["status"] != "ok":
            continue
        if condition is not None and result["condition"] != condition:
            continue
        for score in result["predictions"]["suggestions"]:
            for check in score["checks"]:
                if check["outcome"] not in ("hit", "miss"):
                    continue
                if check.get("confidence") is None:
                    missing += 1
                    continue
                points.append(
                    CalibrationPoint(
                        confidence=check["confidence"],
                        correct=check["outcome"] == "hit",
                        metric=check["metric"],
                        target=result["target"],
                    )
                )
    return calibrate(points, without_confidence=missing)


def summarise(out: Path | None) -> int:
    results = load_results()
    if not results:
        print("No measured cases yet.")
        return 1

    lines = [
        "# Prediction accuracy (phase 5b)",
        "",
        f"- **Cases:** {len(results)} of {len(CONDITIONS) * len(MODELS) * len(TARGETS)}",
        "",
        "> Each case applies **suggestion 1** of **repetition 1** under the "
        "narrowest possible interpretation. Cases whose behaviour tests fail "
        "are marked `broken`: their metric delta is void.",
        "",
        "| Condition | Model | Target | Status | Hits | Misses | Unverifiable | Accuracy |",
        "|---|---|---|---|---|---|---|---|",
    ]

    valid_hits = valid_total = 0
    per_condition: dict[str, list[int]] = {}
    per_metric: dict[str, list[int]] = {}

    for result in results:
        predictions = result["predictions"]
        accuracy = predictions["accuracy"]
        shown = "n/a" if accuracy is None else f"{accuracy:.0%}"
        if result["status"] == "ok":
            hits = predictions["hits"]
            total = hits + predictions["misses"]
            valid_hits += hits
            valid_total += total
            bucket = per_condition.setdefault(result["condition"], [0, 0])
            bucket[0] += total
            bucket[1] += hits
            for score in predictions["suggestions"]:
                for check in score["checks"]:
                    if check["outcome"] == "unverifiable":
                        continue
                    metric = per_metric.setdefault(check["metric"], [0, 0])
                    metric[0] += 1
                    metric[1] += check["outcome"] == "hit"

        lines.append(
            f"| {result['condition']} | `{result['model']}` | "
            f"`{result['target'].split(':')[-1]}` | {result['status']} | "
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
        "## By condition (H2)",
        "",
        "Does telling the model how the metrics are computed improve its predictions about them?",
        "",
        "| Condition | Predictions | Correct | Accuracy |",
        "|---|---|---|---|",
    ]
    for condition in CONDITIONS:
        if condition not in per_condition:
            continue
        total, hits = per_condition[condition]
        rate = f"{hits / total:.0%}" if total else "n/a"
        lines.append(f"| {condition} | {total} | {hits} | {rate} |")

    lines += [
        "",
        "## Per metric",
        "",
        "Reported per metric first; the subtractive / residue-dependent "
        "grouping is a hypothesis, not a taxonomy "
        "(`docs/SPEC-duzeltme-2.5.md`).",
        "",
        "| Metric | Predicted | Correct | Accuracy |",
        "|---|---|---|---|",
    ]
    for metric, (total, hits) in sorted(per_metric.items()):
        lines.append(f"| {metric} | {total} | {hits} | {hits / total:.0%} |")

    closed = [
        (r, r["delta"]["violations"])
        for r in results
        if r["delta"]["violations"]["removed"] or r["delta"]["violations"]["added"]
    ]
    if closed:
        lines += [
            "",
            "## Violation closure",
            "",
            "A suggestion can name the right layer and still leave the import "
            "in place. This is what v1 could not ask.",
            "",
        ]
        for result, violations in closed:
            short = result["target"].split(":")[-1]
            model = result["model"].split("/")[-1]
            label = f"`{short}` — {model}, {result['condition']}"
            lines.append(f"**{label}**")
            for item in violations["removed"]:
                lines.append(f"- closed: {item}")
            for item in violations["added"]:
                lines.append(f"- opened: {item}")
            net = len(violations["added"]) - len(violations["removed"])
            verdict = "no net change" if net == 0 else f"net {net:+d}"
            lines.append(f"- **{verdict}**")
            lines.append("")

    suspicious = [r for r in results if r["goodhart"]["suspicious_count"]]
    broken = [r for r in results if r["status"] != "ok"]
    if suspicious or broken:
        lines += ["", "## Flagged cases", ""]
        for result in broken:
            lines.append(
                f"- **broken:** `{result['model']}` / "
                f"`{result['target'].split(':')[-1]}` — "
                f"{result['behaviour_tests_summary']}"
            )
        for result in suspicious:
            lines.append(
                f"- **suspicious:** `{result['model']}` / `{result['target'].split(':')[-1]}`"
            )

    lines += [
        "",
        "## Calibration",
        "",
        "Brier is the mean squared error of the stated confidence: 0 is "
        "perfect, **0.25 is what a coin flip scores**, and above that the "
        "confidence is worse than useless. ECE averages the gap between "
        "stated and actual over confidence buckets.",
        "",
        "| Condition | Predictions | Brier | ECE | Stated | Actual | Gap |",
        "|---|---|---|---|---|---|---|",
    ]
    for condition in (*CONDITIONS, "all"):
        report = collect_calibration(results, None if condition == "all" else condition)
        if not report.points:
            continue
        lines.append(
            f"| {condition} | {report.count} | {report.brier:.3f} | "
            f"{report.ece:.3f} | {report.mean_confidence:.2f} | "
            f"{report.accuracy:.2f} | {report.overconfidence:+.2f} |"
        )

    pooled = collect_calibration(results, None)
    if pooled.points:
        lines += [
            "",
            "Where the confidence sits, and whether it is earned.",
            "",
            "| Confidence | Predictions | Stated | Actual | Gap |",
            "|---|---|---|---|---|",
        ]
        for bucket in pooled.bins:
            if not bucket.count:
                continue
            lines.append(
                f"| {bucket.low:.1f}–{bucket.high:.1f} | {bucket.count} | "
                f"{bucket.mean_confidence:.2f} | {bucket.accuracy:.2f} | "
                f"{bucket.gap:+.2f} |"
            )
        if pooled.without_confidence:
            lines.append("")
            lines.append(
                f"{pooled.without_confidence} prediction(s) came without a "
                f"confidence and are excluded."
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

    for name, helptext in (
        ("prepare", "Copy the fixture and show the suggestion."),
        ("measure", "Run tests, re-measure, score the prediction."),
    ):
        step = sub.add_parser(name, help=helptext)
        step.add_argument("--condition", required=True, choices=CONDITIONS)
        step.add_argument("--model", required=True)
        step.add_argument("--target", required=True)
        if name == "prepare":
            step.add_argument("--repetition", type=int, default=PROTOCOL_REPETITION)
        else:
            step.add_argument("--applied", type=int, nargs="+", required=True)

    listing = sub.add_parser("cases", help="List the 12 cases and their state.")
    listing.add_argument("--noop", action="store_true", help=argparse.SUPPRESS)

    summary = sub.add_parser("summarise", help="Aggregate every measured case.")
    summary.add_argument("--out", type=Path, default=None)

    args = parser.parse_args()

    if args.command == "prepare":
        return prepare(args.condition, args.model, args.target, args.repetition)
    if args.command == "measure":
        return measure(args.condition, args.model, args.target, args.applied)
    if args.command == "cases":
        for condition in CONDITIONS:
            for model in MODELS:
                for target in TARGETS:
                    path = case_dir(condition, model, target)
                    if (path / "result.json").is_file():
                        state = "measured"
                    elif path.is_dir():
                        state = "prepared"
                    else:
                        state = "-"
                    print(f"{state:<10}{condition:<12}{model:<24}{target}")
        return 0
    return summarise(args.out)


if __name__ == "__main__":
    raise SystemExit(main())
