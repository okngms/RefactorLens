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
from rlens.analysis.imports import build_import_graph
from rlens.analysis.interface import public_interface
from rlens.analysis.model import ModuleReport, ProjectReport
from rlens.analysis.parser import ParsedModule, parse_project
from rlens.analysis.smells import detect_class_smells, detect_function_smells
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


def scan_project(root: Path, config: Config, *, no_arch: bool = False) -> ProjectReport:
    """Bir projeyi tarar ve metrik raporunu döndürür.

    `scan` komutunun kullandığı giriş noktası. Kaynak metinlere ihtiyaç duyan
    `advise` için `scan_project_with_sources` vardır.
    """
    return scan_project_with_sources(root, config, no_arch=no_arch).report


def scan_project_with_sources(root: Path, config: Config, *, no_arch: bool = False) -> ScanResult:
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

    architecture = None
    if config.arch is not None and config.arch.enabled and not no_arch:
        architecture = _architecture_context(root, modules, config)

    module_reports: list[ModuleReport] = []
    for module in modules:
        layer = architecture.layer_of(module.module) if architecture else None
        metrics = architecture.metrics.get(module.module) if architecture else None

        classes = []
        for node in iter_module_classes(module.tree):
            measured = measure_class(
                node,
                module=module.module,
                project_classes=project_classes,
                cam_min_annotation_coverage=config.metrics.cam_min_annotation_coverage,
            )
            if architecture is not None:
                assignment = architecture.assignments.get(module.module)
                measured.layer = layer
                measured.layer_source = assignment.source if assignment else None
                measured.layer_confidence = assignment.confidence if assignment else None
                measured.public_interface = public_interface(node).to_dict()
                measured.smells = [
                    smell.to_dict()
                    for smell in detect_class_smells(
                        node,
                        measured,
                        config,
                        layer=layer,
                        layer_confidence=assignment.confidence if assignment else 0.0,
                        violating_modules=architecture.violating_modules,
                    )
                ]
            classes.append(measured)

        functions = [
            measure_function(node, is_method=False) for node in iter_module_functions(module.tree)
        ]
        module_smells: list[dict] = []
        if architecture is not None:
            for function in functions:
                module_smells.extend(
                    smell.to_dict()
                    for smell in detect_function_smells(function, module.module, config)
                )

        module_reports.append(
            ModuleReport(
                path=module.relative_path,
                module=module.module,
                classes=classes,
                functions=functions,
                layer=layer,
                ca=metrics.ca if metrics else None,
                ce=metrics.ce if metrics else None,
                instability=metrics.instability if metrics else None,
                smells=module_smells,
            )
        )

    report = ProjectReport(
        root=str(root),
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        rlens_version=__version__,
        modules=module_reports,
        skipped_files=[item.to_dict() for item in skipped],
        arch_enabled=architecture is not None,
        violations=architecture.violations if architecture else [],
        arch_notes=architecture.notes if architecture else [],
    )
    return ScanResult(report=report, modules=modules, project_classes=project_classes)


@dataclass(frozen=True)
class _ArchitectureContext:
    """Tarama sırasında kullanılan mimari bilgisi.

    `analyse_project` yeniden ayrıştırma yapardı; tarama zaten ayrıştırmış
    olduğu için burada aynı modüller yeniden kullanılır.
    """

    assignments: dict
    metrics: dict
    violations: list[dict]
    notes: list[str]
    violating_modules: set[str]

    def layer_of(self, module: str) -> str | None:
        assignment = self.assignments.get(module)
        if assignment is None or not assignment.is_known:
            return None
        return assignment.layer


def _architecture_context(
    root: Path, modules: list[ParsedModule], config: Config
) -> _ArchitectureContext:
    from rlens.analysis.architecture import LV_CYCLE, analyse
    from rlens.analysis.graph import module_metrics
    from rlens.integrations.importlinter import apply_to_arch, read_import_linter

    graph = build_import_graph(modules, root_package=root.name)
    arch, notes = apply_to_arch(config.arch, read_import_linter(root))
    report = analyse(modules, graph, arch)

    # `layer_misfit` yalnızca kenar ihlallerine bakar: döngü modül düzeyi bir
    # olgudur ve sınıfın kuplajıyla ilgili bir şey söylemez.
    violating = {v.source for v in report.violations if v.code != LV_CYCLE}

    return _ArchitectureContext(
        assignments=report.assignments,
        metrics=module_metrics(graph),
        violations=[v.to_dict() for v in report.violations],
        notes=notes + report.notes,
        violating_modules=violating,
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
