"""RefactorLens komut satırı arayüzü.

Faz 0 durumu: `scan` bir **kabuktur**. Argüman ve bayrak imzaları nihai
hallerine göre sabitlenmiştir, gövde Faz 1'de yazılacaktır.

Stub sessizce başarılı olmaz; çıkış kodu 3 ile düşer. "Çalışıyor gibi görünen"
bir komut, açıkça hata veren bir komuttan daha tehlikelidir.

`advise` (Faz 3) ve `verify` (Faz 4) komutları henüz **eklenmemiştir**. Kullanıcıya
var olup çalışmayan komut göstermek yerine, komut o faz geldiğinde eklenir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from rlens import __version__
from rlens.analysis.model import SCHEMA_VERSION
from rlens.config import ConfigError, load_config

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
#   1 = kullanıcı/ortam hatası (örn. geçersiz config)
#   2 = click/typer'a ayrılmıştır: hatalı kullanım, eksik/geçersiz argüman
#   3 = komut henüz uygulanmadı
# 3 seçilmesinin sebebi: 2 kullanılsaydı "böyle bir klasör yok" ile
# "komut hazır değil" aynı kodu dönerdi ve ayırt edilemezdi.
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
            help="Paket sürümünü ve rapor şema sürümünü yazdırıp çıkar.",
        ),
    ] = False,
) -> None:
    """RefactorLens: ölçüm temelli AI kod incelemesi."""


def _load_config_or_exit(config_path: Path | None, target: Path):
    """Config'i yükler; hatayı okunur biçimde sunup çıkar."""
    try:
        return load_config(config_path, search_from=target)
    except ConfigError as exc:
        err_console.print(f"[bold red]Config hatası:[/] {exc}")
        raise typer.Exit(code=1) from exc


@app.command()
def scan(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Analiz edilecek proje dizini.",
        ),
    ],
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            exists=True,
            dir_okay=False,
            help="rlens.yaml yolu. Verilmezse hedef dizinden köke doğru aranır.",
        ),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Rapor dizini (config'i geçersiz kılar)."),
    ] = None,
) -> None:
    """Projeyi tara, metrik tablosunu bas, JSON raporu yaz."""
    cfg = _load_config_or_exit(config, path)
    del cfg, output_dir  # Faz 1'de kullanılacak

    err_console.print(
        "[yellow]`rlens scan` henüz uygulanmadı.[/] Metrik motoru Faz 1'de yazılacak."
    )
    raise typer.Exit(code=NOT_IMPLEMENTED_EXIT)


def main() -> None:
    """`rlens` konsol betiği giriş noktası."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
