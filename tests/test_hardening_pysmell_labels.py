"""v2.2 §2: PySmell etiketlerinin neyi kodladığı (`experiments/hardening/pysmell_labels.py`).

Ön kayıt: `experiments/hardening/pysmell-labels.md`. Beklenen değerler elle
hesaplandı.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from pysmell_labels import (  # noqa: E402
    agreement,
    best_single,
    best_two,
    parse_rows,
    reading,
)

CSV = """subject,tag,file,lineno,A,B,experience-based,statistics-based,manual analysis
p,v1,f.py,1,1,5,0,0,0
p,v1,f.py,2,2,,0,1,0
p,v1,f.py,3,5,1,1,1,1
p,v1,f.py,4,7,9,1,0,1
"""


class TestParse:
    def test_metrics_labels_and_missing_values(self):
        metrics, rows = parse_rows(CSV)
        assert metrics == ["A", "B"]
        assert rows[1]["B"] is None
        assert [r["manual"] for r in rows] == [0, 0, 1, 1]
        assert [r["experience"] for r in rows] == [0, 0, 1, 1]


class TestSingle:
    def test_perfect_threshold(self):
        # A: 1, 2 negatif; 5, 7 pozitif → A >= 3..5 hatasız
        _, rows = parse_rows(CSV)
        errors, metric, direction, threshold = best_single(rows, ["A"])
        assert (errors, metric, direction) == (0, "A", ">=")
        assert threshold == 5

    def test_missing_value_counts_as_not_meeting(self):
        # B: 5(-), None(-), 1(+), 9(+). En iyi: B >= 9 → 1 hata (satır 3).
        # B <= 1 → satır 3 doğru, satır 4 hatalı, None karşılamaz → 1 hata.
        _, rows = parse_rows(CSV)
        errors, *_ = best_single(rows, ["B"])
        assert errors == 1

    def test_both_directions_are_tried(self):
        rows = [
            {"manual": 1, "A": 1},
            {"manual": 1, "A": 2},
            {"manual": 0, "A": 8},
            {"manual": 0, "A": 9},
        ]
        errors, _, direction, threshold = best_single(rows, ["A"])
        assert (errors, direction, threshold) == (0, "<=", 2)


class TestTwo:
    def test_and_rule_beats_any_single_threshold(self):
        # Pozitif yalnızca A >= 5 ve B >= 5 iken.
        rows = [
            {"manual": 1, "A": 6, "B": 6},
            {"manual": 1, "A": 7, "B": 8},
            {"manual": 0, "A": 6, "B": 1},
            {"manual": 0, "A": 1, "B": 7},
            {"manual": 0, "A": 2, "B": 2},
        ]
        single, *_ = best_single(rows, ["A", "B"])
        assert single == 1
        errors, rule = best_two(rows, ["A", "B"])
        assert errors == 0
        assert rule["combine"] == "and"


class TestReading:
    def test_readings(self):
        assert reading(n=300, positives=9, single=0, two=None) == "yetersiz pozitif"
        # sınır max(1, ceil(0.02 * 300)) = 6
        assert reading(n=300, positives=20, single=6, two=None) == "tek eşiği kodluyor"
        assert reading(n=300, positives=20, single=7, two=6) == "kuralı kodluyor"
        assert reading(n=300, positives=20, single=7, two=7) == "bağımsız yargı"
        assert reading(n=300, positives=20, single=7, two=None) == "bağımsız yargı"
        # küçük N: sınır en az 1
        assert reading(n=20, positives=10, single=1, two=None) == "tek eşiği kodluyor"

    def test_agreement(self):
        _, rows = parse_rows(CSV)
        assert agreement(rows, "experience") == 1.0
        assert agreement(rows, "statistics") == 0.5


class TestDetectorRules:
    """`detector.py`'nin genel eşikleri (sonradan eklenen analiz)."""

    def test_single_metric_rule(self):
        from pysmell_labels import detector_rule

        # LongMessageChain: experience LMC >= 5, statistics LMC >= 4
        assert detector_rule("LongMessageChain", {"LMC": 4}, 0) is False
        assert detector_rule("LongMessageChain", {"LMC": 4}, 1) is True

    def test_lambda_rule_needs_noc_and_one_of_the_others(self):
        from pysmell_labels import detector_rule

        # statistics: NOC >= 82 ve (PAR >= 3 veya NOO >= 13)
        assert detector_rule("LongLambdaFunction", {"NOC": 82, "PAR": 1, "NOO": 13}, 1) is True
        assert detector_rule("LongLambdaFunction", {"NOC": 81, "PAR": 9, "NOO": 99}, 1) is False

    def test_missing_nested_container_value_does_not_fire(self):
        from pysmell_labels import detector_rule

        row = {"LEC": 2, "DNC": 9, "NCT": None}
        assert detector_rule("MultiplyNestedContainer", row, 1) is False
