"""RefactorLens komut satırı arayüzü.

Bu modül **yalnızca arayüzdür**: argümanları okur, config'i yükler, iş
mantığını çağırır ve sonucu sunar. Tarama akışı `analysis.scanner`, çıktı
biçimlendirme `report` paketi içindedir. Sınır böyle çizildiği için metrikler
CLI'dan bağımsız test edilebilir.

Komut kümesi tamamdır: `scan` ölçer, `advise` önerir, `verify` önerinin
etkisini ve modelin tahmininin isabetini denetler.
"""

from __future__ import annotations

import io
import json
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from rlens import __version__
from rlens.advise.advisor import AdviceDocument, request_advice
from rlens.advise.context import build_context, context_budget
from rlens.advise.prompts import SYSTEM_INSTRUCTION, build_user_prompt
from rlens.advise.selector import select_targets
from rlens.analysis.architecture import analyse_project
from rlens.analysis.model import SCHEMA_VERSION
from rlens.analysis.scanner import scan_project, scan_project_with_sources
from rlens.apply.prompts import SYSTEM_INSTRUCTION as APPLY_SYSTEM_INSTRUCTION
from rlens.apply.runner import preview_chartests, preview_prompt, run_apply, run_chartests_only
from rlens.apply.worktree import ApplyError
from rlens.bench.report import load_results, report_markdown
from rlens.bench.runner import estimate_calls, plan, run_bench
from rlens.bench.suite import BenchError, load_suite
from rlens.chartests.generator import SYSTEM_INSTRUCTION as CHARTESTS_SYSTEM_INSTRUCTION
from rlens.config import ConfigError, load_config
from rlens.diff.baseline import BASELINE_FILE, findings, write_baseline
from rlens.diff.compare import run_diff
from rlens.diff.git_refs import parse_range
from rlens.diff.pr_comment import pr_comment
from rlens.explain.explainer import request_explanation
from rlens.explain.prompts import SYSTEM_INSTRUCTION as EXPLAIN_SYSTEM_INSTRUCTION
from rlens.explain.prompts import build_user_prompt as build_explain_prompt
from rlens.explain.template import translate
from rlens.llm.budget import Budget, BudgetExceeded
from rlens.llm.cache import ResponseCache, prompt_hash
from rlens.loop.runner import preview_loop_prompt, run_loop
from rlens.providers import PROVIDERS, ProviderError, get_provider, load_env_file
from rlens.providers.base import ProviderTruncated
from rlens.report.advice import render_advice
from rlens.report.apply import chartests_line, render_apply
from rlens.report.architecture import render_architecture
from rlens.report.explain import render_explanation, render_template
from rlens.report.files import (
    ReportError,
    latest_report,
    read_report,
    verify_payload,
    write_advice,
    write_apply,
    write_arch,
    write_chartests,
    write_explain,
    write_explain_template,
    write_loop,
    write_report,
    write_verify,
)
from rlens.report.loop import render_loop
from rlens.report.terminal import render_report
from rlens.report.verify import render_verify, verify_markdown
from rlens.verify import goodhart as goodhart_module
from rlens.verify.calibration import collect_points
from rlens.verify.diff import REGRESSED, diff_reports
from rlens.verify.prediction import check_predictions, parse_applied

app = typer.Typer(
    name="rlens",
    help="Metric-grounded AI code review for Python codebases.",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()
err_console = Console(stderr=True)

# Çıkış kodu sözleşmesi:
#   0 = başarı
#   1 = kullanıcı/ortam hatası (geçersiz config, yazılamayan rapor, --fail-on-violation)
#   2 = click/typer'a ayrılmıştır: hatalı kullanım, eksik/geçersiz argüman
#   3 = komut henüz uygulanmadı
# 3 ayrı tutulur; 2 kullanılsaydı "böyle bir klasör yok" ile "komut hazır değil"
# birbirinden ayırt edilemezdi.
NOT_IMPLEMENTED_EXIT = 3


def _version_string() -> str:
    return f"rlens {__version__} (report schema v{SCHEMA_VERSION})"


def _version_callback(value: bool) -> None:
    if value:
        console.print(_version_string())
        raise typer.Exit()


@app.callback()
def main_callback(
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Print the package version and report schema version, then exit.",
        ),
    ] = False,
) -> None:
    """RefactorLens: metric-grounded AI code review."""


def _fail(message: str) -> typer.Exit:
    err_console.print(f"[bold red]Error:[/] {message}")
    return typer.Exit(code=1)


#: `--format` seçeneği. Yalnızca dosyaya zaten yazılan raporlar stdout'a
#: verilir; yeni bir hesaplama ya da yeni bir biçim yoktur (sertleştirme Blok 5).
FORMAT_HELP = "What to print on stdout: the tables, or the report itself."


def _check_format(value: str, allowed: tuple[str, ...], command: str) -> None:
    if value not in allowed:
        choices = ", ".join(allowed[:-1]) + f" or {allowed[-1]}"
        raise _fail(f"`rlens {command}` supports --format {choices}; got {value!r}.")


def _status(output_format: str) -> Console:
    """Durum mesajları: tabloyla birlikte stdout'a, aksi halde stderr'e.

    JSON ya da markdown basılırken stdout yalnızca yükü taşımalı; `Report: ...`
    satırı araya girerse `rlens scan . --format json | jq` bozulur.
    """
    return console if output_format == "table" else err_console


def _emit(text: str) -> None:
    """Yükü stdout'a düz metin ve UTF-8 olarak yazar.

    rich kullanılmaz: köşeli parantezi biçim etiketi sanar ve satırı sarar.
    UTF-8 zorunlu: Windows'ta yönlendirilen stdout'un kodlaması `→` gibi
    karakterleri taşımaz.
    """
    data = text if text.endswith("\n") else text + "\n"
    sys.stdout.flush()
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        sys.stdout.write(data)
        return
    buffer.write(data.encode("utf-8"))
    buffer.flush()


def _quiet_count(render, *args) -> int:
    """Tablo basmadan ihlal sayısını alır; `--fail-on-violation` biçimden bağımsızdır."""
    return render(*args, Console(file=io.StringIO()))


@app.command()
def scan(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Project directory to analyse.",
        ),
    ],
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            exists=True,
            dir_okay=False,
            help="Path to rlens.yaml. If omitted, searched upward from the target directory.",
        ),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Report directory (overrides the config)."),
    ] = None,
    no_report: Annotated[
        bool,
        typer.Option("--no-report", help="Skip the JSON report and only print the tables."),
    ] = False,
    no_arch: Annotated[
        bool,
        typer.Option(
            "--no-arch",
            help=(
                "Skip layer analysis and violations. Smell labels and the "
                "public interface are still computed."
            ),
        ),
    ] = False,
    fail_on_violation: Annotated[
        bool,
        typer.Option(
            "--fail-on-violation",
            help="Exit with code 1 if anything is over threshold (useful in CI).",
        ),
    ] = False,
    output_format: Annotated[
        str, typer.Option("--format", help=f"{FORMAT_HELP} table or json.")
    ] = "table",
) -> None:
    """Scan a project, print the metric tables and write a JSON report."""
    _check_format(output_format, ("table", "json"), "scan")
    try:
        cfg = load_config(config, search_from=path)
    except ConfigError as exc:
        raise _fail(str(exc)) from exc

    report = scan_project(path, cfg, no_arch=no_arch)
    if output_format == "table":
        violations = render_report(report, cfg, console)
    else:
        violations = _quiet_count(lambda c: render_report(report, cfg, c))
        _emit(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))

    if not no_report and report.modules:
        target = Path(output_dir) if output_dir else path / cfg.scan.output_dir
        try:
            written = write_report(report, target)
        except ReportError as exc:
            raise _fail(str(exc)) from exc
        _status(output_format).print(f"[dim]Report: {written}[/dim]")

    if fail_on_violation and violations:
        raise typer.Exit(code=1)


@app.command()
def arch(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Project directory to analyse.",
        ),
    ],
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", exists=True, dir_okay=False, help="Path to rlens.yaml."),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Report directory (overrides the config)."),
    ] = None,
    no_report: Annotated[
        bool,
        typer.Option("--no-report", help="Skip the JSON report and only print the tables."),
    ] = False,
    fail_on_violation: Annotated[
        bool,
        typer.Option(
            "--fail-on-violation",
            help="Exit with code 1 if there is a non-tentative violation (useful in CI).",
        ),
    ] = False,
    output_format: Annotated[
        str, typer.Option("--format", help=f"{FORMAT_HELP} table or json.")
    ] = "table",
) -> None:
    """Map layers, list architecture violations and module coupling."""
    _check_format(output_format, ("table", "json"), "arch")
    try:
        cfg = load_config(config, search_from=path)
    except ConfigError as exc:
        raise _fail(str(exc)) from exc

    result = analyse_project(path, cfg)
    if output_format == "table":
        blocking = render_architecture(result, console)
    else:
        blocking = _quiet_count(lambda c: render_architecture(result, c))
        _emit(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    if not no_report and result.report.assignments:
        target = Path(output_dir) if output_dir else path / cfg.scan.output_dir
        try:
            written = write_arch(result, target)
        except ReportError as exc:
            raise _fail(str(exc)) from exc
        _status(output_format).print(f"[dim]Report: {written}[/dim]")

    if fail_on_violation and blocking:
        raise typer.Exit(code=1)


@app.command()
def advise(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Project directory to analyse.",
        ),
    ],
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            exists=True,
            dir_okay=False,
            help="Path to rlens.yaml. If omitted, searched upward from the target directory.",
        ),
    ] = None,
    top_n: Annotated[
        int | None,
        typer.Option("--top-n", "-n", min=1, help="How many targets to ask about."),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help="Override the configured provider."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Override the configured model name."),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Report directory (overrides the config)."),
    ] = None,
    no_report: Annotated[
        bool,
        typer.Option("--no-report", help="Skip the report files and only print to the terminal."),
    ] = False,
    no_arch_context: Annotated[
        bool,
        typer.Option(
            "--no-arch-context",
            help="Drop the architectural context block from the prompt (A/B).",
        ),
    ] = False,
    metric_rules: Annotated[
        bool,
        typer.Option(
            "--metric-rules",
            help="Add the metric computation rules to the prompt (A/B).",
        ),
    ] = False,
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Ignore the response cache and always call."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Print the prompt that would be sent and stop. Needs no API key.",
        ),
    ] = False,
) -> None:
    """Ask an LLM for refactoring advice, grounded in the measured metrics."""
    try:
        cfg = load_config(config, search_from=path)
    except ConfigError as exc:
        raise _fail(str(exc)) from exc

    if provider is not None:
        if provider not in PROVIDERS:
            raise _fail(
                f"Unknown provider '{provider}'. Available: {', '.join(sorted(PROVIDERS))}."
            )
        cfg = replace(cfg, provider=replace(cfg.provider, name=provider))
    if model is not None:
        cfg = replace(cfg, provider=replace(cfg.provider, model=model))

    result = scan_project_with_sources(path, cfg)
    targets = select_targets(result.report, cfg, top_n)

    if not targets:
        console.print(
            "[green]Nothing over threshold.[/] "
            "There is nothing to ask about — run `rlens scan` to see the measurements."
        )
        return

    contexts = []
    for target in targets:
        try:
            contexts.append(
                build_context(target, result.modules, result.project_classes, context_budget(cfg))
            )
        except LookupError as exc:
            err_console.print(f"[yellow]Skipping {target.qualified_name}:[/] {exc}")

    if not contexts:
        raise _fail("None of the selected targets could be located in the source.")

    # Mimari bağlam yalnızca katmanlar biliniyorsa anlamlıdır; bilinmiyorsa
    # blok zaten üretilmez (bkz. prompts.format_architecture).
    scheme = None if no_arch_context or cfg.arch is None else cfg.arch.scheme

    cache = _build_cache(cfg, path, disabled=no_cache)
    budget = Budget(cfg.budget)

    if dry_run:
        _render_dry_run_summary(contexts, cfg, cache, budget, scheme, metric_rules)
        for context in contexts:
            console.print(f"\n[bold cyan]{context.target.qualified_name}[/bold cyan]")
            console.print(f"[dim]~{context.estimated_tokens} tokens[/dim]\n")
            # markup=False zorunlu: rich köşeli parantezi biçim etiketi sanar ve
            # `self._orders[key]` ifadesindeki `[key]` kısmını yutar. --dry-run'ın
            # tek amacı modele ne gideceğini göstermek olduğu için, gösterilen
            # metnin gönderilenle birebir aynı olması gerekir.
            console.print("[dim]--- system ---[/dim]")
            console.print(SYSTEM_INSTRUCTION, markup=False, highlight=False)
            console.print("[dim]--- user ---[/dim]")
            console.print(
                build_user_prompt(context, scheme=scheme, metric_rules=metric_rules),
                markup=False,
                highlight=False,
            )
        return

    # `.env` yalnızca gerçekten çağrı yapılacaksa okunur; --dry-run anahtarsız çalışır.
    load_env_file(path)

    try:
        adapter = get_provider(cfg.provider)
    except ProviderError as exc:
        raise _fail(str(exc)) from exc

    document = AdviceDocument(
        root=str(Path(path).resolve()),
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        rlens_version=__version__,
        provider=cfg.provider.name,
        model=cfg.provider.model,
        temperature=cfg.advise.temperature,
    )

    for context in contexts:
        name = context.target.qualified_name
        if not budget.fits(context.estimated_tokens):
            err_console.print(
                f"[yellow]Skipping {name}:[/] the prompt is about "
                f"{context.estimated_tokens} tokens, over "
                f"`budget.max_tokens_per_call` ({cfg.budget.max_tokens_per_call})."
            )
            budget.skipped.append(name)
            continue

        console.print(f"[dim]asking about {name}…[/dim]")
        try:
            advice, warnings = request_advice(adapter, context, cfg, cache=cache, budget=budget)
        except BudgetExceeded as exc:
            # Planlı duruş: kalan hedefler atlanır ve rapor kısmi olduğunu söyler.
            err_console.print(f"[yellow]{exc}[/]")
            budget.skipped.extend(
                c.target.qualified_name for c in contexts[contexts.index(context) :]
            )
            break
        except ProviderTruncated as exc:
            # Kesilme bizim çıktı sınırımızdır, modelin sözleşme ihlali değil:
            # yarım yanıt `unstructured` diye kaydedilmez, hedef atlanır.
            err_console.print(f"[yellow]Skipping {name}:[/] {exc}")
            budget.skipped.append(name)
            continue
        except ProviderError as exc:
            raise _fail(str(exc)) from exc
        advice.warnings = warnings
        document.advices.append(advice)

    document.budget = budget.summary()
    document.cache = cache.summary()
    document.partial = bool(budget.skipped)

    console.print()
    render_advice(document, console)
    console.print(f"[dim]{budget.describe()} · {cache.describe()}[/dim]")
    if document.partial:
        console.print(
            f"[yellow]Partial report:[/] {len(budget.skipped)} target(s) were not asked about."
        )

    if not no_report:
        target_dir = Path(output_dir) if output_dir else path / cfg.scan.output_dir
        try:
            json_path, markdown_path = write_advice(document, target_dir)
        except ReportError as exc:
            raise _fail(str(exc)) from exc
        console.print(f"[dim]Report: {markdown_path}[/dim]")
        console.print(f"[dim]Machine-readable: {json_path}[/dim]")


@app.command()
def explain(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Project directory to read measurements from.",
        ),
    ],
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            exists=True,
            dir_okay=False,
            help="Path to rlens.yaml. If omitted, searched upward from the target directory.",
        ),
    ] = None,
    report: Annotated[
        Path | None,
        typer.Option(
            "--report",
            "-r",
            exists=True,
            dir_okay=False,
            help="Scan report to interpret. If omitted, the project is measured now.",
        ),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help="Override the configured provider."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Override the configured model name."),
    ] = None,
    max_classes: Annotated[
        int,
        typer.Option("--max-classes", min=1, help="How many classes to put in the prompt."),
    ] = 25,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Report directory (overrides the config)."),
    ] = None,
    no_report: Annotated[
        bool,
        typer.Option("--no-report", help="Skip the report files and only print to the terminal."),
    ] = False,
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Ignore the response cache and always call."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Print the prompt that would be sent and stop. Needs no API key.",
        ),
    ] = False,
    no_llm: Annotated[
        bool,
        typer.Option(
            "--no-llm",
            help="Translate the measurements with fixed templates. Calls no model.",
        ),
    ] = False,
) -> None:
    """Read the measurements back: what the metrics describe, with no advice."""
    if no_llm and dry_run:
        raise _fail("--no-llm sends no prompt, so --dry-run has nothing to show. Use one.")

    try:
        cfg = load_config(config, search_from=path)
    except ConfigError as exc:
        raise _fail(str(exc)) from exc

    if provider is not None:
        if provider not in PROVIDERS:
            raise _fail(
                f"Unknown provider '{provider}'. Available: {', '.join(sorted(PROVIDERS))}."
            )
        cfg = replace(cfg, provider=replace(cfg.provider, name=provider))
    if model is not None:
        cfg = replace(cfg, provider=replace(cfg.provider, model=model))

    if report is not None:
        try:
            payload = read_report(Path(report))
        except ReportError as exc:
            raise _fail(str(exc)) from exc
    else:
        payload = scan_project_with_sources(path, cfg).report.to_dict()

    if no_llm:
        # Şablon katmanı: sağlayıcı, anahtar, önbellek ve bütçe yok. Çıktısı
        # hiçbir prompt'a girmez (`docs/v2.1-explain.md` Blok 2).
        reading = translate(payload, cfg)
        console.print()
        render_template(reading, console)
        if not no_report:
            target_dir = Path(output_dir) if output_dir else path / cfg.scan.output_dir
            try:
                json_path, markdown_path = write_explain_template(
                    reading,
                    target_dir,
                    root=str(Path(path).resolve()),
                    generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
                )
            except ReportError as exc:
                raise _fail(str(exc)) from exc
            console.print(f"[dim]Report: {markdown_path}[/dim]")
            console.print(f"[dim]Machine-readable: {json_path}[/dim]")
        return

    if not any(module.get("classes") for module in payload.get("modules", [])):
        console.print(
            "[yellow]No classes were measured.[/] "
            "There is nothing to read back — check `scan.include` or run `rlens scan` first."
        )
        return

    if dry_run:
        # markup=False zorunlu: rich köşeli parantezi biçim etiketi sanar ve
        # gösterilen prompt gönderilenden farklı olur. --dry-run'ın tek amacı
        # ikisinin aynı olduğunu göstermek.
        console.print("[dim]--- system ---[/dim]")
        console.print(EXPLAIN_SYSTEM_INSTRUCTION, markup=False, highlight=False)
        console.print("[dim]--- user ---[/dim]")
        console.print(
            build_explain_prompt(payload, max_classes=max_classes),
            markup=False,
            highlight=False,
        )
        return

    # `.env` yalnızca gerçekten çağrı yapılacaksa okunur; --dry-run anahtarsız çalışır.
    load_env_file(path)

    try:
        adapter = get_provider(cfg.provider)
    except ProviderError as exc:
        raise _fail(str(exc)) from exc

    cache = _build_cache(cfg, path, disabled=no_cache)
    budget = Budget(cfg.budget)

    try:
        explanation, warnings = request_explanation(
            adapter, payload, cfg, cache=cache, budget=budget, max_classes=max_classes
        )
    except BudgetExceeded as exc:
        raise _fail(str(exc)) from exc
    except ProviderError as exc:
        raise _fail(str(exc)) from exc

    console.print()
    render_explanation(explanation, console)
    for warning in warnings:
        err_console.print(f"[yellow]{warning}[/]")

    if not no_report:
        target_dir = Path(output_dir) if output_dir else path / cfg.scan.output_dir
        try:
            json_path, markdown_path = write_explain(
                explanation,
                target_dir,
                root=str(Path(path).resolve()),
                generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            )
        except ReportError as exc:
            raise _fail(str(exc)) from exc
        console.print(f"[dim]Report: {markdown_path}[/dim]")
        console.print(f"[dim]Machine-readable: {json_path}[/dim]")


@app.command()
def verify(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Project directory to re-measure.",
        ),
    ],
    before: Annotated[
        Path | None,
        typer.Option(
            "--before",
            "-b",
            exists=True,
            dir_okay=False,
            help="Baseline scan report. Defaults to the most recent one.",
        ),
    ] = None,
    advice: Annotated[
        Path | None,
        typer.Option(
            "--advice",
            "-a",
            exists=True,
            dir_okay=False,
            help="Advice JSON. If given, the model's predictions are checked.",
        ),
    ] = None,
    applied: Annotated[
        list[str] | None,
        typer.Option(
            "--applied",
            help='Which suggestions you applied, e.g. "god:OrderManager=1". '
            "Repeatable. Without it, every suggestion is scored.",
        ),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", exists=True, dir_okay=False, help="Path to rlens.yaml."),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Report directory (overrides the config)."),
    ] = None,
    no_report: Annotated[
        bool,
        typer.Option("--no-report", help="Skip the report files and only print to the terminal."),
    ] = False,
    fail_on_regression: Annotated[
        bool,
        typer.Option(
            "--fail-on-regression",
            help="Exit with code 1 if anything regressed (useful in CI).",
        ),
    ] = False,
    output_format: Annotated[
        str, typer.Option("--format", help=f"{FORMAT_HELP} table, json or markdown.")
    ] = "table",
) -> None:
    """Re-measure after a change and check whether the model's predictions held."""
    _check_format(output_format, ("table", "json", "markdown"), "verify")
    try:
        cfg = load_config(config, search_from=path)
    except ConfigError as exc:
        raise _fail(str(exc)) from exc

    report_dir = Path(output_dir) if output_dir else path / cfg.scan.output_dir

    baseline_path = before
    if baseline_path is None:
        baseline_path = latest_report(report_dir)
        if baseline_path is None:
            raise _fail(
                f"No baseline report found in {report_dir}. "
                f"Run `rlens scan {path}` before making changes, or pass --before."
            )
        _status(output_format).print(f"[dim]baseline: {baseline_path}[/dim]")

    try:
        baseline = read_report(baseline_path)
    except ReportError as exc:
        raise _fail(str(exc)) from exc

    current = scan_project(path, cfg).to_dict()
    delta = diff_reports(baseline, current)

    suspicions = goodhart_module.detect(baseline, current, delta.entities)

    predictions = None
    calibration = None
    if advice is not None:
        try:
            advice_document = json.loads(Path(advice).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise _fail(f"Could not read the advice file: {exc}") from exc
        try:
            applied_map = parse_applied(applied) if applied else None
        except ValueError as exc:
            raise _fail(str(exc)) from exc
        predictions = check_predictions(advice_document, delta, applied_map)
        calibration = collect_points(predictions)

    if output_format == "table":
        render_verify(delta, console, predictions, suspicions, calibration)
    elif output_format == "json":
        payload = verify_payload(delta, predictions, suspicions, calibration)
        _emit(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _emit(verify_markdown(delta, predictions, suspicions, calibration))

    if not no_report:
        try:
            json_path, markdown_path = write_verify(
                delta, predictions, report_dir, suspicions, calibration
            )
        except ReportError as exc:
            raise _fail(str(exc)) from exc
        _status(output_format).print(f"[dim]Report: {markdown_path}[/dim]")
        _status(output_format).print(f"[dim]Machine-readable: {json_path}[/dim]")

    # Karşılaştırma geçersizse regresyon kontrolü yapılmaz: anlamsız sayılara
    # dayanarak derlemeyi kırmak, sessizce yanlış delta üretmek kadar zararlı.
    regressed = any(entity.summarise() == REGRESSED for entity in delta.entities)

    # Şüpheli iyileşmenin CI'ı kırıp kırmayacağı bir politika sorusudur:
    # ölü kod silmek de arayüzü küçültür. Varsayılan sıkı, config gevşetebilir.
    treat_suspicious = cfg.verify is not None and cfg.verify.treat_suspicious_as_regression
    blocking = regressed or (treat_suspicious and suspicions.any_suspicious)

    if fail_on_regression and delta.comparable and blocking:
        raise typer.Exit(code=1)


@app.command()
def apply(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Project directory, inside a git repository.",
        ),
    ],
    advice: Annotated[
        Path,
        typer.Option(
            "--advice", "-a", exists=True, dir_okay=False, help="Advice JSON from `rlens advise`."
        ),
    ],
    target: Annotated[
        str | None,
        typer.Option("--target", "-t", help="Which target in the advice file (module:Name)."),
    ] = None,
    suggestion: Annotated[
        int, typer.Option("--suggestion", "-s", min=1, help="Which suggestion of that target.")
    ] = 1,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", exists=True, dir_okay=False, help="Path to rlens.yaml."),
    ] = None,
    provider: Annotated[
        str | None, typer.Option("--provider", "-p", help="Override the configured provider.")
    ] = None,
    model: Annotated[
        str | None, typer.Option("--model", "-m", help="Override the configured model name.")
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Report directory (overrides the config)."),
    ] = None,
    no_report: Annotated[bool, typer.Option("--no-report", help="Skip the report files.")] = False,
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="Ignore the response cache and always call.")
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print the patch request and stop. Needs no API key."),
    ] = False,
) -> None:
    """Apply one suggestion on a separate git branch, gated by your own tests."""
    try:
        cfg = load_config(config, search_from=path)
    except ConfigError as exc:
        raise _fail(str(exc)) from exc
    if provider is not None:
        if provider not in PROVIDERS:
            raise _fail(
                f"Unknown provider '{provider}'. Available: {', '.join(sorted(PROVIDERS))}."
            )
        cfg = replace(cfg, provider=replace(cfg.provider, name=provider))
    if model is not None:
        cfg = replace(cfg, provider=replace(cfg.provider, model=model))

    try:
        document = json.loads(Path(advice).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _fail(f"Could not read the advice file: {exc}") from exc
    targets = [entry.get("target", "") for entry in document.get("advices", [])]
    if target is None:
        if len(targets) != 1:
            raise _fail(
                f"The advice file has {len(targets)} targets; "
                f"pick one with --target ({', '.join(targets)})."
            )
        target = targets[0]

    try:
        if dry_run:
            console.print("[dim]--- system ---[/dim]")
            console.print(APPLY_SYSTEM_INSTRUCTION, markup=False, highlight=False)
            console.print("[dim]--- user ---[/dim]")
            prompt = preview_prompt(path, document, target, suggestion, cfg)
            console.print(prompt, markup=False, highlight=False)
            return

        load_env_file(path)
        adapter = get_provider(cfg.provider)
        result = run_apply(
            path,
            document,
            target,
            suggestion,
            cfg,
            adapter,
            cache=_build_cache(cfg, path, disabled=no_cache),
            budget=Budget(cfg.budget),
        )
    except ApplyError as exc:
        raise _fail(str(exc)) from exc
    except (ProviderError, BudgetExceeded) as exc:
        raise _fail(str(exc)) from exc

    render_apply(result, console)
    if not no_report:
        target_dir = Path(output_dir) if output_dir else path / cfg.scan.output_dir
        try:
            json_path, markdown_path = write_apply(
                result,
                target_dir,
                root=str(Path(path).resolve()),
                generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            )
        except ReportError as exc:
            raise _fail(str(exc)) from exc
        console.print(f"[dim]Report: {markdown_path}[/dim]")
        console.print(f"[dim]Machine-readable: {json_path}[/dim]")


@app.command()
def chartests(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Project directory, inside a git repository.",
        ),
    ],
    target: Annotated[
        str, typer.Option("--target", "-t", help="Class to characterize (module:Name).")
    ],
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", exists=True, dir_okay=False, help="Path to rlens.yaml."),
    ] = None,
    provider: Annotated[
        str | None, typer.Option("--provider", "-p", help="Override the configured provider.")
    ] = None,
    model: Annotated[
        str | None, typer.Option("--model", "-m", help="Override the configured model name.")
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Report directory (overrides the config)."),
    ] = None,
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="Ignore the response cache and always call.")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Print the request and stop. Needs no API key.")
    ] = False,
) -> None:
    """Write tests that pin down what a class does today, kept only if they pass."""
    try:
        cfg = load_config(config, search_from=path)
    except ConfigError as exc:
        raise _fail(str(exc)) from exc
    if provider is not None:
        if provider not in PROVIDERS:
            raise _fail(
                f"Unknown provider '{provider}'. Available: {', '.join(sorted(PROVIDERS))}."
            )
        cfg = replace(cfg, provider=replace(cfg.provider, name=provider))
    if model is not None:
        cfg = replace(cfg, provider=replace(cfg.provider, model=model))

    try:
        if dry_run:
            console.print("[dim]--- system ---[/dim]")
            console.print(CHARTESTS_SYSTEM_INSTRUCTION, markup=False, highlight=False)
            console.print("[dim]--- user ---[/dim]")
            console.print(preview_chartests(path, target, cfg), markup=False, highlight=False)
            return
        load_env_file(path)
        adapter = get_provider(cfg.provider)
        result = run_chartests_only(
            path,
            target,
            cfg,
            adapter,
            cache=_build_cache(cfg, path, disabled=no_cache),
            budget=Budget(cfg.budget),
        )
    except ApplyError as exc:
        raise _fail(str(exc)) from exc
    except (ProviderError, BudgetExceeded) as exc:
        raise _fail(str(exc)) from exc

    console.print(chartests_line(result.to_dict()))
    target_dir = Path(output_dir) if output_dir else path / cfg.scan.output_dir
    try:
        test_path, json_path = write_chartests(result, target, target_dir)
    except ReportError as exc:
        raise _fail(str(exc)) from exc
    if result.code:
        console.print(f"Tests: {test_path} — review them, then move them into your test suite.")
    console.print(f"[dim]Machine-readable: {json_path}[/dim]")


@app.command()
def loop(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Project directory, inside a git repository.",
        ),
    ],
    target: Annotated[
        str, typer.Option("--target", "-t", help="Class or function to work on (module:Name).")
    ],
    max_iter: Annotated[
        int | None,
        typer.Option("--max-iter", min=1, help="Most iterations (overrides loop.max_iter)."),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", exists=True, dir_okay=False, help="Path to rlens.yaml."),
    ] = None,
    provider: Annotated[
        str | None, typer.Option("--provider", "-p", help="Override the configured provider.")
    ] = None,
    model: Annotated[
        str | None, typer.Option("--model", "-m", help="Override the configured model name.")
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Report directory (overrides the config)."),
    ] = None,
    no_report: Annotated[bool, typer.Option("--no-report", help="Skip the report files.")] = False,
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="Ignore the response cache and always call.")
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print the first advice request and stop. Needs no key."),
    ] = False,
) -> None:
    """Advise, apply and verify in a loop, feeding each result back to the model."""
    try:
        cfg = load_config(config, search_from=path)
    except ConfigError as exc:
        raise _fail(str(exc)) from exc
    if provider is not None:
        if provider not in PROVIDERS:
            raise _fail(
                f"Unknown provider '{provider}'. Available: {', '.join(sorted(PROVIDERS))}."
            )
        cfg = replace(cfg, provider=replace(cfg.provider, name=provider))
    if model is not None:
        cfg = replace(cfg, provider=replace(cfg.provider, model=model))

    try:
        if dry_run:
            console.print("[dim]--- system ---[/dim]")
            console.print(SYSTEM_INSTRUCTION, markup=False, highlight=False)
            console.print("[dim]--- user ---[/dim]")
            console.print(preview_loop_prompt(path, target, cfg), markup=False, highlight=False)
            return
        load_env_file(path)
        adapter = get_provider(cfg.provider)
        result = run_loop(
            path,
            target,
            cfg,
            adapter,
            max_iter=max_iter,
            cache=_build_cache(cfg, path, disabled=no_cache),
            budget=Budget(cfg.budget),
        )
    except ApplyError as exc:
        raise _fail(str(exc)) from exc
    except ProviderError as exc:
        raise _fail(str(exc)) from exc

    render_loop(result, console)
    if not no_report:
        target_dir = Path(output_dir) if output_dir else path / cfg.scan.output_dir
        try:
            json_path, markdown_path = write_loop(
                result,
                target_dir,
                root=str(Path(path).resolve()),
                generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            )
        except ReportError as exc:
            raise _fail(str(exc)) from exc
        console.print(f"[dim]Report: {markdown_path}[/dim]")
        console.print(f"[dim]Machine-readable: {json_path}[/dim]")


FAIL_ON = ("none", "regression", "new-violation")


@app.command("diff")
def diff_command(
    revisions: Annotated[
        str, typer.Argument(help="Range to compare, e.g. origin/main..HEAD (base..head).")
    ],
    path: Annotated[
        Path,
        typer.Option(
            "--path",
            exists=True,
            file_okay=False,
            dir_okay=True,
            help="Directory to scan on both sides, inside the repository.",
        ),
    ] = Path("."),
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", exists=True, dir_okay=False, help="Path to rlens.yaml."),
    ] = None,
    output_format: Annotated[
        str, typer.Option("--format", help="table, json or pr-comment (markdown for a PR).")
    ] = "table",
    fail_on: Annotated[
        str,
        typer.Option(
            "--fail-on",
            help="Exit 1 on: none, regression (a metric got worse), new-violation "
            "(a finding not in the baseline, or not in base).",
        ),
    ] = "none",
    baseline: Annotated[
        Path | None,
        typer.Option(
            "--baseline",
            exists=True,
            dir_okay=False,
            help=f"Accepted findings. Defaults to {BASELINE_FILE} in --path if it exists.",
        ),
    ] = None,
) -> None:
    """Compare two git revisions: metrics, findings and refactorings. Calls no model."""
    _check_format(output_format, ("table", "json", "pr-comment"), "diff")
    if fail_on not in FAIL_ON:
        raise _fail(f"--fail-on must be one of {', '.join(FAIL_ON)}; got {fail_on!r}.")
    try:
        cfg = load_config(config, search_from=path)
    except ConfigError as exc:
        raise _fail(str(exc)) from exc
    if baseline is None and (Path(path) / BASELINE_FILE).is_file():
        baseline = Path(path) / BASELINE_FILE
    try:
        base, head = parse_range(revisions)
        result = run_diff(path, base, head, cfg, baseline=baseline)
    except ApplyError as exc:
        raise _fail(str(exc)) from exc

    if output_format == "json":
        _emit(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif output_format == "pr-comment":
        _emit(pr_comment(result))
    else:
        render_verify(result.delta, console, None, result.goodhart, None)
        source = "the baseline" if result.accepted_from == "baseline" else base
        console.print(f"[bold]{len(result.new_findings)} new finding(s)[/bold] (not in {source})")
        for item in result.new_findings:
            console.print(f"  [yellow]+[/] {item}", markup=False, highlight=False)
        for item in result.fixed_findings:
            console.print(f"  [green]-[/] {item}", markup=False, highlight=False)
        for item in result.refactorings:
            console.print(
                f"  {item.kind} {item.source} -> {item.target} ({item.confidence:.2f})",
                markup=False,
                highlight=False,
            )

    treat_suspicious = cfg.verify is not None and cfg.verify.treat_suspicious_as_regression
    failed = (
        fail_on == "regression"
        and (result.regressed or (treat_suspicious and result.goodhart.any_suspicious))
    ) or (fail_on == "new-violation" and bool(result.new_findings))
    if failed and result.delta.comparable:
        _status(output_format).print(f"[red]Failing: --fail-on {fail_on}.[/]")
        raise typer.Exit(code=1)


baseline_app = typer.Typer(help="Accepted findings for the `rlens diff` ratchet.")
app.add_typer(baseline_app, name="baseline")


@baseline_app.command("update")
def baseline_update(
    path: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=False, dir_okay=True, help="Project directory."),
    ] = Path("."),
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", exists=True, dir_okay=False, help="Path to rlens.yaml."),
    ] = None,
) -> None:
    """Accept every current finding, so `diff --fail-on new-violation` fails only on new ones."""
    try:
        cfg = load_config(config, search_from=path)
    except ConfigError as exc:
        raise _fail(str(exc)) from exc
    accepted = findings(scan_project(path, cfg).to_dict(), cfg)
    written = write_baseline(path, accepted)
    console.print(f"{len(accepted)} finding(s) accepted in {written}. Commit it with your code.")


bench_app = typer.Typer(help="LensBench: measure prediction accuracy across models.")
app.add_typer(bench_app, name="bench")


@bench_app.command("run")
def bench_run(
    suite: Annotated[
        Path, typer.Option("--suite", exists=True, dir_okay=False, help="Suite file (YAML).")
    ],
    provider: Annotated[str | None, typer.Option("--provider", "-p", help="Provider.")] = None,
    model: Annotated[str | None, typer.Option("--model", "-m", help="Model name.")] = None,
    root: Annotated[
        Path,
        typer.Option("--root", exists=True, file_okay=False, help="Base for the suite's projects."),
    ] = Path("."),
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Results directory.")] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Print the plan and its call count, call nothing.")
    ] = False,
) -> None:
    """Run every target x condition x repeat of a suite as an `rlens loop`."""
    try:
        loaded = load_suite(suite)
    except BenchError as exc:
        raise _fail(str(exc)) from exc
    low, high = estimate_calls(loaded)
    runs = len(plan(loaded))
    console.print(
        f"{loaded.name}: {len(loaded.targets)} targets x {len(loaded.conditions)} conditions x "
        f"{loaded.repeats} repeats = {runs} runs, between {low} and {high} model calls. "
        "No response cache: repeats are independent samples."
    )
    if dry_run:
        return
    if not provider or not model:
        raise _fail("Give --provider and --model; a benchmark result is per model.")
    if provider not in PROVIDERS:
        raise _fail(f"Unknown provider '{provider}'. Available: {', '.join(sorted(PROVIDERS))}.")
    from rlens.config import ProviderConfig

    load_env_file(Path(root))
    try:
        adapter = get_provider(
            ProviderConfig(
                name=provider, model=model, base_url=None, timeout_seconds=120, max_retries=3
            )
        )
    except ProviderError as exc:
        raise _fail(str(exc)) from exc
    slug = "".join(ch if ch.isalnum() or ch in "-." else "-" for ch in f"{provider}-{model}")
    target_dir = out or Path(root) / "bench" / "results" / slug

    def progress(done: int, total: int, unit: dict) -> None:
        console.print(
            f"[dim]{done}/{total} {unit['target']} {unit['condition']} #{unit['repeat']}[/dim]"
        )

    try:
        path = run_bench(loaded, root, provider, model, adapter, target_dir, progress=progress)
    except (BenchError, ApplyError, ProviderError) as exc:
        raise _fail(f"{exc} Finished runs are kept; rerun the same command to resume.") from exc
    console.print(f"Results: {path}")


@bench_app.command("report")
def bench_report(
    results: Annotated[
        list[Path], typer.Argument(exists=True, dir_okay=False, help="Result files.")
    ],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Markdown file.")] = None,
) -> None:
    """Tables and the pre-registered verdicts for one or more result files."""
    try:
        text = report_markdown(load_results(results))
    except BenchError as exc:
        raise _fail(str(exc)) from exc
    if output:
        output.write_text(text, encoding="utf-8")
        console.print(f"Report: {output}")
    else:
        _emit(text)


def _build_cache(cfg, path: Path, *, disabled: bool) -> ResponseCache:
    """Önbelleği kurar; göreli dizin taranan projeye göre çözülür.

    Mutlak yol verilmediyse `.rlens-cache/` kullanıcının çalışma dizinine değil
    **projenin** yanına yazılır; aynı projeyi farklı dizinlerden taramak
    önbelleği ıskalamamalıdır.
    """
    from dataclasses import replace as _replace

    cache_config = cfg.cache
    if disabled:
        cache_config = _replace(cache_config, enabled=False)
    directory = Path(cache_config.directory)
    if not directory.is_absolute():
        cache_config = _replace(cache_config, directory=str(path / directory))
    return ResponseCache(cache_config)


def _render_dry_run_summary(
    contexts, cfg, cache: ResponseCache, budget: Budget, scheme=None, metric_rules=False
) -> None:
    """`--dry-run` özeti: kaç çağrı gerekecek, kaçı önbellekte hazır.

    Ağa çıkmadan maliyet tahmini verir — deney planlamanın en sık ihtiyacı.
    """
    cached = 0
    oversized = 0
    for context in contexts:
        key = prompt_hash(
            cfg.provider.name,
            cfg.provider.model,
            SYSTEM_INSTRUCTION
            + "\n"
            + build_user_prompt(context, scheme=scheme, metric_rules=metric_rules),
        )
        if cache.get(key) is not None:
            cached += 1
        if not budget.fits(context.estimated_tokens):
            oversized += 1

    # Sayaçlar yalnızca tahmin içindi; gerçek koşunun istatistiğini kirletmesin.
    cache.hits = 0
    cache.misses = 0

    console.print(
        f"[bold]{len(contexts)} target(s)[/bold] · "
        f"budget {cfg.budget.max_calls_per_run} calls, "
        f"{cfg.budget.max_tokens_per_call} tokens/call · "
        f"{cache.describe() if not cfg.cache.enabled else 'cache enabled'}"
    )
    if cached:
        console.print(
            f"[green]{cached} of {len(contexts)} prompt(s) already cached[/] — "
            f"a real run would make {len(contexts) - cached} call(s)."
        )
    if oversized:
        console.print(
            f"[yellow]{oversized} prompt(s) exceed the per-call token ceiling[/] "
            f"and would be skipped."
        )


def main() -> None:
    """`rlens` konsol betiği giriş noktası."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
