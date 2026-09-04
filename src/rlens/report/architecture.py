"""`rlens arch` terminal çıktısı.

Üç tablo: katman haritası, ihlaller, modül bağlantı ölçütleri.

**İhlal tablosu alias sütunu taşır.** Kodlar (`LV-DIR`) kısa ve grep'lenebilir
olduğu için birincildir, ama okuyucunun bulguyu literatürle eşleştirebilmesi
gerekir; alias (`back-call`) bunu sağlar.

**`tentative` ihlaller işaretlenir ve sayılır.** Düşük güvenli bir katman
atamasından türeyen ihlal CI'ı kırmaz; kullanıcı hangilerinin kesin olduğunu
görmeden geçmemelidir.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from rlens.analysis.architecture import (
    LV_CYCLE,
    UNKNOWN,
    ArchitectureResult,
)

#: Katman kaynaklarının gösterimi.
_SOURCE_STYLES = {"declared": "green", "inferred": "yellow", "unknown": "dim"}


def common_prefix(modules: list[str]) -> str:
    """Tüm modüllerin paylaştığı paket öneki.

    `src.api.view` ve `src.domain.model` gibi adlarda `src.` her satırda
    tekrarlanır ve tabloyu sardırır. Ortak önek bir kez başlıkta gösterilir,
    satırlarda kırpılır. Tek modül varsa kırpma yapılmaz — kırpılacak bir
    tekrar yoktur.
    """
    if len(modules) < 2:
        return ""
    parts = [module.split(".") for module in modules]
    shared: list[str] = []
    for index in range(min(len(p) for p in parts) - 1):
        segment = parts[0][index]
        if all(p[index] == segment for p in parts):
            shared.append(segment)
        else:
            break
    return ".".join(shared) + "." if shared else ""


def _shorten(name: str, prefix: str) -> str:
    return name[len(prefix) :] if prefix and name.startswith(prefix) else name


#: İhlal kodlarının renkleri.
_CODE_STYLES = {
    "LV-DIR": "bold red",
    "LV-SKIP": "red",
    "LV-CYCLE": "magenta",
    "LV-LEAK": "yellow",
}


def build_layer_table(result: ArchitectureResult, prefix: str = "") -> Table:
    """Modül → katman haritası; katmanı bilinmeyenler sonda."""
    title = "Layers" if not prefix else f"Layers (under `{prefix.rstrip('.')}`)"
    table = Table(title=title, title_justify="left", header_style="bold")
    table.add_column("Module", overflow="fold")
    table.add_column("Layer")
    table.add_column("Source")
    table.add_column("Confidence", justify="right")

    def sort_key(module: str):
        assignment = result.report.assignments[module]
        depth = result.scheme.depth(assignment.layer)
        return (0 if assignment.is_known else 1, depth if depth is not None else 99, module)

    for module in sorted(result.report.assignments, key=sort_key):
        assignment = result.report.assignments[module]
        style = _SOURCE_STYLES.get(assignment.source, "")
        layer = assignment.layer
        shown = f"[{style}]{layer}[/{style}]" if style else layer
        confidence = "—" if assignment.layer == UNKNOWN else f"{assignment.confidence:.2f}"
        table.add_row(_shorten(module, prefix), shown, assignment.source, confidence)
    return table


def build_violation_table(result: ArchitectureResult, prefix: str = "") -> Table | None:
    """İhlal tablosu. Hiç ihlal yoksa None."""
    if not result.report.violations:
        return None

    table = Table(title="Violations", title_justify="left", header_style="bold")
    table.add_column("Code")
    table.add_column("Alias")
    table.add_column("From → to", overflow="fold")
    table.add_column("Layers")
    table.add_column("")

    for violation in result.report.violations:
        style = _CODE_STYLES.get(violation.code, "")
        code = f"[{style}]{violation.code}[/{style}]" if style else violation.code
        if violation.code == LV_CYCLE:
            arrow = " ↔ ".join(_shorten(m, prefix) for m in violation.members)
            layers = "—"
        else:
            arrow = f"{_shorten(violation.source, prefix)} → {_shorten(violation.target, prefix)}"
            layers = f"{violation.source_layer} → {violation.target_layer}"
        table.add_row(
            code,
            violation.alias,
            arrow,
            layers,
            "[dim]tentative[/dim]" if violation.tentative else "",
        )
    return table


def build_module_table(result: ArchitectureResult, prefix: str = "") -> Table:
    """Ca / Ce / instability / derinlik.

    Eşik yoktur; bu sayılar bilgi amaçlıdır. Beklenti domain'de düşük Ce,
    presentation'da yüksek Ce'dir, ama beklenti dışı olmak bir ihlal değildir.
    """
    table = Table(title="Module coupling", title_justify="left", header_style="bold")
    table.add_column("Module", overflow="fold")
    table.add_column("Layer")
    for column in ("Ca", "Ce", "I", "Depth"):
        table.add_column(column, justify="right")

    for module in sorted(result.metrics, key=lambda m: (-result.metrics[m].ca, m)):
        metrics = result.metrics[module]
        assignment = result.report.assignments.get(module)
        instability = "—" if metrics.instability is None else f"{metrics.instability:.2f}"
        table.add_row(
            _shorten(module, prefix),
            assignment.layer if assignment else UNKNOWN,
            str(metrics.ca),
            str(metrics.ce),
            instability,
            "—" if metrics.depth is None else str(metrics.depth),
        )
    return table


def render_architecture(result: ArchitectureResult, console: Console) -> int:
    """Mimari raporunu basar ve **bloklayan** ihlal sayısını döndürür.

    `tentative` ihlaller sayıya girmez: `--fail-on-violation` yalnızca kesin
    olanlarda kırmalıdır.
    """
    total = len(result.report.assignments)
    console.print(
        f"[bold]{result.root}[/bold] — {total} modules, "
        f"{result.layered_modules} with a layer, "
        f"{len(result.graph.edges)} internal imports"
    )

    if not result.report.assignments:
        console.print("[yellow]No Python files found.[/]")
        return 0

    prefix = common_prefix(list(result.report.assignments))

    console.print()
    console.print(build_layer_table(result, prefix))

    violations = build_violation_table(result, prefix)
    if violations is None:
        console.print("\n[green]No architecture violations.[/]")
    else:
        console.print()
        console.print(violations)

    console.print()
    console.print(build_module_table(result, prefix))

    if result.report.notes:
        console.print()
        for note in result.report.notes:
            console.print(f"[dim]· {note}[/dim]")

    if result.skipped_files:
        console.print(f"\n[yellow]{len(result.skipped_files)} file(s) skipped:[/]")
        for item in result.skipped_files[:5]:
            console.print(f"  [dim]{item['path']} — {item['reason']}[/dim]")

    blocking = len(result.report.blocking)
    tentative = len(result.report.violations) - blocking
    console.print()
    if blocking:
        suffix = f" ({tentative} tentative, not counted)" if tentative else ""
        console.print(f"[red]{blocking} violation(s){suffix}.[/]")
    elif tentative:
        console.print(f"[yellow]{tentative} tentative violation(s) only.[/]")
    return blocking
