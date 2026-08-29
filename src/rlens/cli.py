"""RefactorLens komut satırı arayüzü.

Bu modül **yalnızca arayüzdür**: argümanları okur, config'i yükler, iş
mantığını çağırır ve sonucu sunar. Tarama akışı `analysis.scanner`, çıktı
biçimlendirme `report` paketi içindedir. Sınır böyle çizildiği için metrikler
CLI'dan bağımsız test edilebilir.

`advise` (Faz 3) ve `verify` (Faz 4) komutları henüz eklenmemiştir; kullanıcıya
var olup çalışmayan komut göstermek yerine, komut kendi fazında eklenir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from rlens import __version__
from rlens.analysis.model import SCHEMA_VERSION
from rlens.analysis.scanner import scan_project
from rlens.config import ConfigError, load_config
from rlens.report.files import ReportError, write_report
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


def main() -> None:
    """`rlens` konsol betiği giriş noktası."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
