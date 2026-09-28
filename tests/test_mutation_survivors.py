"""Mutation testing'in bulduğu test boşlukları (sertleştirme Blok 4, madde 3).

`experiments/hardening/mutation.py` `src/rlens/analysis`'i değiştirip test
setini koşar; testler geçerse mutant "hayatta kalmıştır" ve bir davranış
sınanmıyordur. Buradaki her test en az bir hayatta kalan mutantı öldürür;
mutant satırı testin docstring'inde. Eşdeğer ya da ulaşılamaz olanlar
testsiz bırakıldı ve gerekçeleriyle `experiments/hardening/mutation.md`'de.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from rlens.analysis.architecture import LV_CYCLE, LV_DIR, LV_SKIP, analyse, classify_edge
from rlens.analysis.class_metrics import assigned_attributes, cam, dcc, is_stub_body, measure_class
from rlens.analysis.entry_points import CLI, decorator_kind
from rlens.analysis.func_metrics import code_lines, function_loc
from rlens.analysis.graph import module_metrics
from rlens.analysis.imports import ImportEdge, ImportGraph, _Resolver, build_import_graph
from rlens.analysis.interface import public_interface
from rlens.analysis.model import ARCH_SCHEMA_VERSION
from rlens.analysis.parser import SkippedFile, parse_file, parse_project
from rlens.analysis.scanner import scan_project
from rlens.analysis.smells import (
    LAYER_MISFIT,
    detect_class_smells,
    detect_data_class,
    detect_feature_envy,
    detect_layer_misfit,
)
from rlens.config import load_config


def write(root: Path, files: dict[str, str], config: str = "scan:\n  include: ['.']\n") -> None:
    (root / "rlens.yaml").write_text(config, encoding="utf-8")
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def arch_report(root: Path, files: dict[str, str], arch: str = ""):
    write(root, files, "scan:\n  include: ['.']\n" + arch)
    config = load_config(search_from=root)
    modules, _ = parse_project(root, config.scan.include, config.scan.exclude)
    return analyse(modules, build_import_graph(modules), config.arch)


def the_class(source: str) -> ast.ClassDef:
    return next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef))


def measured(source: str):
    return measure_class(the_class(source), module="m", code_lines=code_lines(source))


DECLARED = """arch:
  layers:
    presentation: ["api/"]
    application: ["services/"]
    domain: ["domain/"]
    infrastructure: ["infra/"]
"""


# --------------------------------------------------------------------------- #
# architecture.py
# --------------------------------------------------------------------------- #


class TestArchitecture:
    @pytest.fixture
    def scheme(self, tmp_path):
        """Hiçbir katmanın hiçbir yere izni olmayan üç katmanlı şema."""
        write(
            tmp_path,
            {},
            "arch:\n  scheme:\n    layers: [x, a, b]\n"
            "    allowed: {x: [], a: [], b: []}\n    allow_skip: false\n",
        )
        return load_config(search_from=tmp_path).arch.scheme

    def test_adjacent_layers_without_permission_either_way(self, scheme):
        """`return LV_DIR` → None; `> 1` → `>= 1`, `1` → `2`, `-` → `+`; `and` → `or`."""
        assert classify_edge(scheme, "a", "b") == LV_DIR
        assert classify_edge(scheme, "b", "a") == LV_DIR

    def test_distance_two_is_a_skip(self, scheme):
        assert classify_edge(scheme, "x", "b") == LV_SKIP

    def test_cycle_across_layers_names_its_ends(self, tmp_path):
        """`members[0]`/`members[-1]` ve katman aramalarındaki indeks mutantları."""
        report = arch_report(
            tmp_path,
            {
                "api/v.py": "import domain.p\n",
                "domain/p.py": "import infra.r\n",
                "infra/r.py": "import api.v\n",
            },
            DECLARED,
        )
        (cycle,) = report.with_code(LV_CYCLE)
        assert (cycle.source, cycle.target) == ("api.v", "infra.r")
        assert (cycle.source_layer, cycle.target_layer) == ("presentation", "infrastructure")

    def test_unassigned_modules_are_counted(self, tmp_path):
        """`not a.is_known` → `a.is_known`."""
        report = arch_report(
            tmp_path,
            {"domain/a.py": "x = 1\n", "misc/b.py": "x = 1\n", "misc/c.py": "x = 1\n"},
            DECLARED,
        )
        assert any(n.startswith("2 module(s) match no declared prefix") for n in report.notes)

    def test_no_prefix_note_without_a_declaration(self, tmp_path):
        """`unassigned and has_declaration` → `or`."""
        report = arch_report(tmp_path, {"misc/b.py": "x = 1\n"})
        assert not any("match no declared prefix" in n for n in report.notes)

    def test_unannotated_classes_are_counted_exactly(self, tmp_path):
        """`unannotated = 0` → 1, `+= 1` → 2, `is None or not known` → `and`."""
        report = arch_report(
            tmp_path,
            {
                "domain/a.py": "class A:\n    def f(self, x):\n        return x\n"
                "class B:\n    def g(self, y):\n        return y\n",
                "misc/c.py": "class C:\n    def h(self, z):\n        return z\n",
            },
            DECLARED,
        )
        assert any(n.startswith("2 class(es) have no annotated") for n in report.notes)


# --------------------------------------------------------------------------- #
# class_metrics.py
# --------------------------------------------------------------------------- #


class TestClassMetrics:
    def test_docstring_then_real_code_is_not_a_stub(self):
        """`body[1:]` → `body[2:]`."""
        method = ast.parse('def f(self):\n    "doc"\n    return 1\n').body[0]
        assert is_stub_body(method) is False

    def test_annotated_counts_its_type_not_its_metadata(self):
        """`inner.elts[0]` → `inner.elts[1]`.

        Metadata bir proje sınıfının adını taşıyorsa ayrım görünür: adlar başka
        bir geçişte zaten sayıldığı için `'meta'` gibi bir string mutantı
        öldürmüyordu.
        """
        source = (
            "from typing import Annotated\n"
            "class C:\n    def f(self, o: Annotated[Order, 'Customer']):\n        return o\n"
        )
        assert dcc(the_class(source), frozenset({"C", "Order", "Customer"})) == 1

    def test_non_constant_slot_entry_does_not_crash(self):
        """`isinstance(element, Constant) and ...` → `or` (AttributeError)."""
        source = "NAME = 'b'\nclass C:\n    __slots__ = ('a', NAME)\n"
        assert assigned_attributes(the_class(source)) == {"a"}

    def test_cam_at_exactly_the_coverage_threshold(self):
        """`coverage < min` → `<=`: 7/10 parametre annotation'lı, eşik 0.7."""
        params = ", ".join([f"a{i}: int" for i in range(7)] + [f"b{i}" for i in range(3)])
        source = f"class C:\n    def f(self, {params}):\n        return 1\n"
        result = cam(the_class(source), 0.7)
        assert result.value is not None


# --------------------------------------------------------------------------- #
# entry_points.py
# --------------------------------------------------------------------------- #


def kind(decorator: str) -> str | None:
    function = ast.parse(f"@{decorator}\ndef f():\n    pass\n").body[0]
    return decorator_kind(function.decorator_list[0])


class TestEntryPoints:
    def test_only_path_keywords_are_read(self):
        """`keyword.arg in keywords and ...` → `or`: rastgele bir anahtar kelime okunmaz."""
        assert kind('things.option(help="-x")') is None
        assert kind('app.get(summary="/x")') is None

    def test_subscript_decorator_is_not_an_entry_point(self):
        """`return "", None, call` → None (unpack hatası)."""
        assert kind('registry["cmd"]') is None

    def test_attribute_command_without_call(self):
        """`owner is not None or call is not None` → `and`."""
        assert kind("app.command") == CLI

    def test_bare_command_needs_a_call(self):
        """`owner is not None` → `is None`."""
        assert kind("command") is None
        assert kind("command()") == CLI

    def test_option_with_a_dash_from_an_unknown_owner(self):
        """`return CLI` → None."""
        assert kind('options.option("--verbose")') == CLI

    def test_option_without_arguments(self):
        """`first is not None and ...` → `is None` (AttributeError)."""
        assert kind("things.option()") is None


# --------------------------------------------------------------------------- #
# func_metrics.py
# --------------------------------------------------------------------------- #


class TestFunctionMetrics:
    def test_the_line_after_the_function_is_not_counted(self):
        """`range(lineno, end + 1)` → `end + 2`."""
        source = "def f():\n    return 1\nx = 2\n"
        node = ast.parse(source).body[0]
        assert function_loc(node, code_lines(source)) == 2


# --------------------------------------------------------------------------- #
# graph.py ve imports.py
# --------------------------------------------------------------------------- #


def graph_of(edges: list[tuple[str, str, bool]]) -> ImportGraph:
    modules = tuple(sorted({m for s, t, _ in edges for m in (s, t)}))
    return ImportGraph(modules=modules, edges=[ImportEdge(s, t, weak, 1) for s, t, weak in edges])


class TestGraph:
    def test_cycle_depth(self):
        """`a != b and b not in dag[a]` → `or`: döngü kendine kenar alırdı.

        Döngü bileşeni kuyruğa hiç girmese de kendi derinliği yine güncellenir;
        hata ancak döngünün **aşağısındaki** modülde (`d`) görünür.
        """
        metrics = module_metrics(
            graph_of([("c", "a", False), ("a", "b", False), ("b", "a", False), ("b", "d", False)])
        )
        assert {m: metrics[m].depth for m in "abcd"} == {"a": 1, "b": 1, "c": 0, "d": 2}


def test_normalised_depth_with_a_maximum_of_one():
    """`maximum <= 0` → `<= 1`. Fonksiyon katman çıkarımı için ayrılmış; bugün
    yalnızca testlerde çağrılıyor."""
    from rlens.analysis.graph import normalised_depth

    assert normalised_depth(1, 1) == 1.0


class TestImports:
    @pytest.fixture
    def graph(self):
        return graph_of([("a", "b", False), ("a", "c", True)])

    def test_weak_edges_are_included_by_default(self, graph):
        """`include_weak=True` varsayılanları → False."""
        assert graph.imports_of("a") == {"b", "c"}
        assert graph.importers_of("c") == {"a"}
        assert graph.adjacency()["a"] == {"b", "c"}

    def test_weak_edges_can_be_excluded(self, graph):
        """`not edge.weak` → `edge.weak`."""
        assert graph.imports_of("a", include_weak=False) == {"b"}
        assert graph.importers_of("c", include_weak=False) == set()
        assert graph.adjacency(include_weak=False)["a"] == {"b"}

    def test_edges_between_needs_both_ends(self, graph):
        """`source == s and target == t` → `or`."""
        assert [(e.source, e.target) for e in graph.edges_between("a", "b")] == [("a", "b")]
        assert graph.edges_between("b", "a") == []

    def test_empty_target(self):
        """`return None, "empty import target"` → None."""
        assert _Resolver(("a",)).resolve("") == (None, "empty import target")

    def test_dotted_root_strips_its_last_part(self):
        """`last == root` → `!=`: `pkg.core` kökünde `core.a` → `a`."""
        assert _Resolver(("a",), root_package="pkg.core").resolve("core.a") == ("a", "")

    def test_partly_resolved_import_is_not_unresolved(self, tmp_path):
        """`resolved_any = True` → False."""
        write(
            tmp_path,
            {
                "x/util.py": "x = 1\n",
                "y/util.py": "y = 1\n",
                "z.py": "z = 1\n",
                "m.py": "import util, z\n",
            },
        )
        modules, _ = parse_project(tmp_path, (".",), ())
        graph = build_import_graph(modules)
        assert [u.source for u in graph.unresolved] == []
        assert ("m", "z") in {(e.source, e.target) for e in graph.edges}


# --------------------------------------------------------------------------- #
# interface.py, model.py
# --------------------------------------------------------------------------- #


class TestInterface:
    def test_a_string_tuple_is_not_slots(self):
        """`isinstance(x, Name) and x.id == "__slots__"` → `or`."""
        interface = public_interface(the_class("class C:\n    names = ('p', 'q')\n"))
        assert interface.attributes == ("names",)


def test_arch_schema_version_is_pinned():
    """`ARCH_SCHEMA_VERSION = 1` → 2. Bir artış bilinçli olmalı (`docs/04` §1)."""
    assert ARCH_SCHEMA_VERSION == 1


# --------------------------------------------------------------------------- #
# parser.py, scanner.py
# --------------------------------------------------------------------------- #


class TestParser:
    def test_unreadable_path_is_skipped_without_the_path(self, tmp_path):
        """`return SkippedFile(...)` → None; `strerror or exc` → `and`."""
        folder = tmp_path / "pkg.py"
        folder.mkdir()
        result = parse_file(folder, tmp_path)
        assert isinstance(result, SkippedFile)
        assert result.reason.startswith("unreadable: ")
        # `exc`'in metni `[Errno 13] ...: 'yol'` biçimindedir; `strerror` değildir.
        assert "Errno" not in result.reason

    def test_syntax_error_names_the_line(self, tmp_path):
        """`exc.lineno or "?"` → `and`."""
        (tmp_path / "bad.py").write_text("x = = 1\n", encoding="utf-8")
        assert "(line 1)" in parse_file(tmp_path / "bad.py", tmp_path).reason

    def test_recursion_error_is_skipped(self, tmp_path):
        """`return SkippedFile(... could not parse ...)` → None."""
        (tmp_path / "deep.py").write_text("1" + "+1" * 200_000 + "\n", encoding="utf-8")
        result = parse_file(tmp_path / "deep.py", tmp_path)
        assert result.reason == "could not parse: RecursionError"


class TestScanner:
    def test_module_function_keeps_a_parameter_named_self(self, tmp_path):
        """`measure_function(..., is_method=False)` → True."""
        write(tmp_path, {"m.py": "def helper(self, x):\n    return x\n"})
        report = scan_project(tmp_path, load_config(search_from=tmp_path))
        assert report.modules[0].functions[0].param_count == 2

    def test_a_cycle_alone_does_not_make_a_misfit(self, tmp_path):
        """`v.code != LV_CYCLE` → `==`: döngü `layer_misfit` için ihlal sayılmaz."""
        write(
            tmp_path,
            {
                "domain/a.py": "import domain.b\nclass A:\n    def f(self):\n"
                "        return domain.b.B()\n",
                "domain/b.py": "import domain.a\nclass B:\n    pass\n",
            },
            "scan:\n  include: ['.']\nthresholds:\n  dcc: {warn: 1}\n"
            'arch:\n  layers:\n    domain: ["domain/"]\n',
        )
        report = scan_project(tmp_path, load_config(search_from=tmp_path))
        labels = {s["label"] for s in report.iter_smells()}
        assert LAYER_MISFIT not in labels


# --------------------------------------------------------------------------- #
# smells.py
# --------------------------------------------------------------------------- #

DATA_HOLDER = """class C:
    def __init__(self):
        self._a = 1
        self._b = 2
        self._c = 3
    def get_a(self):
        return self._a
    def get_b(self):
        return self._b
    def get_c(self):
        return self._c
    def work(self, x):
{branches}        return 0
"""


def data_holder(branches: int) -> str:
    body = "".join(f"        if x == {i}:\n            return {i}\n" for i in range(branches))
    return DATA_HOLDER.format(branches=body)


class TestSmells:
    @pytest.fixture
    def rules(self, tmp_path):
        return load_config(search_from=tmp_path).smells

    def test_data_class_at_wmc_equal_to_nom_plus_two(self, rules):
        """`wmc <= nom + 2` → `<`: NOM 4, WMC 6."""
        source = data_holder(2)
        report = measured(source)
        assert (report.nom, report.wmc) == (4, 6)
        assert detect_data_class(the_class(source), report, rules) is not None

    def test_not_a_data_class_at_nom_plus_three(self, rules):
        """`nom + 2` → `nom + 3`: NOM 4, WMC 7."""
        source = data_holder(3)
        report = measured(source)
        assert (report.nom, report.wmc) == (4, 7)
        assert detect_data_class(the_class(source), report, rules) is None

    def test_accessor_ratio_exactly_at_the_rule(self, rules):
        """`ratio < rule` → `<=`: 3/4 erişimci, kural 0.75."""
        source = data_holder(2)
        rules = replace(rules, data_class_accessor_ratio=0.75)
        assert detect_data_class(the_class(source), measured(source), rules) is not None

    def test_feature_envy_ties_break_by_name(self, rules):
        """`key=(item[1], item[0])` → `(item[1], item[1])`."""
        source = "class C:\n    def m(self, a, b):\n        return a.x, a.y, a.z, b.x, b.y, b.z\n"
        (smell,) = detect_feature_envy(the_class(source), "m", rules)
        assert smell.evidence["envied"] == "b"

    def test_feature_envy_ratio_is_rounded_to_two_places(self, rules):
        """`round(ratio, 2)` → 3. Kanıt alanı prompt'a gider; basamağı sabit."""
        source = (
            "class C:\n    def m(self, a):\n"
            "        return a.p, a.q, a.r, a.s, a.t, a.u, a.v, self.x, self.y, self.z\n"
        )
        (smell,) = detect_feature_envy(the_class(source), "m", rules)
        assert smell.evidence["ratio"] == 2.33

    @pytest.fixture
    def coupled(self):
        return replace(measured("class C:\n    pass\n"), dcc=20)

    def test_misfit_at_exactly_the_minimum_confidence(self, tmp_path, coupled):
        """`confidence < MISFIT_MIN_CONFIDENCE` → `<=`; kanıtta `module_has_violation`."""
        config = load_config(search_from=tmp_path)
        smell = detect_layer_misfit(coupled, "domain", 0.7, {"m"}, config)
        assert smell is not None
        assert smell.evidence["module_has_violation"] is True

    def test_misfit_through_the_class_smell_entry_point(self, tmp_path, coupled):
        """`violating_modules or set()` → `and`."""
        config = load_config(search_from=tmp_path)
        smells = detect_class_smells(
            the_class("class C:\n    pass\n"),
            coupled,
            config,
            layer="domain",
            layer_confidence=1.0,
            violating_modules={"m"},
        )
        assert LAYER_MISFIT in {s.label for s in smells}
