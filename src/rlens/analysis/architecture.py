"""Katman ataması ve mimari ihlal tespiti.

Bu aşamada yalnızca **beyan edilmiş** katmanlar işlenir (`arch.layers`).
Çıkarım Aşama 2'nin işidir; önce beyanla çalışan doğru bir tespit, sonra
tahmin. Sıra tersine olsaydı, çıkarım hatalarıyla tespit hatalarını birbirinden
ayıramazdık.

## Dört ihlal türü

`LV-DIR` ve `LV-SKIP` ikisi de "izin verilmemiş kenar"dır ama farklı şeyleri
anlatır ve farklı düzeltme ister:

* **LV-DIR** — ters yön. `infrastructure → domain` izinliyken
  `domain → infrastructure` görülüyorsa, bağımlılık ters çevrilmiştir. Düzeltme
  genelde bağımlılığın tersine çevrilmesidir (arayüz + enjeksiyon).
* **LV-SKIP** — katman atlama. Ters yön de izinli değil, ama katmanlar şema
  sırasında bir adımdan uzak. `presentation → infrastructure` böyledir.
  Düzeltme aradaki katmandan geçmektir.

Ayrım şema sırasına dayanır: `arch.scheme.layers` listesindeki komşuluk
"bir adım" tanımını verir. Bu yüzden liste sırası anlamlıdır ve config
doğrulaması bunu belgeler.

* **LV-CYCLE** — import döngüsü. Yapısal bir gerçektir, katman güveninden
  bağımsızdır, **asla `tentative` değildir.**
* **LV-LEAK** — alt katman tipinin üst katmanın public imzasında görünmesi.
  Yalnızca annotation varsa tespit edilebilir; annotation'sız kodda sessiz
  kalır ve bu sınırlılık raporlanır.

## `tentative` ne demek

Düşük güvenli bir katman atamasından türeyen ihlal, CI'ı kırmamalıdır: hata
ihlalde değil, atamada olabilir. Beyan edilmiş katmanlarda güven 1.0'dır,
dolayısıyla bu aşamada hiçbir ihlal `tentative` değildir. Alan Aşama 2 için
şimdiden vardır.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from rlens.analysis.graph import ModuleMetrics, cycles, module_metrics
from rlens.analysis.imports import ImportGraph, build_import_graph
from rlens.analysis.model import ARCH_SCHEMA_VERSION
from rlens.analysis.parser import ParsedModule, parse_project
from rlens.config import ArchConfig, Config, SchemeConfig

#: İhlal kodları.
LV_DIR = "LV-DIR"
LV_SKIP = "LV-SKIP"
LV_CYCLE = "LV-CYCLE"
LV_LEAK = "LV-LEAK"

#: Literatürdeki karşılıkları (Sarkar et al.; Pruijt/HUSACCT).
#:
#: Kodlar kısa ve grep'lenebilir olduğu için kalır, ama rapor okuyucusunun
#: bulguyu literatürle eşleştirebilmesi gerekir. Arcan'ın `cyclic dependency`
#: kokusu `LV-CYCLE` ile, `unstable dependency` ise `LV-DIR` ile örtüşür;
#: ilişki README'de belgelenir.
ALIASES = {
    LV_DIR: "back-call",
    LV_SKIP: "skip-call",
    LV_CYCLE: "cyclic",
    LV_LEAK: "leak",
}

#: Katman ataması kaynakları.
DECLARED = "declared"
INFERRED = "inferred"
UNKNOWN = "unknown"

#: Bu güvenin altındaki çıkarımdan doğan ihlaller `tentative` işaretlenir.
TENTATIVE_BELOW = 0.7


@dataclass(frozen=True)
class LayerAssignment:
    """Bir modülün katmanı, nereden geldiği ve ne kadar güvenilir olduğu."""

    module: str
    layer: str
    source: str
    confidence: float
    evidence: str = ""

    @property
    def is_known(self) -> bool:
        return self.layer != UNKNOWN

    @property
    def is_tentative(self) -> bool:
        """Çıkarımdan gelen ve güveni düşük olan atama."""
        return self.source == INFERRED and self.confidence < TENTATIVE_BELOW

    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "layer": self.layer,
            "source": self.source,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class Violation:
    """Tespit edilmiş bir mimari ihlal."""

    code: str
    source: str
    target: str
    source_layer: str
    target_layer: str
    detail: str
    lineno: int | None = None
    tentative: bool = False
    """Düşük güvenli bir atamadan türediyse CI'ı kırmaz."""

    members: tuple[str, ...] = ()
    """`LV-CYCLE` için döngüdeki tüm modüller."""

    @property
    def alias(self) -> str:
        """Literatürdeki adı. Bulguları yayınla eşleştirebilmek için."""
        return ALIASES.get(self.code, "")

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "alias": self.alias,
            "source": self.source,
            "target": self.target,
            "layers": [self.source_layer, self.target_layer],
            "detail": self.detail,
            "lineno": self.lineno,
            "tentative": self.tentative,
            "members": list(self.members),
        }


@dataclass
class ArchitectureReport:
    """Katman haritası, ihlaller ve tespitin sınırlılıkları."""

    assignments: dict[str, LayerAssignment] = field(default_factory=dict)
    violations: list[Violation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    """Neyin ölçülemediği. Sessiz kalmak yanıltıcı olurdu."""

    def layer_of(self, module: str) -> str:
        assignment = self.assignments.get(module)
        return assignment.layer if assignment else UNKNOWN

    def with_code(self, code: str) -> list[Violation]:
        return [v for v in self.violations if v.code == code]

    @property
    def blocking(self) -> list[Violation]:
        """`--fail-on-violation` kapsamındaki ihlaller: `tentative` olanlar hariç."""
        return [v for v in self.violations if not v.tentative]

    def to_dict(self) -> dict:
        return {
            "assignments": {k: v.to_dict() for k, v in sorted(self.assignments.items())},
            "violations": [v.to_dict() for v in self.violations],
            "notes": list(self.notes),
        }


# --------------------------------------------------------------------------- #
# Katman ataması
# --------------------------------------------------------------------------- #


def _normalise(prefix: str) -> str:
    return prefix.strip().replace("\\", "/").strip("/")


def assign_declared_layers(
    modules: list[ParsedModule], arch: ArchConfig
) -> dict[str, LayerAssignment]:
    """Beyan edilmiş yol öneklerine göre katman atar.

    Eşleşme dosya yolu üzerinden yapılır, modül adı üzerinden değil: kullanıcı
    `src/api/` yazar, modül adı ise `src.api.order_controller`'dır. En **uzun**
    eşleşen önek kazanır, böylece `src/` ve `src/api/` birlikte beyan
    edildiğinde daha özel olan geçerli olur.

    Eşleşmeyen modül `unknown` kalır. Tahmin zorlanmaz.
    """
    assignments: dict[str, LayerAssignment] = {}
    # Kanıt metninde kullanıcının yazdığı hâl gösterilir; normalize edilmiş
    # sürüm yalnızca eşleştirme içindir. Kullanıcı config'inde aradığı satırı
    # bulabilmeli.
    prefixes = [
        (_normalise(prefix), layer, prefix)
        for layer, paths in arch.declared.items()
        for prefix in paths
    ]

    for module in modules:
        path = module.relative_path
        best: tuple[int, str, str] | None = None
        for prefix, layer, original in prefixes:
            matches = prefix and (path == prefix or path.startswith(prefix + "/"))
            if matches and (best is None or len(prefix) > best[0]):
                best = (len(prefix), layer, original)

        if best is None:
            assignments[module.module] = LayerAssignment(
                module=module.module,
                layer=UNKNOWN,
                source=UNKNOWN,
                confidence=0.0,
                evidence="no declared prefix matches this path",
            )
        else:
            _, layer, prefix = best
            assignments[module.module] = LayerAssignment(
                module=module.module,
                layer=layer,
                source=DECLARED,
                confidence=1.0,
                evidence=f"declared prefix `{prefix}`",
            )
    return assignments


# --------------------------------------------------------------------------- #
# İhlal tespiti
# --------------------------------------------------------------------------- #


def classify_edge(scheme: SchemeConfig, source_layer: str, target_layer: str) -> str | None:
    """İzin verilmemiş bir kenar hangi ihlaldir? İzinliyse `None`.

    Sıra önemlidir: önce ters yön kontrol edilir. `domain → infrastructure`
    hem ters yöndür hem şema sırasında komşudur; ters yön kontrolü olmasaydı
    hiçbir kurala takılmazdı.
    """
    if scheme.may_import(source_layer, target_layer):
        return None

    if scheme.may_import(target_layer, source_layer):
        return LV_DIR

    source_depth = scheme.depth(source_layer)
    target_depth = scheme.depth(target_layer)
    distant = (
        source_depth is not None
        and target_depth is not None
        and abs(source_depth - target_depth) > 1
    )
    if distant:
        return None if scheme.allow_skip else LV_SKIP

    return LV_DIR


def _tentative(a: LayerAssignment | None, b: LayerAssignment | None) -> bool:
    return any(x is not None and x.is_tentative for x in (a, b))


def detect_edge_violations(
    graph: ImportGraph,
    assignments: dict[str, LayerAssignment],
    scheme: SchemeConfig,
) -> list[Violation]:
    """Import kenarlarından doğan `LV-DIR` ve `LV-SKIP` ihlalleri.

    Katmanı bilinmeyen modüller atlanır: bilmediğimiz bir şey hakkında ihlal
    üretmek, aracın en temel ilkesine aykırıdır.
    """
    found: list[Violation] = []
    for edge in graph.edges:
        source = assignments.get(edge.source)
        target = assignments.get(edge.target)
        if source is None or target is None or not (source.is_known and target.is_known):
            continue
        if source.layer == target.layer:
            continue

        code = classify_edge(scheme, source.layer, target.layer)
        if code is None:
            continue

        detail = f"{source.layer} must not import {target.layer}"
        if edge.weak:
            detail += " (weak import: inside a function or conditional)"
        found.append(
            Violation(
                code=code,
                source=edge.source,
                target=edge.target,
                source_layer=source.layer,
                target_layer=target.layer,
                detail=detail,
                lineno=edge.lineno,
                tentative=_tentative(source, target),
            )
        )
    return found


def detect_cycles(graph: ImportGraph, assignments: dict[str, LayerAssignment]) -> list[Violation]:
    """`LV-CYCLE`. Yapısal bir gerçektir; katman bilgisine ihtiyaç duymaz.

    Bu yüzden **asla `tentative` değildir** ve katmanı bilinmeyen modüllerde de
    raporlanır.
    """
    found: list[Violation] = []
    for component in cycles(graph.adjacency()):
        members = tuple(sorted(component))
        found.append(
            Violation(
                code=LV_CYCLE,
                source=members[0],
                target=members[-1],
                source_layer=assignments.get(members[0], _unknown(members[0])).layer,
                target_layer=assignments.get(members[-1], _unknown(members[-1])).layer,
                detail=f"import cycle of {len(members)} modules: {' → '.join(members)}",
                tentative=False,
                members=members,
            )
        )
    return found


def _unknown(module: str) -> LayerAssignment:
    return LayerAssignment(module=module, layer=UNKNOWN, source=UNKNOWN, confidence=0.0)


def _public_annotations(node: ast.ClassDef) -> list[tuple[str, str, int]]:
    """Public metotların imzalarındaki annotation adları.

    Returns:
        (metot adı, annotation metni, satır) üçlüleri.
    """
    found: list[tuple[str, str, int]] = []
    for item in node.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if item.name.startswith("_"):
            continue  # private ve dunder metotlar arayüz değildir
        arguments = item.args.posonlyargs + item.args.args + item.args.kwonlyargs
        for argument in arguments:
            if argument.annotation is not None:
                found.append((item.name, ast.unparse(argument.annotation), item.lineno))
        if item.returns is not None:
            found.append((item.name, ast.unparse(item.returns), item.lineno))
    return found


def _names_in(annotation: str) -> set[str]:
    """Annotation metnindeki tanımlayıcılar. `list[Order]` → {list, Order}."""
    try:
        tree = ast.parse(annotation, mode="eval")
    except SyntaxError:
        return set()
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    return names


def detect_interface_leaks(
    modules: list[ParsedModule],
    assignments: dict[str, LayerAssignment],
    scheme: SchemeConfig,
) -> tuple[list[Violation], list[str]]:
    """`LV-LEAK`: alt katman tipinin public imzada görünmesi.

    Returns:
        (ihlaller, sınırlılık notları)

    **Yalnızca annotation varsa görülebilir.** Annotation'sız bir imza aynı
    sızıntıyı yapabilir ama tespit edilemez; kaç sınıfın bu yüzden
    değerlendirilemediği not olarak raporlanır.
    """
    class_layer: dict[str, tuple[str, str]] = {}
    for module in modules:
        layer = assignments.get(module.module)
        for node in module.tree.body:
            if isinstance(node, ast.ClassDef):
                class_layer[node.name] = (
                    module.module,
                    layer.layer if layer else UNKNOWN,
                )

    found: list[Violation] = []
    unannotated = 0

    for module in modules:
        assignment = assignments.get(module.module)
        if assignment is None or not assignment.is_known:
            continue

        for node in module.tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            annotations = _public_annotations(node)
            if not annotations:
                unannotated += 1
                continue

            for method, annotation, lineno in annotations:
                for name in _names_in(annotation):
                    owner = class_layer.get(name)
                    if owner is None:
                        continue
                    owner_module, owner_layer = owner
                    if owner_layer in (UNKNOWN, assignment.layer):
                        continue
                    if scheme.may_import(assignment.layer, owner_layer):
                        continue
                    found.append(
                        Violation(
                            code=LV_LEAK,
                            source=f"{module.module}:{node.name}.{method}",
                            target=f"{owner_module}:{name}",
                            source_layer=assignment.layer,
                            target_layer=owner_layer,
                            detail=(
                                f"`{name}` is a {owner_layer} type appearing in a "
                                f"public {assignment.layer} signature"
                            ),
                            lineno=lineno,
                            tentative=assignment.is_tentative,
                        )
                    )

    notes = []
    if unannotated:
        notes.append(
            f"{unannotated} class(es) have no annotated public signature; "
            f"interface leaks cannot be detected there"
        )
    return found, notes


def analyse(
    modules: list[ParsedModule],
    graph: ImportGraph,
    arch: ArchConfig,
) -> ArchitectureReport:
    """Katmanları atar ve dört ihlal türünü birden arar."""
    report = ArchitectureReport()

    if not arch.has_declaration:
        report.notes.append(
            "No layers declared in `arch.layers`; every module is unknown. "
            "Layer inference arrives in a later stage."
        )
        report.assignments = {m.module: _unknown(m.module) for m in modules}
    else:
        report.assignments = assign_declared_layers(modules, arch)

    unassigned = [m for m, a in report.assignments.items() if not a.is_known]
    if unassigned and arch.has_declaration:
        report.notes.append(
            f"{len(unassigned)} module(s) match no declared prefix and stay unknown; "
            f"violations involving them are not reported"
        )

    report.violations.extend(detect_edge_violations(graph, report.assignments, arch.scheme))
    report.violations.extend(detect_cycles(graph, report.assignments))
    leaks, notes = detect_interface_leaks(modules, report.assignments, arch.scheme)
    report.violations.extend(leaks)
    report.notes.extend(notes)

    report.violations.sort(key=lambda v: (v.code, v.source, v.target))
    return report


@dataclass
class ArchitectureResult:
    """`rlens arch` çalıştırmasının tam çıktısı."""

    root: str
    generated_at: str
    rlens_version: str
    scheme: SchemeConfig
    report: ArchitectureReport
    graph: ImportGraph
    metrics: dict[str, ModuleMetrics] = field(default_factory=dict)
    skipped_files: list[dict[str, str]] = field(default_factory=list)
    schema_version: int = ARCH_SCHEMA_VERSION

    @property
    def layered_modules(self) -> int:
        return sum(1 for a in self.report.assignments.values() if a.is_known)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "rlens_version": self.rlens_version,
            "generated_at": self.generated_at,
            "root": self.root,
            "scheme": {
                "layers": list(self.scheme.layers),
                "allowed": {k: list(v) for k, v in self.scheme.allowed.items()},
                "allow_skip": self.scheme.allow_skip,
            },
            "modules": [
                {**self.metrics[module].to_dict(), **self.report.assignments[module].to_dict()}
                for module in sorted(self.report.assignments)
                if module in self.metrics
            ],
            "graph": self.graph.to_dict(),
            "violations": [v.to_dict() for v in self.report.violations],
            "notes": list(self.report.notes),
            "skipped_files": list(self.skipped_files),
        }


def analyse_project(root: Path, config: Config) -> ArchitectureResult:
    """Bir projenin mimari analizini uçtan uca yapar.

    Sıra: ayrıştır → import-linter'ı oku → katmanları ata → grafiği kur →
    ihlalleri ara. import-linter okuması katman atamasından **önce** gelir,
    çünkü beyanı o sağlayabilir.
    """
    from datetime import UTC, datetime

    from rlens import __version__
    from rlens.integrations.importlinter import apply_to_arch, read_import_linter

    root = Path(root).resolve()
    modules, skipped = parse_project(root, config.scan.include, config.scan.exclude)
    # Tarama kökü paketin kendisiyse modül adları önek taşımaz ama kod taşır.
    graph = build_import_graph(modules, root_package=root.name)

    arch, linter_notes = apply_to_arch(config.arch, read_import_linter(root))
    report = analyse(modules, graph, arch)
    report.notes = linter_notes + report.notes

    if graph.unresolved:
        report.notes.append(
            f"{len(graph.unresolved)} import(s) could not be resolved to a project "
            f"module and are excluded from the graph"
        )

    return ArchitectureResult(
        root=str(root),
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        rlens_version=__version__,
        scheme=arch.scheme,
        report=report,
        graph=graph,
        metrics=module_metrics(graph),
        skipped_files=[item.to_dict() for item in skipped],
    )
