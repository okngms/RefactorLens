"""Import grafiği testleri."""

from pathlib import Path

import pytest

from rlens.analysis.imports import build_import_graph
from rlens.analysis.parser import parse_project
from rlens.config import load_config

LAYERED = Path(__file__).resolve().parent.parent / "examples" / "layered_project"


def build(tmp_path, files: dict[str, str]):
    """Verilen dosyalardan bir proje kurup import grafiğini döndürür."""
    (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
    for name, source in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    modules, _ = parse_project(tmp_path, (".",), ())
    return build_import_graph(modules)


class TestResolution:
    def test_direct_import(self, tmp_path):
        graph = build(tmp_path, {"a.py": "import b\n", "b.py": "x = 1\n"})
        assert graph.imports_of("a") == {"b"}

    def test_from_import(self, tmp_path):
        graph = build(tmp_path, {"a.py": "from b import x\n", "b.py": "x = 1\n"})
        assert graph.imports_of("a") == {"b"}

    def test_dotted_module(self, tmp_path):
        graph = build(
            tmp_path,
            {"a.py": "from pkg.core import x\n", "pkg/core.py": "x = 1\n"},
        )
        assert graph.imports_of("a") == {"pkg.core"}

    def test_from_package_import_submodule(self, tmp_path):
        """`from pkg import core` — core bir alt modül olabilir."""
        graph = build(
            tmp_path,
            {"a.py": "from pkg import core\n", "pkg/core.py": "x = 1\n"},
        )
        assert "pkg.core" in graph.imports_of("a")

    def test_suffix_match_across_a_src_root(self, tmp_path):
        """Modül `src.domain.entities`, kod `from domain.entities import` yazar."""
        graph = build(
            tmp_path,
            {
                "src/api/view.py": "from domain.entities import Order\n",
                "src/domain/entities.py": "class Order: pass\n",
            },
        )
        assert graph.imports_of("src.api.view") == {"src.domain.entities"}

    def test_stdlib_is_ignored(self, tmp_path):
        graph = build(tmp_path, {"a.py": "import json\nimport os\n"})
        assert graph.edges == []

    def test_third_party_is_ignored(self, tmp_path):
        graph = build(tmp_path, {"a.py": "from httpx import Client\n"})
        assert graph.edges == []

    def test_self_import_is_not_an_edge(self, tmp_path):
        graph = build(tmp_path, {"a.py": "from a import x\n"})
        assert graph.edges == []

    def test_duplicate_imports_collapse(self, tmp_path):
        graph = build(
            tmp_path,
            {"a.py": "from b import x\nfrom b import y\n", "b.py": "x = y = 1\n"},
        )
        assert len(graph.edges_between("a", "b")) == 1

    def test_ambiguous_suffix_is_left_unresolved(self, tmp_path):
        """Yanlış kenar, olmayan kenardan kötüdür: olmayan bir ihlal üretir."""
        graph = build(
            tmp_path,
            {
                "a.py": "from shared.util import x\n",
                "one/shared/util.py": "x = 1\n",
                "two/shared/util.py": "x = 1\n",
            },
        )
        assert graph.imports_of("a") == set()
        assert any("ambiguous" in u.reason for u in graph.unresolved)

    def test_unknown_module_is_not_reported_as_unresolved(self, tmp_path):
        """Üçüncü parti importlar gürültü üretmemeli."""
        graph = build(tmp_path, {"a.py": "from requests import get\n"})
        assert graph.unresolved == []


class TestRelativeImports:
    def test_same_package(self, tmp_path):
        graph = build(
            tmp_path,
            {
                "pkg/__init__.py": "",
                "pkg/a.py": "from .b import x\n",
                "pkg/b.py": "x = 1\n",
            },
        )
        assert graph.imports_of("pkg.a") == {"pkg.b"}

    def test_parent_package(self, tmp_path):
        graph = build(
            tmp_path,
            {
                "pkg/__init__.py": "",
                "pkg/core.py": "x = 1\n",
                "pkg/sub/__init__.py": "",
                "pkg/sub/a.py": "from ..core import x\n",
            },
        )
        assert "pkg.core" in graph.imports_of("pkg.sub.a")

    def test_bare_relative_import(self, tmp_path):
        graph = build(
            tmp_path,
            {
                "pkg/__init__.py": "",
                "pkg/a.py": "from . import b\n",
                "pkg/b.py": "x = 1\n",
            },
        )
        assert "pkg.b" in graph.imports_of("pkg.a")


class TestWeakImports:
    """Fonksiyon içindeki import gerçek bir bağımlılıktır, ama farklı ağırlıkta."""

    def test_module_level_import_is_strong(self, tmp_path):
        graph = build(tmp_path, {"a.py": "import b\n", "b.py": "x = 1\n"})
        assert graph.edges[0].weak is False

    def test_function_level_import_is_weak(self, tmp_path):
        graph = build(
            tmp_path,
            {"a.py": "def f():\n    import b\n    return b\n", "b.py": "x = 1\n"},
        )
        assert graph.edges[0].weak is True

    def test_conditional_import_is_weak(self, tmp_path):
        graph = build(
            tmp_path,
            {"a.py": "if True:\n    import b\n", "b.py": "x = 1\n"},
        )
        assert graph.edges[0].weak is True

    def test_try_import_is_weak(self, tmp_path):
        graph = build(
            tmp_path,
            {"a.py": "try:\n    import b\nexcept ImportError:\n    b = None\n", "b.py": "x=1\n"},
        )
        assert graph.edges[0].weak is True

    def test_weak_edges_can_be_excluded(self, tmp_path):
        graph = build(
            tmp_path,
            {"a.py": "def f():\n    import b\n", "b.py": "x = 1\n"},
        )
        assert graph.imports_of("a", include_weak=False) == set()
        assert graph.imports_of("a", include_weak=True) == {"b"}


class TestGraphShape:
    def test_isolated_modules_appear_in_adjacency(self, tmp_path):
        graph = build(tmp_path, {"a.py": "x = 1\n", "b.py": "x = 1\n"})
        assert set(graph.adjacency()) == {"a", "b"}

    def test_importers_of(self, tmp_path):
        graph = build(
            tmp_path,
            {"a.py": "import c\n", "b.py": "import c\n", "c.py": "x = 1\n"},
        )
        assert graph.importers_of("c") == {"a", "b"}

    def test_edges_are_deterministic(self, tmp_path):
        files = {"z.py": "import a\n", "a.py": "x = 1\n", "m.py": "import a\n"}
        first = build(tmp_path, files)
        second = build_import_graph(parse_project(tmp_path, (".",), ())[0])
        assert [e.to_dict() for e in first.edges] == [e.to_dict() for e in second.edges]

    def test_serialisation(self, tmp_path):
        graph = build(tmp_path, {"a.py": "import b\n", "b.py": "x = 1\n"})
        payload = graph.to_dict()
        assert payload["edges"][0]["source"] == "a"
        assert "unresolved" in payload


@pytest.fixture(scope="module")
def graph():
    config = load_config(search_from=LAYERED)
    modules, _ = parse_project(LAYERED, config.scan.include, config.scan.exclude)
    return build_import_graph(modules)


class TestLayeredFixture:
    """ARCH_SMELLS.md'deki kenarların hepsi bulunmalı, fazlası bulunmamalı."""

    def test_module_count(self, graph):
        assert len(graph.modules) == 10

    def test_everything_resolves(self, graph):
        """Fikstürde çözülemeyen import olmamalı."""
        assert graph.unresolved == []

    def test_lv_dir_edge_exists(self, graph):
        """domain → infrastructure: yön ihlali."""
        assert "src.infra.order_repository" in graph.imports_of("src.domain.policies")

    def test_lv_skip_edges_exist(self, graph):
        """presentation → infrastructure: katman atlama."""
        targets = graph.imports_of("src.api.report_view")
        assert "src.infra.email_client" in targets
        assert "src.infra.order_repository" in targets

    def test_report_view_does_not_use_the_application_layer(self, graph):
        assert not any(
            t.startswith("src.services") for t in graph.imports_of("src.api.report_view")
        )

    def test_cycle_edges_exist_in_both_directions(self, graph):
        assert "src.shared.registry" in graph.imports_of("src.shared.helpers")
        assert "src.shared.helpers" in graph.imports_of("src.shared.registry")

    def test_domain_entities_imports_nothing(self, graph):
        """Domain hiçbir katmana bağımlı olmamalı — entities bu kurala uyar."""
        assert graph.imports_of("src.domain.entities") == set()

    def test_edge_count(self, graph):
        assert len(graph.edges) == 11
