"""Tarama akışı testleri."""

import json
from pathlib import Path

import pytest

from rlens import __version__
from rlens.analysis.model import SCHEMA_VERSION
from rlens.analysis.scanner import count_classes, count_functions, scan_project
from rlens.config import load_config

MESSY_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "messy_project"


@pytest.fixture
def default_config(tmp_path):
    return load_config(search_from=tmp_path)


@pytest.fixture(scope="module")
def messy_report():
    config = load_config(search_from=MESSY_PROJECT)
    return scan_project(MESSY_PROJECT, config)


class TestScanProject:
    def test_finds_every_module(self, messy_report):
        assert {m.module for m in messy_report.modules} == {
            "models",
            "services",
            "god",
            "reporting",
            "utils",
        }

    def test_tests_directory_is_excluded_by_config(self, messy_report):
        """messy_project/rlens.yaml `tests/` dizinini dışlar."""
        assert all("tests" not in m.path for m in messy_report.modules)

    def test_counts(self, messy_report):
        assert count_classes(messy_report) == 10
        assert count_functions(messy_report) == 55

    def test_version_fields_are_recorded(self, messy_report):
        assert messy_report.rlens_version == __version__
        assert messy_report.schema_version == SCHEMA_VERSION

    def test_generated_at_is_iso_utc(self, messy_report):
        assert messy_report.generated_at.endswith("+00:00")

    def test_root_is_absolute(self, messy_report):
        assert Path(messy_report.root).is_absolute()

    def test_no_files_skipped_in_fixture(self, messy_report):
        assert messy_report.skipped_files == []


class TestMetricsAreWiredThrough:
    """scanner'ın metrikleri gerçekten çağırdığının kanıtı."""

    def test_god_class_metrics(self, messy_report):
        god = next(c for c in messy_report.iter_classes() if c.name == "OrderManager")
        assert (god.nom, god.wmc, god.lcom4, god.dcc) == (25, 49, 4, 8)
        assert god.dam == 1.0
        assert god.cam is None
        assert god.cam_skipped_reason == "no_annotated_parameters"

    def test_dcc_requires_the_second_pass(self, messy_report):
        """DCC>0 ancak proje geneli sınıf sözlüğü kurulduysa mümkündür."""
        line = next(c for c in messy_report.iter_classes() if c.name == "OrderLine")
        assert line.dcc == 1

    def test_module_level_functions_are_measured(self, messy_report):
        utils = next(m for m in messy_report.modules if m.module == "utils")
        classify = next(f for f in utils.functions if f.name == "classify_order")
        assert classify.cyclomatic_complexity == 15
        assert classify.param_count == 7

    def test_methods_are_attached_to_classes(self, messy_report):
        customer = next(c for c in messy_report.iter_classes() if c.name == "Customer")
        assert {m.name for m in customer.methods} == {
            "rename",
            "promote",
            "is_premium",
            "add_note",
            "notes",
            "label",
        }


class TestCamThresholdIsHonoured:
    def test_lower_threshold_enables_cam(self, tmp_path):
        """Eşik düşürülünce kısmi annotation'lı sınıf için CAM hesaplanır."""
        (tmp_path / "rlens.yaml").write_text(
            "scan:\n  include: ['.']\n  exclude: ['tests/']\n"
            "metrics:\n  cam_min_annotation_coverage: 0.2\n",
            encoding="utf-8",
        )
        config = load_config(search_from=tmp_path)
        report = scan_project(MESSY_PROJECT, config)
        builder = next(c for c in report.iter_classes() if c.name == "ReportBuilder")
        assert builder.cam is not None


class TestEdgeCases:
    def test_empty_project(self, tmp_path, default_config):
        report = scan_project(tmp_path, default_config)
        assert report.modules == []
        assert count_classes(report) == 0

    def test_broken_file_is_reported_not_raised(self, tmp_path):
        (tmp_path / "good.py").write_text("class A:\n    pass\n", encoding="utf-8")
        (tmp_path / "bad.py").write_text("class B(\n", encoding="utf-8")
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        config = load_config(search_from=tmp_path)
        report = scan_project(tmp_path, config)
        assert count_classes(report) == 1
        assert len(report.skipped_files) == 1
        assert report.skipped_files[0]["path"] == "bad.py"

    def test_report_is_json_serialisable(self, messy_report):
        """Rapor doğrudan JSON'a yazılabilmeli; ara dönüşüm gerekmemeli."""
        payload = json.dumps(messy_report.to_dict())
        assert '"schema_version"' in payload

    def test_scan_is_deterministic(self, tmp_path):
        """Aynı proje iki kez taranınca modül sırası değişmemeli."""
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        for name in ("z.py", "a.py", "m.py"):
            (tmp_path / name).write_text("x = 1\n", encoding="utf-8")
        config = load_config(search_from=tmp_path)
        first = [m.module for m in scan_project(tmp_path, config).modules]
        second = [m.module for m in scan_project(tmp_path, config).modules]
        assert first == second == sorted(first)


LAYERED = Path(__file__).resolve().parent.parent / "examples" / "layered_project"


@pytest.fixture(scope="module")
def layered_report():
    return scan_project(LAYERED, load_config(search_from=LAYERED))


class TestArchitectureIntegration:
    def test_schema_version_is_two(self, layered_report):
        """v2 raporları v1 ile karşılaştırılamaz; eşikler artık katmana bağlı."""
        assert layered_report.schema_version == 2

    def test_classes_carry_their_layer(self, layered_report):
        service = next(c for c in layered_report.iter_classes() if c.name == "OrderService")
        assert service.layer == "application"
        assert service.layer_source == "declared"
        assert service.layer_confidence == 1.0

    def test_modules_carry_coupling_metrics(self, layered_report):
        entities = next(m for m in layered_report.modules if m.module.endswith("entities"))
        assert (entities.ca, entities.ce, entities.instability) == (2, 0, 0.0)

    def test_violations_are_included(self, layered_report):
        assert len(layered_report.violations) == 6
        assert {v["code"] for v in layered_report.violations} == {
            "LV-DIR",
            "LV-SKIP",
            "LV-CYCLE",
            "LV-LEAK",
        }

    def test_public_interface_is_recorded(self, layered_report):
        """Aşama 4'teki Goodhart koruması bu kümeyi karşılaştıracak."""
        customer = next(c for c in layered_report.iter_classes() if c.name == "Customer")
        assert "name" in customer.public_interface["methods"]
        assert customer.public_interface["size"] == 5

    def test_smells_are_attached(self, layered_report):
        labels = sorted(s["label"] for s in layered_report.iter_smells())
        assert labels == [
            "data_class",
            "feature_envy_candidate",
            "feature_envy_candidate",
            "god_class",
        ]

    def test_layer_misfit_needs_both_conditions(self, layered_report):
        """Fikstürde ihlal var ama kuplaj eşik altında."""
        assert not any(s["label"] == "layer_misfit" for s in layered_report.iter_smells())

    def test_arch_notes_are_carried(self, layered_report):
        assert any("stay unknown" in note for note in layered_report.arch_notes)


class TestNoArch:
    def test_nothing_architectural_is_computed(self):
        report = scan_project(LAYERED, load_config(search_from=LAYERED), no_arch=True)
        assert report.arch_enabled is False
        assert report.violations == []
        assert all(c.layer is None for c in report.iter_classes())
        assert all(m.ca is None for m in report.modules)

    def test_metrics_are_unchanged(self):
        config = load_config(search_from=LAYERED)
        with_arch = scan_project(LAYERED, config)
        without = scan_project(LAYERED, config, no_arch=True)
        assert [c.wmc for c in with_arch.iter_classes()] == [c.wmc for c in without.iter_classes()]

    def test_disabled_in_config_has_the_same_effect(self, tmp_path):
        (tmp_path / "rlens.yaml").write_text(
            "scan:\n  include: ['.']\narch:\n  enabled: false\n", encoding="utf-8"
        )
        (tmp_path / "m.py").write_text("class C:\n    pass\n", encoding="utf-8")
        report = scan_project(tmp_path, load_config(search_from=tmp_path))
        assert report.arch_enabled is False
