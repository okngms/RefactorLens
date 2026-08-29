"""Tarama akışının orkestrasyonu: kaynak dosyalardan `ProjectReport`'a.

**Neden iki geçiş?** DCC "proje-içi sınıf" sayar. Bir sınıfın projeye ait olup
olmadığını bilmek için önce projedeki tüm sınıf adlarının toplanması gerekir.
Tek geçişte ilerlenirse, henüz görülmemiş bir modüldeki sınıfa yapılan referans
kaçırılır ve DCC sistematik olarak düşük çıkar.

Bu modül metrik *hesaplamaz*; hesaplayan modülleri doğru sırayla çağırır ve
sonucu rapor nesnesine yerleştirir. Sınır böyle çizildiği için metrikler
CLI'dan bağımsız test edilebilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from rlens import __version__
from rlens.analysis.class_metrics import (
    collect_class_names,
    iter_module_classes,
    measure_class,
)
from rlens.analysis.func_metrics import iter_module_functions, measure_function
from rlens.analysis.model import ModuleReport, ProjectReport
from rlens.analysis.parser import ParsedModule, parse_project
from rlens.config import Config


@dataclass(frozen=True)
class ScanResult:
    """Rapor + kaynak metinler.

    `scan` yalnızca rapora ihtiyaç duyar, ama `advise` prompt'a gerçek kodu
    koymak zorundadır ve `ProjectReport` kaynak metni taşımaz (taşısaydı JSON
    raporlar devasa olurdu). Bu yüzden iki tüketici için iki farklı giriş
    noktası vardır; ikisi de aynı hesabı yapar.
    """

    report: ProjectReport
    modules: list[ParsedModule]
    project_classes: frozenset[str]


def scan_project(root: Path, config: Config) -> ProjectReport:
    """Bir projeyi tarar ve metrik raporunu döndürür.

    `scan` komutunun kullandığı giriş noktası. Kaynak metinlere ihtiyaç duyan
    `advise` için `scan_project_with_sources` vardır.
    """
    return scan_project_with_sources(root, config).report


def scan_project_with_sources(root: Path, config: Config) -> ScanResult:
    """Raporu ve ayrıştırılmış kaynakları birlikte döndürür.

    **Neden iki geçiş?** DCC "proje-içi sınıf" sayar. Bir sınıfın projeye ait
    olup olmadığını bilmek için önce projedeki tüm sınıf adlarının toplanması
    gerekir. Tek geçişte ilerlenirse, henüz görülmemiş bir modüldeki sınıfa
    yapılan referans kaçırılır ve DCC sistematik olarak düşük çıkar.
    """
    root = root.resolve()

    # 1. geçiş — ayrıştır
    modules, skipped = parse_project(root, config.scan.include, config.scan.exclude)

    # 2. geçiş — DCC sözlüğünü kur
    project_classes = collect_class_names([module.tree for module in modules])

    module_reports: list[ModuleReport] = []
    for module in modules:
        module_reports.append(
            ModuleReport(
                path=module.relative_path,
                module=module.module,
                classes=[
                    measure_class(
                        node,
                        module=module.module,
                        project_classes=project_classes,
                        cam_min_annotation_coverage=config.metrics.cam_min_annotation_coverage,
                    )
                    for node in iter_module_classes(module.tree)
                ],
                functions=[
                    measure_function(node, is_method=False)
                    for node in iter_module_functions(module.tree)
                ],
            )
        )

    report = ProjectReport(
        root=str(root),
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        rlens_version=__version__,
        modules=module_reports,
        skipped_files=[item.to_dict() for item in skipped],
    )
    return ScanResult(report=report, modules=modules, project_classes=project_classes)


def count_classes(report: ProjectReport) -> int:
    return sum(len(module.classes) for module in report.modules)


def count_functions(report: ProjectReport) -> int:
    """Modül düzeyi fonksiyonlar + sınıf metotları."""
    total = 0
    for module in report.modules:
        total += len(module.functions)
        total += sum(len(cls.methods) for cls in module.classes)
    return total
