"""utils.py davranış testleri."""

import pytest
from utils import build_shipping_label, classify_order, deep_transform


class TestDeepTransform:
    def test_extracts_numeric_pairs_sorted_by_key(self):
        data = [[{"b": 5, "a": 2}]]
        assert deep_transform(data) == [("a", 2), ("b", 5)]

    def test_non_positive_values_become_zero(self):
        assert deep_transform([[{"a": -3}]]) == [("a", 0)]

    def test_non_list_groups_are_skipped(self):
        assert deep_transform(["skip", [{"a": 1}]]) == [("a", 1)]

    def test_non_numeric_values_are_skipped(self):
        assert deep_transform([[{"a": "text", "b": 1}]]) == [("b", 1)]

    def test_empty_input(self):
        assert deep_transform([]) == []


def test_build_shipping_label_format():
    label = build_shipping_label("Ada", "Main 1", "Gebze", "41400", "TR", 2.0, True)
    assert label == "Ada|Main 1|Gebze 41400|TR|2.0kg|EXPRESS"


def test_build_shipping_label_standard_speed():
    label = build_shipping_label("Ada", "Main 1", "Gebze", "41400", "TR", 2.0, False)
    assert label.endswith("STANDARD")


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"total": 0}, "invalid"),
        ({"item_count": 0}, "invalid"),
        ({"tier": "premium", "total": 2000}, "vip-large"),
        ({"tier": "premium"}, "vip"),
        ({"is_gift": True, "country": "DE"}, "gift-international"),
        ({"is_gift": True}, "gift-domestic"),
        ({"coupon": "X", "total": 600}, "discounted-large"),
        ({"coupon": "X"}, "discounted"),
        ({"weight": 50}, "freight"),
        ({"total": 2000}, "large"),
        ({"item_count": 30}, "bulk"),
        ({}, "standard"),
    ],
)
def test_classify_order_branches(kwargs, expected):
    defaults = {
        "total": 100.0,
        "item_count": 2,
        "tier": "standard",
        "is_gift": False,
        "country": "TR",
        "coupon": None,
        "weight": 1.0,
    }
    defaults.update(kwargs)
    assert classify_order(**defaults) == expected
