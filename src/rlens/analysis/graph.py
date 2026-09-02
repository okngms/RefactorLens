"""Import grafiği üzerinde yapısal hesaplar.

Üç şey üretir:

* **Güçlü bağlı bileşenler (SCC).** Birden büyük her bileşen bir import
  döngüsüdür — `LV-CYCLE` ihlalinin ta kendisi. Döngüler ayrıca topolojik
  sıralamayı imkânsız kılar, bu yüzden derinlik hesabından önce yoğunlaştırılır.
* **Topolojik derinlik.** Bağımlılık zincirinde ne kadar aşağıda? Katman
  çıkarımının üç sinyalinden biri: `presentation` genelde 0, `domain` en derin.
* **Ca / Ce / instability.** Martin'in ölçütleri. Beklenti: domain düşük Ce,
  infrastructure yüksek Ce. Eşik konmaz, yalnızca bilgi olarak raporlanır.

**Zayıf kenarlar dahil edilir.** Fonksiyon içindeki import da gerçek bir
bağımlılıktır; döngü tespiti onu görmezse, döngüyü kırmak için oraya konmuş
importlar döngüyü gizler. Çağıran taraf isterse zayıfları hariç tutabilir.
"""

from __future__ import annotations

from dataclasses import dataclass

from rlens.analysis.imports import ImportGraph


@dataclass(frozen=True)
class ModuleMetrics:
    """Tek bir modülün bağlantı ölçütleri."""

    module: str
    ca: int
    """Afferent: bu modülü kaç proje modülü import ediyor."""

    ce: int
    """Efferent: bu modül kaç proje modülünü import ediyor."""

    instability: float | None
    """Ce / (Ca + Ce). Hiç bağlantı yoksa `None` — sıfır yanıltıcı olurdu."""

    depth: int | None
    """Bağımlılık zincirindeki derinlik. Döngüdeki modüller bileşen derinliğini paylaşır."""

    in_cycle: bool

    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "ca": self.ca,
            "ce": self.ce,
            "instability": self.instability,
            "depth": self.depth,
            "in_cycle": self.in_cycle,
        }


def strongly_connected_components(
    adjacency: dict[str, set[str]],
) -> list[frozenset[str]]:
    """Tarjan algoritması, yinelemesiz.

    Özyinelemeli hâli derin grafiklerde yığını taşırır; gerçek projelerde
    yüzlerce modül zinciri olağandır.

    Sonuç kararlıdır: bileşenler kendi içinde ve aralarında sıralanır, böylece
    aynı proje iki kez tarandığında rapor değişmez.
    """
    index_of: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[frozenset[str]] = []
    counter = 0

    for root in sorted(adjacency):
        if root in index_of:
            continue

        # (düğüm, komşu yineleyici) çiftlerinden oluşan açık yığın
        work: list[tuple[str, list[str]]] = [(root, sorted(adjacency.get(root, ())))]
        index_of[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)

        while work:
            node, pending = work[-1]
            if pending:
                neighbour = pending.pop(0)
                if neighbour not in index_of:
                    index_of[neighbour] = low[neighbour] = counter
                    counter += 1
                    stack.append(neighbour)
                    on_stack.add(neighbour)
                    work.append((neighbour, sorted(adjacency.get(neighbour, ()))))
                elif neighbour in on_stack:
                    low[node] = min(low[node], index_of[neighbour])
                continue

            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])

            if low[node] == index_of[node]:
                component: set[str] = set()
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.add(member)
                    if member == node:
                        break
                components.append(frozenset(component))

    return sorted(components, key=lambda c: sorted(c))


def cycles(adjacency: dict[str, set[str]]) -> list[frozenset[str]]:
    """Yalnızca gerçek döngüler: birden büyük bileşenler ve kendine döngüler."""
    found = []
    for component in strongly_connected_components(adjacency):
        if len(component) > 1:
            found.append(component)
        else:
            (only,) = component
            if only in adjacency.get(only, set()):
                found.append(component)
    return found


def condensation_depths(adjacency: dict[str, set[str]]) -> dict[str, int]:
    """Her modülün bağımlılık zincirindeki derinliği.

    Döngüler önce tek düğüme yoğunlaştırılır — aksi halde topolojik sıralama
    tanımsızdır. Aynı döngüdeki modüller aynı derinliği paylaşır; hangisinin
    "daha derin" olduğu sorusu döngü içinde anlamsızdır.

    Derinlik, kaynaklardan (hiç import edilmeyen modüller) itibaren **en uzun**
    yoldur. Bir modül birden çok zincirde yer alıyorsa en derin konumu geçerlidir:
    katman ataması için "en az bu kadar aşağıda" bilgisi doğru olandır.
    """
    components = strongly_connected_components(adjacency)
    owner: dict[str, int] = {}
    for index, component in enumerate(components):
        for module in component:
            owner[module] = index

    # Yoğunlaştırılmış DAG
    dag: dict[int, set[int]] = {index: set() for index in range(len(components))}
    incoming: dict[int, int] = dict.fromkeys(range(len(components)), 0)
    for source, targets in adjacency.items():
        for target in targets:
            if target not in owner or source not in owner:
                continue
            a, b = owner[source], owner[target]
            if a != b and b not in dag[a]:
                dag[a].add(b)
                incoming[b] += 1

    # Kahn sıralaması + en uzun yol
    depth: dict[int, int] = dict.fromkeys(range(len(components)), 0)
    queue = sorted(index for index, count in incoming.items() if count == 0)
    order: list[int] = []
    remaining = dict(incoming)
    while queue:
        node = queue.pop(0)
        order.append(node)
        for target in sorted(dag[node]):
            depth[target] = max(depth[target], depth[node] + 1)
            remaining[target] -= 1
            if remaining[target] == 0:
                queue.append(target)
                queue.sort()

    return {module: depth[owner[module]] for module in owner}


def module_metrics(graph: ImportGraph, *, include_weak: bool = True) -> dict[str, ModuleMetrics]:
    """Her modül için Ca, Ce, instability ve derinlik."""
    adjacency = graph.adjacency(include_weak=include_weak)
    depths = condensation_depths(adjacency)
    cyclic = {module for component in cycles(adjacency) for module in component}

    result: dict[str, ModuleMetrics] = {}
    for module in graph.modules:
        ce = len(graph.imports_of(module, include_weak=include_weak))
        ca = len(graph.importers_of(module, include_weak=include_weak))
        total = ca + ce
        result[module] = ModuleMetrics(
            module=module,
            ca=ca,
            ce=ce,
            instability=round(ce / total, 4) if total else None,
            depth=depths.get(module),
            in_cycle=module in cyclic,
        )
    return result


def normalised_depth(depth: int | None, maximum: int) -> float | None:
    """Derinliği 0-1 aralığına çeker; katman güven skoru bunu kullanır."""
    if depth is None or maximum <= 0:
        return None
    return round(min(depth, maximum) / maximum, 4)
