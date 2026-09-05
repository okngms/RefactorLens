"""Goodhart koruması testleri.

Referans vaka FINDINGS-1'den: dört metrik birden iyileşti, sınıfın tüm public
arayüzü silindi, 42 davranış testi kırıldı.
"""

import pytest

from rlens.verify import goodhart
from rlens.verify.diff import diff_reports


def report(*classes, schema=2):
    return {
        "schema_version": schema,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "modules": [{"module": "m", "path": "m.py", "classes": list(classes), "functions": []}],
    }


def cls(name="C", interface=None, **metrics):
    base = {"name": name, "nom": 5, "wmc": 10, "lcom4": 2, "dam": 0.5, "dcc": 3, "cam": None}
    base.update(metrics)
    if interface is not None:
        base["public_interface"] = {
            "methods": list(interface),
            "attributes": [],
            "accessors": [],
            "size": len(interface),
        }
    return base


def analyse(before, after):
    delta = diff_reports(before, after)
    return goodhart.detect(before, after, delta.entities)


class TestTheFindingsOneCase:
    """Metrikler mükemmelleşirken program ölür."""

    @pytest.fixture
    def result(self):
        before = report(
            cls(nom=25, wmc=49, lcom4=4, dcc=8, interface=["place", "get", "log", "notify"])
        )
        after = report(cls(nom=0, wmc=0, lcom4=0, dcc=4, interface=[]))
        return analyse(before, after)

    def test_it_is_flagged(self, result):
        assert result.any_suspicious is True

    def test_the_reason_names_the_lost_members(self, result):
        reason = result.suspicious[0].reason
        assert "4 public member(s) disappeared" in reason
        assert "place" in reason

    def test_the_metric_verdict_is_still_improved(self):
        """Şüphe kararı ezmez; iki bilgi yan yana durur."""
        before = report(cls(nom=25, wmc=49, lcom4=4, dcc=8, interface=["a", "b"]))
        after = report(cls(nom=0, wmc=0, lcom4=0, dcc=4, interface=[]))
        assert diff_reports(before, after).by_name("m:C").summarise() == "improved"


class TestConditions:
    """İki koşul birden aranır."""

    def test_interface_shrinking_alone_is_not_suspicious(self):
        """Ölü kod silmek meşrudur."""
        before = report(cls(interface=["a", "b"]))
        after = report(cls(interface=["a"]))
        assert analyse(before, after).any_suspicious is False

    def test_metric_improvement_alone_is_not_suspicious(self):
        before = report(cls(lcom4=4, interface=["a", "b"]))
        after = report(cls(lcom4=1, interface=["a", "b"]))
        assert analyse(before, after).any_suspicious is False

    def test_both_together_are(self):
        before = report(cls(lcom4=4, interface=["a", "b"]))
        after = report(cls(lcom4=1, interface=["a"]))
        assert analyse(before, after).any_suspicious is True

    def test_a_mixed_verdict_also_counts(self):
        """Bir metriği düzeltip diğerini bozarken arayüz silmek de şüphelidir."""
        before = report(cls(lcom4=4, dcc=2, interface=["a", "b"]))
        after = report(cls(lcom4=1, dcc=9, interface=["a"]))
        assert analyse(before, after).any_suspicious is True

    def test_growing_the_interface_is_never_suspicious(self):
        before = report(cls(lcom4=4, interface=["a"]))
        after = report(cls(lcom4=1, interface=["a", "b"]))
        assert analyse(before, after).any_suspicious is False


class TestMissingData:
    def test_v1_reports_have_no_interface_field(self):
        """Yokluğundan 'arayüz küçülmedi' sonucu çıkarılmaz."""
        before = report(cls(lcom4=4))
        after = report(cls(lcom4=1))
        result = analyse(before, after)
        assert result.checks == []
        assert result.unavailable == ["m:C"]

    def test_one_sided_data_is_also_unavailable(self):
        before = report(cls(lcom4=4, interface=["a"]))
        after = report(cls(lcom4=1))
        assert analyse(before, after).unavailable == ["m:C"]

    def test_added_class_is_not_suspicious(self):
        before = report()
        after = report(cls(name="New", interface=["a"]))
        assert analyse(before, after).any_suspicious is False


class TestSerialisation:
    def test_only_suspicious_checks_are_written(self):
        before = report(
            cls(name="A", lcom4=4, interface=["a", "b"]),
            cls(name="B", lcom4=4, interface=["x"]),
        )
        after = report(
            cls(name="A", lcom4=1, interface=["a"]),
            cls(name="B", lcom4=1, interface=["x"]),
        )
        payload = analyse(before, after).to_dict()
        assert payload["suspicious_count"] == 1
        assert len(payload["checks"]) == 1

    def test_removed_members_are_listed(self):
        before = report(cls(lcom4=4, interface=["a", "b"]))
        after = report(cls(lcom4=1, interface=["a"]))
        payload = analyse(before, after).to_dict()
        assert payload["checks"][0]["interface"]["removed"] == ["b"]

    def test_long_lists_are_truncated_in_the_reason(self):
        members = [f"m{i}" for i in range(9)]
        before = report(cls(lcom4=4, interface=members))
        after = report(cls(lcom4=1, interface=[]))
        assert "and 4 more" in analyse(before, after).suspicious[0].reason
