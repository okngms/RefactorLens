"""İki rapor arasındaki metrik farkı testleri."""

import pytest

from rlens.analysis.model import SCHEMA_VERSION
from rlens.verify.diff import (
    ADDED,
    IMPROVED,
    MIXED,
    REGRESSED,
    REMOVED,
    UNCHANGED,
    MetricDelta,
    check_compatibility,
    diff_reports,
)


def report(*classes, functions=(), schema=SCHEMA_VERSION, at="2026-01-01T00:00:00+00:00"):
    """Elle kurulmuş küçük bir tarama raporu."""
    return {
        "schema_version": schema,
        "generated_at": at,
        "modules": [
            {
                "module": "m",
                "path": "m.py",
                "classes": list(classes),
                "functions": list(functions),
            }
        ],
    }


def cls(name="C", **metrics):
    base = {"name": name, "nom": 1, "wmc": 1, "lcom4": 1, "dam": 0.5, "dcc": 1, "cam": 0.5}
    base.update(metrics)
    return base


def func(name="f", **metrics):
    base = {"name": name, "cyclomatic_complexity": 1, "loc": 3, "param_count": 1, "max_nesting": 0}
    base.update(metrics)
    return base


class TestMetricDelta:
    def test_change_and_direction(self):
        delta = MetricDelta("LCOM4", before=4, after=1)
        assert delta.change == -3
        assert delta.direction == "down"

    def test_no_change_is_same(self):
        assert MetricDelta("NOM", 5, 5).direction == "same"

    def test_lower_is_better_for_lcom4(self):
        assert MetricDelta("LCOM4", 4, 1).improved is True
        assert MetricDelta("LCOM4", 1, 4).improved is False

    def test_higher_is_better_for_dam(self):
        """Yön tek başına yetmez; DAM'de yükselmek iyileşmedir."""
        assert MetricDelta("DAM", 0.2, 0.8).improved is True
        assert MetricDelta("DAM", 0.8, 0.2).improved is False

    def test_higher_is_better_for_cam(self):
        assert MetricDelta("CAM", 0.4, 0.9).improved is True

    def test_unchanged_has_no_verdict(self):
        assert MetricDelta("NOM", 3, 3).improved is None

    def test_none_before_is_not_comparable(self):
        """`None` hesaplanamadı demektir; sıfır sayıp çıkarmak uydurma olur."""
        delta = MetricDelta("CAM", None, 0.8)
        assert delta.comparable is False
        assert delta.change is None
        assert delta.direction is None
        assert delta.improved is None

    def test_none_after_is_not_comparable(self):
        assert MetricDelta("CAM", 0.8, None).comparable is False

    def test_both_none(self):
        assert MetricDelta("CAM", None, None).comparable is False

    def test_serialisation(self):
        payload = MetricDelta("LCOM4", 4, 1).to_dict()
        assert payload["change"] == -3
        assert payload["improved"] is True


class TestCompatibility:
    def test_same_schema_is_compatible(self):
        assert check_compatibility(report(), report()) is None

    def test_different_schema_is_reported(self):
        """Sessizce devam etmek, tutarlı görünen ama yanlış delta üretirdi."""
        reason = check_compatibility(report(schema=1), report(schema=2))
        assert reason is not None
        assert "schema version" in reason

    def test_diff_marks_incomparable(self):
        delta = diff_reports(report(cls(), schema=1), report(cls(), schema=2))
        assert delta.comparable is False
        assert delta.incompatibility

    def test_entities_are_still_listed_when_incomparable(self):
        """Kullanıcı ne olduğunu görebilmeli, ama güvenmemesi gerektiğini bilmeli."""
        delta = diff_reports(report(cls(), schema=1), report(cls(), schema=2))
        assert delta.entities


class TestDiffReports:
    def test_unchanged_class(self):
        delta = diff_reports(report(cls()), report(cls()))
        entity = delta.by_name("m:C")
        assert entity.status == UNCHANGED
        assert entity.summarise() == UNCHANGED

    def test_improved_class(self):
        delta = diff_reports(report(cls(lcom4=4)), report(cls(lcom4=1)))
        assert delta.by_name("m:C").summarise() == IMPROVED

    def test_regressed_class(self):
        delta = diff_reports(report(cls(dcc=2)), report(cls(dcc=9)))
        assert delta.by_name("m:C").summarise() == REGRESSED

    def test_mixed_is_not_hidden(self):
        """'Bir metriği düzeltirken diğerini bozdu' bulgusu gizlenmez."""
        delta = diff_reports(report(cls(lcom4=4, dcc=2)), report(cls(lcom4=1, dcc=9)))
        assert delta.by_name("m:C").summarise() == MIXED

    def test_added_class_is_detected(self):
        """'Sınıfı böl' önerisi yeni sınıflar doğurur."""
        delta = diff_reports(report(cls("A")), report(cls("A"), cls("B")))
        assert delta.by_name("m:B").status == ADDED
        assert [e.name for e in delta.with_status(ADDED)] == ["B"]

    def test_removed_class_is_detected(self):
        delta = diff_reports(report(cls("A"), cls("B")), report(cls("A")))
        assert delta.by_name("m:B").status == REMOVED

    def test_added_class_has_no_false_deltas(self):
        delta = diff_reports(report(), report(cls("New")))
        entity = delta.by_name("m:New")
        assert all(not d.comparable for d in entity.metrics.values())

    def test_functions_are_compared_too(self):
        before = report(functions=[func(cyclomatic_complexity=15)])
        after = report(functions=[func(cyclomatic_complexity=5)])
        entity = diff_reports(before, after).by_name("m:f")
        assert entity.kind == "function"
        assert entity.summarise() == IMPROVED

    def test_class_and_function_do_not_collide(self):
        before = report(cls("thing"), functions=[func("thing")])
        after = report(cls("thing"), functions=[func("thing")])
        kinds = {e.kind for e in diff_reports(before, after).entities}
        assert kinds == {"class", "function"}

    def test_changed_metrics_lists_only_movement(self):
        delta = diff_reports(report(cls(lcom4=4)), report(cls(lcom4=1)))
        changed = delta.by_name("m:C").changed_metrics
        assert set(changed) == {"LCOM4"}

    def test_changed_property_skips_untouched_entities(self):
        before = report(cls("A", lcom4=4), cls("B"))
        after = report(cls("A", lcom4=1), cls("B"))
        assert [e.name for e in diff_reports(before, after).changed] == ["A"]

    def test_ordering_is_deterministic(self):
        before = report(cls("Z"), cls("A"), cls("M"))
        after = report(cls("Z"), cls("A"), cls("M"))
        names = [e.name for e in diff_reports(before, after).entities]
        assert names == sorted(names)

    def test_timestamps_are_carried(self):
        before = report(at="2026-01-01T00:00:00+00:00")
        after = report(at="2026-02-01T00:00:00+00:00")
        delta = diff_reports(before, after)
        assert delta.before_generated_at.startswith("2026-01")
        assert delta.after_generated_at.startswith("2026-02")

    def test_cam_null_does_not_produce_a_verdict(self):
        delta = diff_reports(report(cls(cam=None)), report(cls(cam=0.9)))
        assert delta.by_name("m:C").metrics["CAM"].improved is None

    def test_serialisation_round_trip(self):
        payload = diff_reports(report(cls(lcom4=4)), report(cls(lcom4=1))).to_dict()
        assert payload["entities"][0]["verdict"] == IMPROVED
        assert payload["comparable"] is True


class TestEmptyReports:
    def test_two_empty_reports(self):
        delta = diff_reports(report(), report())
        assert delta.entities == []
        assert delta.comparable is True

    def test_missing_modules_key(self):
        delta = diff_reports({"schema_version": SCHEMA_VERSION}, {"schema_version": SCHEMA_VERSION})
        assert delta.entities == []


@pytest.mark.parametrize(
    ("metric", "before", "after", "expected"),
    [
        ("NOM", 25, 12, True),
        ("WMC", 49, 20, True),
        ("DCC", 4, 8, False),
        ("DAM", 0.0, 1.0, True),
        ("CAM", 0.9, 0.3, False),
    ],
)
def test_polarity_table(metric, before, after, expected):
    assert MetricDelta(metric, before, after).improved is expected
