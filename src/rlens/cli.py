"""RefactorLens komut satırı arayüzü.

Bu modül **yalnızca arayüzdür**: argümanları okur, config'i yükler, iş
mantığını çağırır ve sonucu sunar. Tarama akışı `analysis.scanner`, çıktı
biçimlendirme `report` paketi içindedir. Sınır böyle çizildiği için metrikler
CLI'dan bağımsız test edilebilir.

Komut kümesi tamamdır: `scan` ölçer, `advise` önerir, `verify` önerinin
etkisini ve modelin tahmininin isabetini denetler.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from rlens import __version__
from rlens.advise.advisor import AdviceDocument, request_advice
from rlens.advise.context import build_context
from rlens.advise.prompts import SYSTEM_INSTRUCTION, build_user_prompt
from rlens.advise.selector import select_targets
from rlens.analysis.architecture import analyse_project
from rlens.analysis.model import SCHEMA_VERSION
from rlens.analysis.scanner import scan_project, scan_project_with_sources
from rlens.config import ConfigError, load_config
from rlens.llm.budget import Budget, BudgetExceeded
from rlens.llm.cache import ResponseCache, prompt_hash
from rlens.providers import PROVIDERS, ProviderError, get_provider, load_env_file
from rlens.report.advice import render_advice
from rlens.report.architecture import render_architecture
from rlens.report.files import (
    ReportError,
    latest_report,
    read_report,
    write_advice,
    write_arch,
    write_report,
    write_verify,
)
from rlens.report.terminal import render_report
from rlens.report.verify import render_verify
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
    fail_on_violation: Annotated[
        bool,
        typer.Option(
            "--fail-on-violation",
            help="Exit with code 1 if anything is over threshold (useful in CI).",
        ),
    ] = False,
) -> None:
    """Scan a project, print the metric tables and write a JSON report."""
    try:
        cfg = load_config(config, search_from=path)
    except ConfigError as exc:
        raise _fail(str(exc)) from exc

    report = scan_project(path, cfg)
    violations = render_report(report, cfg, console)

    if not no_report and report.modules:
        target = Path(output_dir) if output_dir else path / cfg.scan.output_dir
        try:
            written = write_report(report, target)
        except ReportError as exc:
            raise _fail(str(exc)) from exc
        console.print(f"[dim]Report: {written}[/dim]")

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
) -> None:
    """Map layers, list architecture violations and module coupling."""
    try:
        cfg = load_config(config, search_from=path)
    except ConfigError as exc:
        raise _fail(str(exc)) from exc

    result = analyse_project(path, cfg)
    blocking = render_architecture(result, console)

    if not no_report and result.report.assignments:
        target = Path(output_dir) if output_dir else path / cfg.scan.output_dir
        try:
            written = write_arch(result, target)
        except ReportError as exc:
            raise _fail(str(exc)) from exc
        console.print(f"[dim]Report: {written}[/dim]")

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
                build_context(
                    target, result.modules, result.project_classes, cfg.advise.max_context_tokens
                )
            )
        except LookupError as exc:
            err_console.print(f"[yellow]Skipping {target.qualified_name}:[/] {exc}")

    if not contexts:
        raise _fail("None of the selected targets could be located in the source.")

    cache = _build_cache(cfg, path, disabled=no_cache)
    budget = Budget(cfg.budget)

    if dry_run:
        _render_dry_run_summary(contexts, cfg, cache, budget)
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
            console.print(build_user_prompt(context), markup=False, highlight=False)
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
) -> None:
    """Re-measure after a change and check whether the model's predictions held."""
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
        console.print(f"[dim]baseline: {baseline_path}[/dim]")

    try:
        baseline = read_report(baseline_path)
    except ReportError as exc:
        raise _fail(str(exc)) from exc

    current = scan_project(path, cfg).to_dict()
    delta = diff_reports(baseline, current)

    predictions = None
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

    render_verify(delta, console, predictions)

    if not no_report:
        try:
            json_path, markdown_path = write_verify(delta, predictions, report_dir)
        except ReportError as exc:
            raise _fail(str(exc)) from exc
        console.print(f"[dim]Report: {markdown_path}[/dim]")
        console.print(f"[dim]Machine-readable: {json_path}[/dim]")

    # Karşılaştırma geçersizse regresyon kontrolü yapılmaz: anlamsız sayılara
    # dayanarak derlemeyi kırmak, sessizce yanlış delta üretmek kadar zararlı.
    regressed = any(entity.summarise() == REGRESSED for entity in delta.entities)
    if fail_on_regression and delta.comparable and regressed:
        raise typer.Exit(code=1)


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


def _render_dry_run_summary(contexts, cfg, cache: ResponseCache, budget: Budget) -> None:
    """`--dry-run` özeti: kaç çağrı gerekecek, kaçı önbellekte hazır.

    Ağa çıkmadan maliyet tahmini verir — deney planlamanın en sık ihtiyacı.
    """
    cached = 0
    oversized = 0
    for context in contexts:
        key = prompt_hash(
            cfg.provider.name,
            cfg.provider.model,
            SYSTEM_INSTRUCTION + "\n" + build_user_prompt(context),
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
