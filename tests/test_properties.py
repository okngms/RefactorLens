"""Özellik tabanlı testler (sertleştirme Blok 4, madde 2).

Altın değer testleri tek tek örnekleri sabitler; bunlar ise metriklerin
**tanımından** gelen ilişkileri rastgele üretilmiş kodda sınar. Bir kural
bozulursa hypothesis en küçük karşı örneği gösterir.

Sabitlenen ilişkiler:

* Dunder olmayan yeni bir metot NOM'u tam 1 artırır; dunder değiştirmez.
* Bir metoda `self.x` okuması eklemek LCOM4'ü artırmaz (bileşenleri yalnızca
  birleştirebilir).
* Bir parametre eklemek PARAMS'ı tam 1 artırır.
* Metodu olmayan sınıfta NOM 0, WMC 0, LCOM4 `null` (K2).
* İki modül arasına yeni bir import eklemek, içe aktaranın Ce'sini ve içe
  aktarılanın Ca'sını tam 1 artırır.
* Tarama raporu JSON'a yazılıp okunduğunda kayıpsızdır.
"""

from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from rlens.analysis.class_metrics import measure_class
from rlens.analysis.func_metrics import code_lines, measure_function
from rlens.analysis.scanner import scan_project
from rlens.config import load_config
from rlens.report.files import read_report, write_report

ATTRIBUTES = ("a", "b", "c", "d")
METHOD_NAMES = tuple(f"m{i}" for i in range(6))

# Tarama tabanlı özellikler dosya sistemine yazar; örnek sayısı düşük tutulur.
# `derandomize` ve veritabanısız: her koşu aynı örnekleri üretir. Rastgele
# tohum CI'da ara sıra düşen (flaky) bir test ve mutation skorunda gürültü
# demekti; keşif gücünden bu kadarı bilerek verildi.
SCAN = settings(
    max_examples=40,
    deadline=None,
    derandomize=True,
    database=None,
    suppress_health_check=[HealthCheck.too_slow],
)
FAST = settings(max_examples=150, deadline=None, derandomize=True, database=None)


@st.composite
def methods(draw, min_size: int = 0):
    """(ad, yazılan, okunan, çağrılan) dörtlülerinin listesi; adlar benzersiz."""
    names = draw(st.lists(st.sampled_from(METHOD_NAMES), min_size=min_size, unique=True))
    result = []
    for name in names:
        writes = draw(st.sets(st.sampled_from(ATTRIBUTES)))
        reads = draw(st.sets(st.sampled_from(ATTRIBUTES)))
        calls = draw(st.sets(st.sampled_from(names)))
        result.append((name, writes, reads, calls - {name}))
    return result


def class_source(spec, extra: str = "") -> str:
    lines = ["class C:"]
    for name, writes, reads, calls in spec:
        lines.append(f"    def {name}(self):")
        body = [f"self.{attr} = 1" for attr in sorted(writes)]
        body += [f"_ = self.{attr}" for attr in sorted(reads)]
        body += [f"self.{other}()" for other in sorted(calls)]
        lines += [f"        {line}" for line in body or ["pass"]]
    if extra:
        lines.append(extra)
    if len(lines) == 1:
        lines.append("    pass")
    return "\n".join(lines) + "\n"


def measure(source: str):
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    return measure_class(node, module="m", code_lines=code_lines(source))


def add_line(source: str, method: str, line: str) -> str:
    """`method`'un gövdesinin başına bir satır ekler."""
    header = f"    def {method}(self):\n"
    return source.replace(header, header + f"        {line}\n", 1)


class TestClassProperties:
    @FAST
    @given(spec=methods(), new=st.sampled_from(("extra", "__repr__")))
    def test_a_new_method_adds_one_to_nom_unless_dunder(self, spec, new):
        before = measure(class_source(spec))
        after = measure(class_source(spec, f"    def {new}(self):\n        return 1"))
        assert after.nom == before.nom + (0 if new.startswith("__") else 1)

    @FAST
    @given(spec=methods(min_size=1), data=st.data())
    def test_reading_an_attribute_never_raises_lcom4(self, spec, data):
        method = data.draw(st.sampled_from([name for name, *_ in spec]))
        attribute = data.draw(st.sampled_from(ATTRIBUTES))
        source = class_source(spec)
        before = measure(source)
        after = measure(add_line(source, method, f"_ = self.{attribute}"))
        assert after.lcom4 <= before.lcom4

    @FAST
    @given(assignments=st.lists(st.sampled_from(ATTRIBUTES), max_size=3))
    def test_a_class_without_methods(self, assignments):
        body = [f"    {name} = 1" for name in assignments] or ["    pass"]
        report = measure("class C:\n" + "\n".join(body) + "\n")
        assert (report.nom, report.wmc, report.lcom4) == (0, 0, None)


class TestFunctionProperties:
    @FAST
    @given(
        count=st.integers(min_value=0, max_value=8),
        star=st.booleans(),
        double_star=st.booleans(),
    )
    def test_one_more_parameter_adds_exactly_one(self, count, star, double_star):
        def source(n: int) -> str:
            params = [f"p{i}" for i in range(n)]
            if star:
                params.append("*args")
            if double_star:
                params.append("**kwargs")
            return f"def f({', '.join(params)}):\n    return 1\n"

        def params(text: str) -> int:
            node = ast.parse(text).body[0]
            return measure_function(node, code_lines=code_lines(text)).param_count

        assert params(source(count + 1)) == params(source(count)) + 1


def scan(files: dict[str, str]):
    with tempfile.TemporaryDirectory() as workdir:
        root = Path(workdir)
        (root / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        for name, text in files.items():
            (root / name).write_text(text, encoding="utf-8")
        return scan_project(root, load_config(search_from=root))


@st.composite
def module_graphs(draw):
    """2-5 düz modül ve aralarında rastgele import kenarları (kendine değil)."""
    count = draw(st.integers(min_value=2, max_value=5))
    names = [f"m{i}" for i in range(count)]
    pairs = [(a, b) for a in names for b in names if a != b]
    edges = draw(st.sets(st.sampled_from(pairs)))
    return names, edges


def sources(names, edges) -> dict[str, str]:
    files = {}
    for name in names:
        imports = sorted(target for source, target in edges if source == name)
        files[f"{name}.py"] = "".join(f"import {t}\n" for t in imports) + "x = 1\n"
    return files


class TestCouplingProperties:
    @SCAN
    @given(graph=module_graphs(), data=st.data())
    def test_a_new_import_adds_one_to_ce_and_ca(self, graph, data):
        names, edges = graph
        missing = [(a, b) for a in names for b in names if a != b and (a, b) not in edges]
        if not missing:
            return
        source, target = data.draw(st.sampled_from(missing))

        def coupling(edge_set):
            report = scan(sources(names, edge_set))
            return {m.module: (m.ca, m.ce) for m in report.modules}

        before = coupling(edges)
        after = coupling(edges | {(source, target)})
        assert after[source][1] == before[source][1] + 1
        assert after[target][0] == before[target][0] + 1
        for name in set(names) - {source, target}:
            assert after[name] == before[name]


class TestReportRoundTrip:
    @SCAN
    @given(spec=methods(), functions=st.integers(min_value=0, max_value=3))
    def test_written_report_reads_back_unchanged(self, spec, functions):
        text = class_source(spec) + "".join(
            f"\ndef f{i}(a, b=1):\n    if a:\n        return b\n    return a\n"
            for i in range(functions)
        )
        report = scan({"mod.py": text})
        expected = json.loads(json.dumps(report.to_dict()))
        with tempfile.TemporaryDirectory() as out:
            assert read_report(write_report(report, Path(out))) == expected
