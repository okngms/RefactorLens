"""SCC, derinlik ve modül ölçütleri testleri."""

from pathlib import Path

import pytest

from rlens.analysis.graph import (
    condensation_depths,
    cycles,
    module_metrics,
    normalised_depth,
    strongly_connected_components,
)
from rlens.analysis.imports import build_import_graph
from rlens.analysis.parser import parse_project
from rlens.config import load_config

LAYERED = Path(__file__).resolve().parent.parent / "examples" / "layered_project"


class TestStronglyConnectedComponents:
    def test_isolated_nodes(self):
        components = strongly_connected_components({"a": set(), "b": set()})
        assert components == [frozenset({"a"}), frozenset({"b"})]

    def test_chain_has_no_cycle(self):
        adjacency = {"a": {"b"}, "b": {"c"}, "c": set()}
        assert all(len(c) == 1 for c in strongly_connected_components(adjacency))

    def test_two_node_cycle(self):
        adjacency = {"a": {"b"}, "b": {"a"}}
        assert strongly_connected_components(adjacency) == [frozenset({"a", "b"})]

    def test_three_node_cycle(self):
        adjacency = {"a": {"b"}, "b": {"c"}, "c": {"a"}}
        assert strongly_connected_components(adjacency) == [frozenset({"a", "b", "c"})]

    def test_cycle_plus_tail(self):
        adjacency = {"a": {"b"}, "b": {"a"}, "c": {"a"}, "d": set()}
        components = strongly_connected_components(adjacency)
        assert frozenset({"a", "b"}) in components
        assert frozenset({"c"}) in components

    def test_deep_chain_does_not_overflow(self):
        """Özyinelemeli Tarjan burada yığını taşırırdı."""
        size = 2000
        adjacency = {str(i): {str(i + 1)} for i in range(size)}
        adjacency[str(size)] = set()
        assert len(strongly_connected_components(adjacency)) == size + 1

    def test_result_is_deterministic(self):
        adjacency = {"z": {"a"}, "a": {"z"}, "m": set()}
        assert strongly_connected_components(adjacency) == strongly_connected_components(adjacency)


class TestCycles:
    def test_chain_has_none(self):
        assert cycles({"a": {"b"}, "b": set()}) == []

    def test_two_node_cycle_is_reported(self):
        assert cycles({"a": {"b"}, "b": {"a"}}) == [frozenset({"a", "b"})]

    def test_self_loop_is_a_cycle(self):
        assert cycles({"a": {"a"}}) == [frozenset({"a"})]

    def test_single_node_without_self_loop_is_not(self):
        assert cycles({"a": set()}) == []


class TestDepths:
    def test_chain(self):
        depths = condensation_depths({"a": {"b"}, "b": {"c"}, "c": set()})
        assert (depths["a"], depths["b"], depths["c"]) == (0, 1, 2)

    def test_isolated_nodes_are_zero(self):
        assert condensation_depths({"a": set(), "b": set()}) == {"a": 0, "b": 0}

    def test_longest_path_wins(self):
        """Bir modül birden çok zincirdeyse en derin konumu geçerlidir."""
        adjacency = {"a": {"b", "c"}, "b": {"d"}, "c": set(), "d": {"c"}}
        depths = condensation_depths(adjacency)
        assert depths["c"] == 3

    def test_cycle_members_share_a_depth(self):
        """Döngü içinde 'daha derin' sorusu anlamsızdır."""
        adjacency = {"a": {"b"}, "b": {"c"}, "c": {"b"}}
        depths = condensation_depths(adjacency)
        assert depths["b"] == depths["c"]

    def test_cycle_does_not_break_ordering(self):
        adjacency = {"a": {"b"}, "b": {"c"}, "c": {"b"}, "d": {"a"}}
        depths = condensation_depths(adjacency)
        assert depths["d"] < depths["a"] < depths["b"]


class TestNormalisedDepth:
    def test_scales_to_unit_range(self):
        assert normalised_depth(2, 4) == 0.5

    def test_none_depth(self):
        assert normalised_depth(None, 4) is None

    def test_zero_maximum(self):
        assert normalised_depth(0, 0) is None

    def test_clamps_above_maximum(self):
        assert normalised_depth(9, 4) == 1.0


def graph_from(tmp_path, files):
    (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
    for name, source in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    modules, _ = parse_project(tmp_path, (".",), ())
    return build_import_graph(modules)


class TestModuleMetrics:
    def test_afferent_and_efferent(self, tmp_path):
        graph = graph_from(
            tmp_path, {"a.py": "import c\n", "b.py": "import c\n", "c.py": "x = 1\n"}
        )
        metrics = module_metrics(graph)
        assert metrics["c"].ca == 2
        assert metrics["c"].ce == 0
        assert metrics["a"].ce == 1

    def test_instability_of_a_pure_consumer(self, tmp_path):
        graph = graph_from(tmp_path, {"a.py": "import b\n", "b.py": "x = 1\n"})
        assert module_metrics(graph)["a"].instability == 1.0

    def test_instability_of_a_pure_provider(self, tmp_path):
        graph = graph_from(tmp_path, {"a.py": "import b\n", "b.py": "x = 1\n"})
        assert module_metrics(graph)["b"].instability == 0.0

    def test_isolated_module_has_no_instability(self, tmp_path):
        """Sıfır yanıltıcı olurdu: bağlantısı yok, kararsız değil."""
        graph = graph_from(tmp_path, {"a.py": "x = 1\n"})
        assert module_metrics(graph)["a"].instability is None

    def test_cycle_membership_is_flagged(self, tmp_path):
        graph = graph_from(
            tmp_path,
            {
                "a.py": "import b\n",
                "b.py": "def f():\n    import a\n    return a\n",
            },
        )
        metrics = module_metrics(graph)
        assert metrics["a"].in_cycle is True

    def test_weak_edges_can_be_excluded(self, tmp_path):
        """Zayıf import hariç tutulunca döngü kaybolabilir."""
        graph = graph_from(
            tmp_path,
            {
                "a.py": "import b\n",
                "b.py": "def f():\n    import a\n    return a\n",
            },
        )
        assert module_metrics(graph, include_weak=False)["a"].in_cycle is False

    def test_serialisation(self, tmp_path):
        graph = graph_from(tmp_path, {"a.py": "import b\n", "b.py": "x = 1\n"})
        payload = module_metrics(graph)["a"].to_dict()
        assert payload["ce"] == 1
        assert "instability" in payload


@pytest.fixture(scope="module")
def layered():
    config = load_config(search_from=LAYERED)
    modules, _ = parse_project(LAYERED, config.scan.include, config.scan.exclude)
    return module_metrics(build_import_graph(modules))


class TestLayeredFixture:
    def test_shared_modules_are_the_only_cycle(self, layered):
        in_cycle = {name for name, m in layered.items() if m.in_cycle}
        assert in_cycle == {"src.shared.helpers", "src.shared.registry"}

    def test_domain_entities_is_maximally_stable(self, layered):
        """Domain hiçbir şeye bağımlı değil, çok şey ona bağımlı."""
        entities = layered["src.domain.entities"]
        assert entities.ce == 0
        assert entities.instability == 0.0

    def test_presentation_is_maximally_unstable(self, layered):
        for name in ("src.api.order_controller", "src.api.report_view"):
            assert layered[name].instability == 1.0

    def test_presentation_sits_at_the_top(self, layered):
        assert layered["src.api.order_controller"].depth == 0
        assert layered["src.api.report_view"].depth == 0

    def test_domain_is_deepest(self, layered):
        depths = {name: m.depth for name, m in layered.items()}
        assert depths["src.domain.entities"] == max(depths.values())

    def test_service_layer_sits_between(self, layered):
        assert (
            layered["src.api.order_controller"].depth
            < layered["src.services.order_service"].depth
            < layered["src.domain.entities"].depth
        )

    def test_repository_is_the_most_depended_on_infrastructure(self, layered):
        """Üç modül onu import ediyor; hepsi de ihlal (LV-DIR + iki LV-SKIP)."""
        assert layered["src.infra.order_repository"].ca == 3
