"""Hedef seçimi testleri."""

from pathlib import Path

import pytest

from rlens.advise.selector import (
    available_targets,
    collect_targets,
    rank_targets,
    score_violations,
    select_targets,
    target_for,
)
from rlens.analysis.model import ClassReport, ModuleReport, ProjectReport
from rlens.analysis.scanner import scan_project
from rlens.config import load_config

MESSY_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "messy_project"


@pytest.fixture(scope="module")
def messy():
    config = load_config(search_from=MESSY_PROJECT)
    return scan_project(MESSY_PROJECT, config), config


def make_report(*classes: ClassReport) -> ProjectReport:
    return ProjectReport(
        root="/tmp",
        generated_at="2026-08-29T00:00:00+00:00",
        rlens_version="0.1.0",
        modules=[ModuleReport(path="m.py", module="m", classes=list(classes))],
    )


class TestScoring:
    def test_empty_is_zero(self):
        assert score_violations({}) == 0

    def test_warn_weighs_one(self):
        assert score_violations({"lcom4": "warn"}) == 1

    def test_critical_weighs_three(self):
        assert score_violations({"lcom4": "critical"}) == 3

    def test_one_critical_outranks_two_warnings(self):
        """Bir metriği ciddi aşan sınıf, iki metriği kıl payı aşandan acildir."""
        assert score_violations({"lcom4": "critical"}) > score_violations(
            {"dcc": "warn", "nom": "warn"}
        )


class TestCollectTargets:
    def test_clean_classes_are_not_targets(self, config=None):
        cfg = load_config(search_from=Path("/tmp"))
        clean = ClassReport(name="Ok", module="m", lineno=1, nom=2, wmc=3, lcom4=1, dcc=1)
        assert collect_targets(make_report(clean), cfg) == []

    def test_violating_class_is_a_target(self):
        cfg = load_config(search_from=Path("/tmp"))
        bad = ClassReport(name="Bad", module="m", lineno=1, nom=2, wmc=3, lcom4=5, dcc=1)
        targets = collect_targets(make_report(bad), cfg)
        assert len(targets) == 1
        assert targets[0].kind == "class"
        assert targets[0].threshold_flags["lcom4"] == "critical"

    def test_module_functions_can_be_targets(self, messy):
        report, cfg = messy
        names = {t.name for t in collect_targets(report, cfg) if t.kind == "function"}
        assert "classify_order" in names

    def test_methods_are_not_separate_targets(self, messy):
        """Metot sorunluysa bağlamı sınıfıdır; öneri sınıf üzerinden verilir."""
        report, cfg = messy
        assert all(t.kind in ("class", "function") for t in collect_targets(report, cfg))


class TestNoRawThresholds:
    """Goodhart azaltması: model eşiğin sayısını bilmemeli."""

    def test_target_carries_levels_not_numbers(self, messy):
        report, cfg = messy
        target = select_targets(report, cfg, top_n=1)[0]
        assert set(target.threshold_flags.values()) <= {"warn", "critical"}

    def test_metrics_are_measured_values_only(self, messy):
        report, cfg = messy
        target = next(t for t in select_targets(report, cfg, 5) if t.name == "OrderManager")
        assert target.metrics["LCOM4"] == 4
        assert "threshold" not in str(target.metrics).lower()


class TestRanking:
    def test_worst_first(self, messy):
        report, cfg = messy
        assert select_targets(report, cfg, top_n=1)[0].name == "OrderManager"

    def test_ranking_is_deterministic(self, messy):
        report, cfg = messy
        first = [t.qualified_name for t in select_targets(report, cfg, 5)]
        second = [t.qualified_name for t in select_targets(report, cfg, 5)]
        assert first == second

    def test_equal_scores_break_ties_by_complexity(self):
        cfg = load_config(search_from=Path("/tmp"))
        light = ClassReport(name="Light", module="m", lineno=1, wmc=5, lcom4=2, dcc=1)
        heavy = ClassReport(name="Heavy", module="m", lineno=2, wmc=40, lcom4=2, dcc=1)
        ranked = rank_targets(collect_targets(make_report(light, heavy), cfg))
        assert [t.name for t in ranked] == ["Heavy", "Light"]

    def test_severity_property(self, messy):
        report, cfg = messy
        target = next(t for t in select_targets(report, cfg, 5) if t.name == "OrderManager")
        assert target.severity == "critical"


class TestLimit:
    def test_top_n_from_config(self, messy):
        report, cfg = messy
        assert len(select_targets(report, cfg)) == cfg.advise.top_n

    def test_explicit_limit_overrides_config(self, messy):
        report, cfg = messy
        assert len(select_targets(report, cfg, top_n=1)) == 1

    def test_limit_larger_than_available(self, messy):
        report, cfg = messy
        assert len(select_targets(report, cfg, top_n=999)) == len(collect_targets(report, cfg))


class TestExplicitTargets:
    """Deney hedefleri seçiciye değil protokole aittir."""

    def test_a_named_class_is_found(self, messy):
        report, config = messy
        target = target_for(report, config, "god:OrderManager")
        assert target is not None
        assert target.kind == "class"
        assert target.metrics["LCOM4"] == 4

    def test_an_entity_without_violations_can_be_a_target(self, messy):
        """Eşik aşmayan hedef de sabitlenebilir; boş bayrak bir bilgidir."""
        report, config = messy
        target = target_for(report, config, "services:Invoice")
        assert target is not None
        assert target.threshold_flags == {}
        assert target.score == 0

    def test_a_module_level_function_is_found(self, messy):
        report, config = messy
        target = target_for(report, config, "utils:classify_order")
        assert target is not None and target.kind == "function"

    def test_an_unknown_name_returns_none(self, messy):
        report, config = messy
        assert target_for(report, config, "nope:Ghost") is None

    def test_available_targets_lists_everything(self, messy):
        report, _ = messy
        names = available_targets(report)
        assert "god:OrderManager" in names
        assert "utils:classify_order" in names
        assert names == sorted(names)

    def test_layer_and_smells_travel_with_the_target(self):
        from pathlib import Path

        from rlens.analysis.scanner import scan_project

        layered = Path(__file__).resolve().parent.parent / "examples" / "layered_project"
        config = load_config(search_from=layered)
        report = scan_project(layered, config)
        target = target_for(report, config, "src.domain.entities:Customer")
        assert target.layer == "domain"
        assert target.smell_labels == ["data_class"]
