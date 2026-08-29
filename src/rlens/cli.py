"""RefactorLens komut satırı arayüzü.

Bu modül **yalnızca arayüzdür**: argümanları okur, config'i yükler, iş
mantığını çağırır ve sonucu sunar. Tarama akışı `analysis.scanner`, çıktı
biçimlendirme `report` paketi içindedir. Sınır böyle çizildiği için metrikler
CLI'dan bağımsız test edilebilir.

`verify` (Faz 4) komutu henüz eklenmemiştir; kullanıcıya var olup çalışmayan
komut göstermek yerine, komut kendi fazında eklenir.
"""

from __future__ import annotations

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
from rlens.analysis.model import SCHEMA_VERSION
from rlens.analysis.scanner import scan_project, scan_project_with_sources
from rlens.config import ConfigError, load_config
from rlens.providers import PROVIDERS, ProviderError, get_provider, load_env_file
from rlens.report.advice import render_advice
from rlens.report.files import ReportError, write_advice, write_report
from rlens.report.terminal import render_report

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

    if dry_run:
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
        console.print(f"[dim]asking about {context.target.qualified_name}…[/dim]")
        try:
            advice, warnings = request_advice(adapter, context, cfg)
        except ProviderError as exc:
            raise _fail(str(exc)) from exc
        advice.warnings = warnings
        document.advices.append(advice)

    console.print()
    render_advice(document, console)

    if not no_report:
        target_dir = Path(output_dir) if output_dir else path / cfg.scan.output_dir
        try:
            json_path, markdown_path = write_advice(document, target_dir)
        except ReportError as exc:
            raise _fail(str(exc)) from exc
        console.print(f"[dim]Report: {markdown_path}[/dim]")
        console.print(f"[dim]Machine-readable: {json_path}[/dim]")


def main() -> None:
    """`rlens` konsol betiği giriş noktası."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
