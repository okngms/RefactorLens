"""Terminal çıktısı: `rich` tabloları.

Kullanıcıya görünen tüm metinler İngilizcedir; paket açık kaynak olarak
yayınlanır ve arayüz dili geliştiricinin diline bağlı olmamalıdır. Docstring'ler
Türkçe kalır — onlar projeyi geliştiren kişiye bakar.

Tasarım ilkeleri:

* **`None` asla sayı gibi gösterilmez.** Hesaplanamayan metrik `—` olarak
  basılır ve tablonun altına nedeni yazılır. Kullanıcı "0" ile "ölçemedim"i
  karıştırmamalıdır.
* **Eşik ihlalleri renklendirilir**, ama renk tek bilgi taşıyıcısı değildir;
  ihlaller ayrıca özet satırında sayılır (renksiz terminaller ve günlük
  dosyaları için).
* **Fonksiyon tablosunda yalnızca ihlaller listelenir.** Binlerce fonksiyonun
  tamamını basmak terminali kullanılamaz hale getirir.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from rlens.analysis.model import ClassReport, FunctionReport, ProjectReport
from rlens.analysis.scanner import count_classes, count_functions
from rlens.config import Config
from rlens.report.architecture import common_prefix

#: Hesaplanamayan değerlerin gösterimi.
NULL_DISPLAY = "—"

#: Eşik seviyelerinin renkleri.
_LEVEL_STYLES = {"warn": "yellow", "critical": "bold red"}

#: Sınıf metriği adı → config'teki eşik anahtarı.
_CLASS_THRESHOLD_KEYS = {
    "nom": "nom",
    "wmc": "wmc",
    "lcom4": "lcom4",
    "dcc": "dcc",
}

#: Fonksiyon metriği adı → config anahtarı.
_FUNCTION_THRESHOLD_KEYS = {
    "cyclomatic_complexity": "cyclomatic_complexity",
    "param_count": "max_params",
    "max_nesting": "max_nesting",
}

#: Koku etiketlerinin tabloya sığan kısa biçimleri. Tam adlar JSON raporunda.
SMELL_SHORT = {
    "god_class": "god",
    "data_class": "data",
    "feature_envy_candidate": "envy",
    "long_method": "long",
    "too_many_params": "params",
    "layer_misfit": "misfit",
}

#: CAM'in atlanma nedenlerinin kullanıcıya gösterilen karşılıkları.
_CAM_REASON_LABELS = {
    "insufficient_annotations": "annotation coverage below threshold",
    "no_annotated_parameters": "no annotated parameters",
}


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    """ "1 class" / "2 classes" — yayınlanan bir araçta çoğul eki göze batar."""
    return f"{count} {singular if count == 1 else (plural or singular + 'es')}"


def _format(value: float | int | None, *, decimals: int = 0) -> str:
    if value is None:
        return NULL_DISPLAY
    if decimals:
        return f"{value:.{decimals}f}"
    return str(value)


def _styled(value: float | int | None, level: str | None, *, decimals: int = 0) -> str:
    text = _format(value, decimals=decimals)
    style = _LEVEL_STYLES.get(level or "")
    return f"[{style}]{text}[/{style}]" if style else text


def class_violations(report: ClassReport, config: Config) -> dict[str, str]:
    """Sınıfın hangi metriklerinin hangi seviyede eşiği aştığı."""
    levels: dict[str, str] = {}
    for metric, key in _CLASS_THRESHOLD_KEYS.items():
        # Aynı DCC değeri application-service'te tasarım gereği, domain
        # modelinde kokudur. Katman bilinmiyorsa genel eşiğe düşülür.
        threshold = config.threshold_for(key, report.layer)
        if threshold is None:
            continue
        level = threshold.level(getattr(report, metric))
        if level:
            levels[metric] = level
    return levels


def function_violations(report: FunctionReport, config: Config) -> dict[str, str]:
    """Fonksiyonun hangi metriklerinin eşiği aştığı."""
    levels: dict[str, str] = {}
    for metric, key in _FUNCTION_THRESHOLD_KEYS.items():
        threshold = config.thresholds.get(key)
        if threshold is None:
            continue
        level = threshold.level(getattr(report, metric))
        if level:
            levels[metric] = level
    return levels


def _worst(levels: dict[str, str]) -> str | None:
    if "critical" in levels.values():
        return "critical"
    if "warn" in levels.values():
        return "warn"
    return None


def build_class_table(report: ProjectReport, config: Config) -> Table:
    """Sınıf metrikleri tablosu; en sorunlu sınıflar üstte.

    `Layer` ve `Smells` sütunları yalnızca mimari analizi açıkken eklenir;
    `--no-arch` çıktısı v1 ile birebir aynı kalmalıdır.
    """
    # Ortak paket öneki yalnızca mimari açıkken kırpılır: iki ek sütun tabloyu
    # sardırır. `--no-arch` v1 tablosunu ve v1 biçimini aynen korur.
    prefix = _prefix_for(report)
    title = "Class metrics"
    if prefix:
        title += f" (under `{prefix.rstrip('.')}`)"
    table = Table(title=title, title_justify="left", header_style="bold")
    table.add_column("Class", overflow="fold")
    if report.arch_enabled:
        table.add_column("Layer")
    for column in ("NOM", "WMC", "LCOM4", "DCC", "DAM", "CAM"):
        table.add_column(column, justify="right")
    if report.arch_enabled:
        table.add_column("Smells")

    rows: list[tuple[int, int, ClassReport, dict[str, str]]] = []
    for module in report.modules:
        for cls in module.classes:
            levels = class_violations(cls, config)
            severity = 2 if _worst(levels) == "critical" else 1 if levels else 0
            rows.append((severity, cls.wmc or 0, cls, levels))

    # En sorunlular üstte; eşitlikte karmaşıklığı yüksek olan önce.
    rows.sort(key=lambda row: (-row[0], -row[1], row[2].qualified_name))

    for _, _, cls, levels in rows:
        cells = [_shorten(cls.qualified_name, prefix)]
        if report.arch_enabled:
            cells.append(cls.layer or "—")
        cells += [
            _styled(cls.nom, levels.get("nom")),
            _styled(cls.wmc, levels.get("wmc")),
            _styled(cls.lcom4, levels.get("lcom4")),
            _styled(cls.dcc, levels.get("dcc")),
            _format(cls.dam, decimals=2),
            _format(cls.cam, decimals=2),
        ]
        if report.arch_enabled:
            labels = [SMELL_SHORT.get(s["label"], s["label"]) for s in cls.smells]
            cells.append(", ".join(labels) if labels else "")
        table.add_row(*cells)
    return table


def _prefix_for(report: ProjectReport) -> str:
    """Sınıf ve modül adlarında kırpılacak ortak paket öneki."""
    if not report.arch_enabled:
        return ""
    return common_prefix([module.module for module in report.modules])


def _shorten(name: str, prefix: str) -> str:
    return name[len(prefix) :] if prefix and name.startswith(prefix) else name


def build_module_table(report: ProjectReport) -> Table | None:
    """Modül düzeyi bağlantı ölçütleri. Eşik yoktur; yalnızca bilgidir."""
    if not report.arch_enabled:
        return None
    table = Table(title="Modules", title_justify="left", header_style="bold")
    table.add_column("Module", overflow="fold")
    table.add_column("Layer")
    for column in ("Ca", "Ce", "I"):
        table.add_column(column, justify="right")

    prefix = _prefix_for(report)
    for module in sorted(report.modules, key=lambda m: (-(m.ca or 0), m.module)):
        table.add_row(
            _shorten(module.module, prefix),
            module.layer or "—",
            _format(module.ca),
            _format(module.ce),
            _format(module.instability, decimals=2),
        )
    return table


def _smell_notes(report: ProjectReport) -> list[str]:
    """Koku özetleri ve gerektiğinde açıklama.

    `data_class` için ayrı bir not vardır: o etiketin varlık sebebi, LCOM4'ün
    veri taşıyıcılarında yüksek çıkmasının bir kusur olmadığını söylemektir.
    """
    counts: dict[str, int] = {}
    for smell in report.iter_smells():
        counts[smell["label"]] = counts.get(smell["label"], 0) + 1
    if not counts:
        return []

    notes = [
        ", ".join(f"{count} {label}" for label, count in sorted(counts.items()))
        + "  (smell labels; see the JSON report for the evidence behind each)"
    ]
    if "data_class" in counts:
        notes.append(
            "data_class marks a data holder: a high LCOM4 there is expected, "
            "because one accessor per field shares no state by design"
        )
    return notes


def build_function_table(report: ProjectReport, config: Config) -> Table | None:
    """Yalnızca eşik aşan fonksiyonlar. İhlal yoksa None."""
    table = Table(
        title="Functions over threshold",
        title_justify="left",
        header_style="bold",
    )
    table.add_column("Function", overflow="fold")
    for column in ("CC", "Params", "Nesting", "LOC"):
        table.add_column(column, justify="right")

    prefix = _prefix_for(report)
    rows: list[tuple[int, FunctionReport, str, dict[str, str]]] = []
    for module in report.modules:
        short = _shorten(module.module, prefix)
        candidates = [(short, fn) for fn in module.functions]
        for cls in module.classes:
            candidates += [(f"{short}:{cls.name}", fn) for fn in cls.methods]

        for owner, fn in candidates:
            levels = function_violations(fn, config)
            if levels:
                rows.append((fn.cyclomatic_complexity or 0, fn, owner, levels))

    if not rows:
        return None

    rows.sort(key=lambda row: (-row[0], row[2], row[1].name))
    for _, fn, owner, levels in rows:
        table.add_row(
            f"{owner}.{fn.name}",
            _styled(fn.cyclomatic_complexity, levels.get("cyclomatic_complexity")),
            _styled(fn.param_count, levels.get("param_count")),
            _styled(fn.max_nesting, levels.get("max_nesting")),
            _format(fn.loc),
        )
    return table


def _cam_notes(report: ProjectReport) -> list[str]:
    """CAM'in neden `null` döndüğüne dair özet."""
    reasons: dict[str, int] = {}
    for cls in report.iter_classes():
        if cls.cam is None and cls.cam_skipped_reason:
            reasons[cls.cam_skipped_reason] = reasons.get(cls.cam_skipped_reason, 0) + 1

    return [
        f"CAM not computed for {_plural(count, 'class')} ({_CAM_REASON_LABELS.get(reason, reason)})"
        for reason, count in sorted(reasons.items())
    ]


def _render_skipped(report: ProjectReport, console: Console) -> None:
    """Atlanan dosyaları listeler. Kullanıcı neyin ölçülmediğini bilmelidir."""
    if not report.skipped_files:
        return
    count = len(report.skipped_files)
    console.print(f"[yellow]{_plural(count, 'file', 'files')} skipped:[/]")
    for item in report.skipped_files[:5]:
        console.print(f"  [dim]{item['path']} — {item['reason']}[/dim]")
    if count > 5:
        console.print(f"  [dim]… and {count - 5} more[/dim]")


def render_report(report: ProjectReport, config: Config, console: Console) -> int:
    """Raporu terminale basar ve toplam ihlal sayısını döndürür."""
    console.print(
        f"[bold]{report.root}[/bold] — "
        f"{_plural(len(report.modules), 'module', 'modules')}, "
        f"{_plural(count_classes(report), 'class')}, "
        f"{_plural(count_functions(report), 'function', 'functions')}"
    )

    if not report.modules:
        # Dosya bulunup ayrıştırılamadıysa sorun config'te değil kodda olabilir;
        # bu iki durumu ayırmak kullanıcıyı doğru yere yönlendirir.
        if report.skipped_files:
            console.print("[yellow]None of the files found could be parsed.[/]")
            _render_skipped(report, console)
        else:
            console.print(
                "[yellow]No Python files found.[/] "
                "Check the `scan.include` and `scan.exclude` settings."
            )
        return 0

    class_table = build_class_table(report, config)
    if class_table.row_count:
        console.print()
        console.print(class_table)

    function_table = build_function_table(report, config)
    if function_table is not None:
        console.print()
        console.print(function_table)

    console.print()

    modules = build_module_table(report)
    if modules is not None:
        console.print()
        console.print(modules)
        console.print()

    for note in _cam_notes(report):
        console.print(f"[dim]{NULL_DISPLAY} {note}[/dim]")
    for note in _smell_notes(report):
        console.print(f"[dim]{note}[/dim]")
    for note in report.arch_notes:
        console.print(f"[dim]· {note}[/dim]")

    if report.violations:
        blocking = [v for v in report.violations if not v.get("tentative")]
        console.print(
            f"[red]{len(blocking)} architecture violation(s)[/] — run `rlens arch` for details."
        )

    _render_skipped(report, console)

    violations = sum(1 for cls in report.iter_classes() if class_violations(cls, config)) + sum(
        1 for module in report.modules for fn in module.functions if function_violations(fn, config)
    )

    if violations:
        console.print(
            f"[yellow]{violations} {'item' if violations == 1 else 'items'} over threshold.[/]"
        )
    else:
        console.print("[green]Nothing over threshold.[/]")

    return violations
