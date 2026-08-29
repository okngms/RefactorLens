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
from rlens.analysis.parser import parse_project
from rlens.config import Config


def scan_project(root: Path, config: Config) -> ProjectReport:
    """Bir projeyi tarar ve tam metrik raporunu üretir.

    Args:
        root: Taranacak dizin.
        config: Yüklenmiş yapılandırma; `scan.include`, `scan.exclude` ve
            `metrics.cam_min_annotation_coverage` buradan okunur.

    Returns:
        Ayrıştırılan her modül için metrikleri ve atlanan dosyaların listesini
        içeren rapor. Atlanan dosyalar gizlenmez — kullanıcı neyin ölçülmediğini
        bilmelidir.
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

    return ProjectReport(
        root=str(root),
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        rlens_version=__version__,
        modules=module_reports,
        skipped_files=[item.to_dict() for item in skipped],
    )


def count_classes(report: ProjectReport) -> int:
    return sum(len(module.classes) for module in report.modules)


def count_functions(report: ProjectReport) -> int:
    """Modül düzeyi fonksiyonlar + sınıf metotları."""
    total = 0
    for module in report.modules:
        total += len(module.functions)
        total += sum(len(cls.methods) for cls in module.classes)
    return total
