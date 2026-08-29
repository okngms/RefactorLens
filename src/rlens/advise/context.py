"""Prompt'a girecek kodun seçimi ve bağlam bütçesi.

Üç kural:

1. **Hedefin tam gövdesi gönderilir.** Yarım kodla verilen öneri havada kalır.
2. **Bağımlı sınıfların yalnızca imzaları eklenir.** Coupling önerisi, karşı
   tarafı hiç görmeden anlamsızdır; ama gövdelerini de göndermek bütçeyi
   patlatır. İmza (sınıf adı + metot imzaları + attribute adları) doğru orta yol.
3. **Kırpma yapıldıysa açıkça belirtilir.** Modele eksik kod verildiği hem
   prompt'ta hem raporda yazılır. Gizlenseydi, eksik bilgiye dayanan bir öneri
   tam bilgiye dayanmış gibi değerlendirilirdi.

Bütçe aşıldığında sıra: önce bağımlı imzalar atılır (yardımcı bilgidir), sonra
hedefin en uzun metot gövdeleri kısaltılır (hedefin iskeleti korunur).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from rlens.advise.selector import AdviceTarget
from rlens.analysis.class_metrics import class_methods
from rlens.analysis.parser import ParsedModule

#: Kırpılan gövdelerin yerine konan işaret.
TRUNCATION_MARKER = "# ... body truncated by rlens ..."

#: Bir token kabaca kaç karakter? Sağlayıcılar arasında değişir; bu yalnızca
#: bütçe kararı için kullanılan bir yaklaşıklıktır, faturalandırma değil.
_CHARS_PER_TOKEN = 4


@dataclass
class PromptContext:
    """Prompt'a girecek kod parçaları ve bütçe durumu."""

    target: AdviceTarget
    source: str
    """Hedefin kaynak metni (gerekirse kırpılmış)."""

    dependency_signatures: list[str] = field(default_factory=list)
    """Bağımlı proje-içi sınıfların gövdesiz imzaları."""

    truncation_notes: list[str] = field(default_factory=list)
    """Ne kırpıldığının insan tarafından okunabilir listesi."""

    @property
    def truncated(self) -> bool:
        return bool(self.truncation_notes)

    @property
    def estimated_tokens(self) -> int:
        return estimate_tokens(self.as_text())

    def as_text(self) -> str:
        """Prompt'a gömülecek nihai kod bloğu."""
        parts = [self.source]
        if self.dependency_signatures:
            parts.append("# --- Signatures of coupled project classes (bodies omitted) ---")
            parts.extend(self.dependency_signatures)
        return "\n\n".join(parts)


def estimate_tokens(text: str) -> int:
    """Kaba token tahmini.

    Gerçek tokenizer sağlayıcıya göre değişir. Burada amaç faturayı hesaplamak
    değil, "bu prompt çok mu büyük" sorusuna tutarlı bir cevap vermek.
    """
    return len(text) // _CHARS_PER_TOKEN


def _find_node(module: ParsedModule, target: AdviceTarget) -> ast.AST | None:
    """Hedefe karşılık gelen üst düzey düğümü bulur."""
    wanted = (ast.ClassDef,) if target.kind == "class" else (ast.FunctionDef, ast.AsyncFunctionDef)
    for node in module.tree.body:
        if isinstance(node, wanted) and node.name == target.name:
            return node
    return None


def _segment(source: str, node: ast.AST) -> str:
    """Düğümün kaynak metni, orijinal girintisiyle."""
    lines = source.splitlines()
    start = node.lineno - 1
    end = getattr(node, "end_lineno", node.lineno)
    return "\n".join(lines[start:end])


def _signature_line(method: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Bir metodun tek satırlık imzası."""
    arguments = ast.unparse(method.args)
    returns = f" -> {ast.unparse(method.returns)}" if method.returns else ""
    prefix = "async def" if isinstance(method, ast.AsyncFunctionDef) else "def"
    return f"    {prefix} {method.name}({arguments}){returns}: ..."


def build_signature(node: ast.ClassDef) -> str:
    """Bir sınıfın gövdesiz imzası: ad, metot imzaları, attribute adları."""
    bases = ", ".join(ast.unparse(base) for base in node.bases)
    header = f"class {node.name}({bases}):" if bases else f"class {node.name}:"

    lines = [header]
    attributes = sorted(_attribute_names(node))
    if attributes:
        lines.append(f"    # attributes: {', '.join(attributes)}")
    for method in node.body:
        if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines.append(_signature_line(method))
    if len(lines) == 1:
        lines.append("    ...")
    return "\n".join(lines)


def _attribute_names(node: ast.ClassDef) -> set[str]:
    """`self.<ad> = ...` ve sınıf düzeyi atamalardan gelen adlar."""
    names: set[str] = set()
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            names.add(item.target.id)
        elif isinstance(item, ast.Assign):
            names.update(t.id for t in item.targets if isinstance(t, ast.Name))
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id == "self"
            and isinstance(child.ctx, ast.Store)
        ):
            names.add(child.attr)
    return {name for name in names if not name.startswith("__")}


def find_dependencies(
    node: ast.AST,
    modules: list[ParsedModule],
    project_classes: frozenset[str],
    own_name: str,
) -> list[tuple[str, ast.ClassDef]]:
    """Hedefin referans verdiği proje-içi sınıfların düğümleri.

    Sıralama kararlıdır (modül, sınıf adı); aynı hedef iki kez işlendiğinde
    prompt aynı olmalıdır.
    """
    referenced: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            referenced.add(child.id)
        elif isinstance(child, ast.Attribute):
            referenced.add(child.attr)
    referenced &= set(project_classes)
    referenced.discard(own_name)

    found: list[tuple[str, ast.ClassDef]] = []
    for module in modules:
        for item in module.tree.body:
            if isinstance(item, ast.ClassDef) and item.name in referenced:
                found.append((module.module, item))
    found.sort(key=lambda pair: (pair[0], pair[1].name))
    return found


def _truncate_longest_methods(
    source: str, node: ast.ClassDef, budget_chars: int
) -> tuple[str, list[str]]:
    """Bütçeye sığana kadar en uzun metot gövdelerini kısaltır.

    Sınıfın iskeleti (metot imzaları) her zaman korunur — model neyin var
    olduğunu görmeli, sadece nasıl yazıldığını görmemelidir.
    """
    if len(source) <= budget_chars:
        return source, []

    lines = source.splitlines()
    offset = node.lineno - 1
    notes: list[str] = []

    methods = [
        method
        for method in class_methods(node)
        if method.body and getattr(method, "end_lineno", None)
    ]
    methods.sort(key=lambda m: (m.end_lineno or 0) - m.lineno, reverse=True)

    removed: set[int] = set()

    def current_length() -> int:
        return len("\n".join(line for i, line in enumerate(lines) if i not in removed))

    for method in methods:
        if current_length() <= budget_chars:
            break
        body_start = method.body[0].lineno - 1 - offset
        body_end = (method.end_lineno or method.lineno) - offset
        if body_start < 0 or body_end > len(lines):
            continue
        indent = " " * (method.body[0].col_offset)
        lines[body_start] = f"{indent}{TRUNCATION_MARKER}"
        removed.update(range(body_start + 1, body_end))
        notes.append(f"{node.name}.{method.name} body omitted")

    kept = [line for index, line in enumerate(lines) if index not in removed]
    return "\n".join(kept), notes


def build_context(
    target: AdviceTarget,
    modules: list[ParsedModule],
    project_classes: frozenset[str],
    max_tokens: int,
) -> PromptContext:
    """Bir hedef için prompt bağlamını kurar.

    Raises:
        LookupError: Hedef, verilen modüllerde bulunamazsa.
    """
    module = next((m for m in modules if m.module == target.module), None)
    if module is None:
        raise LookupError(f"Module not found for target: {target.qualified_name}")

    node = _find_node(module, target)
    if node is None:
        raise LookupError(f"Target not found in module: {target.qualified_name}")

    source = _segment(module.source, node)
    budget_chars = max_tokens * _CHARS_PER_TOKEN
    notes: list[str] = []

    signatures: list[str] = []
    if isinstance(node, ast.ClassDef):
        dependencies = find_dependencies(node, modules, project_classes, node.name)
        signatures = [build_signature(dependency) for _, dependency in dependencies]

    # 1. adım: imzalar bütçeyi aşıyorsa at (yardımcı bilgidir).
    while signatures and estimate_tokens(source + "\n\n".join(signatures)) > max_tokens:
        signatures.pop()
        notes.append("dependency signatures dropped to fit the context budget")
        notes = list(dict.fromkeys(notes))

    # 2. adım: hâlâ aşıyorsa hedefin en uzun metot gövdelerini kısalt.
    if isinstance(node, ast.ClassDef) and estimate_tokens(source) > max_tokens:
        source, method_notes = _truncate_longest_methods(
            source, node, budget_chars - len("\n\n".join(signatures))
        )
        notes.extend(method_notes)

    return PromptContext(
        target=target,
        source=source,
        dependency_signatures=signatures,
        truncation_notes=notes,
    )
