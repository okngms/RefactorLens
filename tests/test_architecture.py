"""Katman ataması ve ihlal tespiti testleri."""

from pathlib import Path

import pytest

from rlens.analysis.architecture import (
    DECLARED,
    LV_CYCLE,
    LV_DIR,
    LV_LEAK,
    LV_SKIP,
    UNKNOWN,
    analyse,
    classify_edge,
)
from rlens.analysis.imports import build_import_graph
from rlens.analysis.parser import parse_project
from rlens.config import load_config

LAYERED = Path(__file__).resolve().parent.parent / "examples" / "layered_project"


def project(tmp_path, files: dict[str, str], config: str = ""):
    """Verilen dosyalardan bir proje kurar ve mimari raporunu döndürür."""
    (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n" + config, encoding="utf-8")
    for name, source in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    cfg = load_config(search_from=tmp_path)
    modules, _ = parse_project(tmp_path, cfg.scan.include, cfg.scan.exclude)
    return analyse(modules, build_import_graph(modules), cfg.arch)


DECLARE_FOUR = """
arch:
  layers:
    presentation: ["api/"]
    application: ["services/"]
    domain: ["domain/"]
    infrastructure: ["infra/"]
"""


class TestClassifyEdge:
    """LV-DIR ve LV-SKIP ayrımı."""

    @pytest.fixture
    def scheme(self, tmp_path):
        return load_config(search_from=tmp_path).arch.scheme

    def test_allowed_edge_is_not_a_violation(self, scheme):
        assert classify_edge(scheme, "application", "domain") is None

    def test_reverse_of_an_allowed_edge_is_a_direction_violation(self, scheme):
        """infrastructure → domain izinli; tersi yön ihlalidir."""
        assert classify_edge(scheme, "domain", "infrastructure") == LV_DIR

    def test_distant_layers_are_a_skip(self, scheme):
        assert classify_edge(scheme, "presentation", "infrastructure") == LV_SKIP

    def test_adjacent_but_forbidden_is_a_direction_violation(self, scheme):
        assert classify_edge(scheme, "domain", "application") == LV_DIR

    def test_allow_skip_disables_the_skip_rule(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text(
            "arch:\n  scheme:\n    allow_skip: true\n", encoding="utf-8"
        )
        scheme = load_config(search_from=tmp_path).arch.scheme
        assert classify_edge(scheme, "presentation", "infrastructure") is None


class TestDeclaredAssignment:
    def test_prefix_match(self, tmp_path):
        report = project(
            tmp_path,
            {"api/view.py": "x = 1\n", "domain/model.py": "x = 1\n"},
            DECLARE_FOUR,
        )
        assert report.layer_of("api.view") == "presentation"
        assert report.layer_of("domain.model") == "domain"

    def test_source_is_recorded(self, tmp_path):
        report = project(tmp_path, {"api/view.py": "x = 1\n"}, DECLARE_FOUR)
        assert report.assignments["api.view"].source == DECLARED
        assert report.assignments["api.view"].confidence == 1.0

    def test_unmatched_module_stays_unknown(self, tmp_path):
        """Tahmin zorlanmaz."""
        report = project(tmp_path, {"misc/thing.py": "x = 1\n"}, DECLARE_FOUR)
        assert report.layer_of("misc.thing") == UNKNOWN

    def test_longest_prefix_wins(self, tmp_path):
        report = project(
            tmp_path,
            {"src/api/view.py": "x = 1\n"},
            'arch:\n  layers:\n    domain: ["src/"]\n    presentation: ["src/api/"]\n',
        )
        assert report.layer_of("src.api.view") == "presentation"

    def test_evidence_names_the_prefix(self, tmp_path):
        report = project(tmp_path, {"api/view.py": "x = 1\n"}, DECLARE_FOUR)
        assert "api/" in report.assignments["api.view"].evidence

    def test_without_a_declaration_everything_is_unknown(self, tmp_path):
        report = project(tmp_path, {"api/view.py": "x = 1\n"})
        assert report.layer_of("api.view") == UNKNOWN
        assert any("No layers declared" in n for n in report.notes)


class TestEdgeViolations:
    def test_direction_violation(self, tmp_path):
        report = project(
            tmp_path,
            {
                "domain/policy.py": "from infra.db import Repo\n",
                "infra/db.py": "class Repo: pass\n",
            },
            DECLARE_FOUR,
        )
        assert [v.code for v in report.with_code(LV_DIR)] == [LV_DIR]

    def test_skip_violation(self, tmp_path):
        report = project(
            tmp_path,
            {
                "api/view.py": "from infra.db import Repo\n",
                "infra/db.py": "class Repo: pass\n",
            },
            DECLARE_FOUR,
        )
        assert len(report.with_code(LV_SKIP)) == 1

    def test_allowed_edge_produces_nothing(self, tmp_path):
        report = project(
            tmp_path,
            {
                "services/svc.py": "from domain.model import Thing\n",
                "domain/model.py": "class Thing: pass\n",
            },
            DECLARE_FOUR,
        )
        assert report.violations == []

    def test_same_layer_edge_is_allowed(self, tmp_path):
        report = project(
            tmp_path,
            {
                "domain/a.py": "from domain.b import B\n",
                "domain/b.py": "class B: pass\n",
            },
            DECLARE_FOUR,
        )
        assert report.violations == []

    def test_unknown_layer_produces_no_violation(self, tmp_path):
        """Bilmediğimiz bir şey hakkında ihlal üretmek ilkeye aykırı."""
        report = project(
            tmp_path,
            {
                "misc/thing.py": "from infra.db import Repo\n",
                "infra/db.py": "class Repo: pass\n",
            },
            DECLARE_FOUR,
        )
        assert report.with_code(LV_DIR) == []
        assert report.with_code(LV_SKIP) == []

    def test_weak_import_is_still_a_violation_but_says_so(self, tmp_path):
        report = project(
            tmp_path,
            {
                "domain/policy.py": "def f():\n    from infra.db import Repo\n    return Repo\n",
                "infra/db.py": "class Repo: pass\n",
            },
            DECLARE_FOUR,
        )
        violations = report.with_code(LV_DIR)
        assert len(violations) == 1
        assert "weak import" in violations[0].detail

    def test_line_number_is_recorded(self, tmp_path):
        report = project(
            tmp_path,
            {
                "domain/policy.py": "\n\nfrom infra.db import Repo\n",
                "infra/db.py": "class Repo: pass\n",
            },
            DECLARE_FOUR,
        )
        assert report.with_code(LV_DIR)[0].lineno == 3


class TestCycles:
    def test_cycle_is_detected(self, tmp_path):
        report = project(
            tmp_path,
            {
                "domain/a.py": "import domain.b\n",
                "domain/b.py": "import domain.a\n",
            },
            DECLARE_FOUR,
        )
        assert len(report.with_code(LV_CYCLE)) == 1

    def test_cycle_lists_its_members(self, tmp_path):
        report = project(
            tmp_path,
            {
                "domain/a.py": "import domain.b\n",
                "domain/b.py": "import domain.a\n",
            },
            DECLARE_FOUR,
        )
        assert report.with_code(LV_CYCLE)[0].members == ("domain.a", "domain.b")

    def test_cycle_is_reported_even_without_layers(self, tmp_path):
        """Döngü yapısal bir gerçektir; katman bilgisine ihtiyaç duymaz."""
        report = project(
            tmp_path,
            {"a.py": "import b\n", "b.py": "import a\n"},
        )
        assert len(report.with_code(LV_CYCLE)) == 1

    def test_cycle_is_never_tentative(self, tmp_path):
        report = project(tmp_path, {"a.py": "import b\n", "b.py": "import a\n"})
        assert report.with_code(LV_CYCLE)[0].tentative is False


class TestInterfaceLeaks:
    def test_lower_layer_type_in_a_public_return(self, tmp_path):
        report = project(
            tmp_path,
            {
                "api/view.py": (
                    "from infra.db import Repo\n\n\n"
                    "class View:\n"
                    "    def repository(self) -> Repo:\n        return self._r\n"
                ),
                "infra/db.py": "class Repo: pass\n",
            },
            DECLARE_FOUR,
        )
        leaks = report.with_code(LV_LEAK)
        assert len(leaks) == 1
        assert "Repo" in leaks[0].target

    def test_parameter_annotation_also_leaks(self, tmp_path):
        report = project(
            tmp_path,
            {
                "api/view.py": (
                    "from infra.db import Repo\n\n\n"
                    "class View:\n    def use(self, r: Repo) -> None:\n        pass\n"
                ),
                "infra/db.py": "class Repo: pass\n",
            },
            DECLARE_FOUR,
        )
        assert len(report.with_code(LV_LEAK)) == 1

    def test_private_method_is_not_an_interface(self, tmp_path):
        report = project(
            tmp_path,
            {
                "api/view.py": (
                    "from infra.db import Repo\n\n\n"
                    "class View:\n    def _repo(self) -> Repo:\n        return None\n"
                ),
                "infra/db.py": "class Repo: pass\n",
            },
            DECLARE_FOUR,
        )
        assert report.with_code(LV_LEAK) == []

    def test_allowed_layer_type_is_not_a_leak(self, tmp_path):
        report = project(
            tmp_path,
            {
                "api/view.py": (
                    "from domain.model import Thing\n\n\n"
                    "class View:\n    def get(self) -> Thing:\n        return None\n"
                ),
                "domain/model.py": "class Thing: pass\n",
            },
            DECLARE_FOUR,
        )
        assert report.with_code(LV_LEAK) == []

    def test_generic_annotation_is_inspected(self, tmp_path):
        """`list[Repo]` de sızıntıdır."""
        report = project(
            tmp_path,
            {
                "api/view.py": (
                    "from infra.db import Repo\n\n\n"
                    "class View:\n    def all(self) -> list[Repo]:\n        return []\n"
                ),
                "infra/db.py": "class Repo: pass\n",
            },
            DECLARE_FOUR,
        )
        assert len(report.with_code(LV_LEAK)) == 1

    def test_unannotated_classes_are_counted_as_a_limitation(self, tmp_path):
        """Annotation'sız imza aynı sızıntıyı yapabilir ama görülemez."""
        report = project(
            tmp_path,
            {"api/view.py": "class View:\n    def get(self):\n        return None\n"},
            DECLARE_FOUR,
        )
        assert any("no annotated public signature" in n for n in report.notes)


@pytest.fixture(scope="module")
def fixture_report():
    config = load_config(search_from=LAYERED)
    modules, _ = parse_project(LAYERED, config.scan.include, config.scan.exclude)
    return analyse(modules, build_import_graph(modules), config.arch)


class TestLayeredFixture:
    """ARCH_SMELLS.md sözleşmesi: hepsi bulunmalı, fazlası bulunmamalı."""

    def test_total_violation_count(self, fixture_report):
        assert len(fixture_report.violations) == 6

    def test_one_direction_violation(self, fixture_report):
        violations = fixture_report.with_code(LV_DIR)
        assert len(violations) == 1
        assert violations[0].source == "src.domain.policies"
        assert violations[0].target == "src.infra.order_repository"

    def test_three_skip_violations(self, fixture_report):
        sources = {v.source for v in fixture_report.with_code(LV_SKIP)}
        assert sources == {"src.api.order_controller", "src.api.report_view"}
        assert len(fixture_report.with_code(LV_SKIP)) == 3

    def test_one_cycle(self, fixture_report):
        violations = fixture_report.with_code(LV_CYCLE)
        assert len(violations) == 1
        assert violations[0].members == ("src.shared.helpers", "src.shared.registry")

    def test_one_interface_leak(self, fixture_report):
        violations = fixture_report.with_code(LV_LEAK)
        assert len(violations) == 1
        assert "OrderController.repository" in violations[0].source

    def test_the_god_class_has_no_violation(self, fixture_report):
        """Fikstürün ana iddiası: kötü metrik ≠ mimari ihlal."""
        assert not any(
            v.source.startswith("src.services.order_service") for v in fixture_report.violations
        )

    def test_declared_layers_are_never_tentative(self, fixture_report):
        assert all(v.tentative is False for v in fixture_report.violations)
        assert fixture_report.blocking == fixture_report.violations

    def test_shared_modules_stay_unknown(self, fixture_report):
        assert fixture_report.layer_of("src.shared.helpers") == UNKNOWN

    def test_limitations_are_reported(self, fixture_report):
        assert any("unknown" in n for n in fixture_report.notes)

    def test_serialisation(self, fixture_report):
        payload = fixture_report.to_dict()
        assert len(payload["violations"]) == 6
        assert payload["assignments"]["src.api.report_view"]["layer"] == "presentation"
