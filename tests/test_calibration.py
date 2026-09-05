"""Kalibrasyon testleri: Brier skoru ve ECE."""

import pytest

from rlens.verify.calibration import (
    CalibrationPoint,
    calibrate,
    collect_points,
    make_bins,
)


class TestPoint:
    def test_confident_and_correct_has_small_error(self):
        assert CalibrationPoint(0.9, True).error == pytest.approx(0.01)

    def test_confident_and_wrong_has_large_error(self):
        assert CalibrationPoint(0.9, False).error == pytest.approx(0.81)

    def test_uncertain_prediction_is_middling(self):
        assert CalibrationPoint(0.5, True).error == 0.25


class TestBrier:
    def test_perfect_confidence_and_correct(self):
        assert calibrate([CalibrationPoint(1.0, True)]).brier == 0.0

    def test_perfectly_wrong(self):
        assert calibrate([CalibrationPoint(1.0, False)]).brier == 1.0

    def test_coin_flip(self):
        report = calibrate([CalibrationPoint(0.5, i % 2 == 0) for i in range(10)])
        assert report.brier == 0.25

    def test_no_points_gives_none_not_zero(self):
        """Sıfır 'mükemmel kalibre' demek olurdu."""
        assert calibrate([]).brier is None


class TestEce:
    def test_calibrated_model_scores_zero(self):
        """0.8 diyen ve %80 haklı çıkan model."""
        points = [CalibrationPoint(0.8, i < 8) for i in range(10)]
        assert calibrate(points).ece == 0.0

    def test_overconfident_model(self):
        points = [CalibrationPoint(0.9, i % 2 == 0) for i in range(10)]
        report = calibrate(points)
        assert report.ece == pytest.approx(0.4)
        assert report.overconfidence == pytest.approx(0.4)

    def test_underconfident_model_has_negative_overconfidence(self):
        points = [CalibrationPoint(0.3, True) for _ in range(10)]
        assert calibrate(points).overconfidence == pytest.approx(-0.7)

    def test_no_points(self):
        assert calibrate([]).ece is None


class TestBins:
    def test_default_bin_count(self):
        assert len(make_bins([])) == 5

    def test_points_land_in_the_upper_bin_at_a_boundary(self):
        """0.2 iki kovaya birden girmemeli."""
        bins = make_bins([CalibrationPoint(0.2, True)])
        assert bins[0].count == 1
        assert bins[1].count == 0

    def test_zero_lands_in_the_first_bin(self):
        assert make_bins([CalibrationPoint(0.0, False)])[0].count == 1

    def test_one_lands_in_the_last_bin(self):
        assert make_bins([CalibrationPoint(1.0, True)])[-1].count == 1

    def test_empty_bins_report_none(self):
        bins = make_bins([CalibrationPoint(0.9, True)])
        assert bins[0].accuracy is None
        assert bins[-1].accuracy == 1.0

    def test_gap_is_confidence_minus_accuracy(self):
        bins = make_bins([CalibrationPoint(0.9, False), CalibrationPoint(0.9, True)])
        assert bins[-1].gap == pytest.approx(0.4)

    def test_bin_count_is_configurable(self):
        assert len(calibrate([], bins=10).bins) == 10


class TestMissingConfidence:
    def test_it_is_counted_not_penalised(self):
        """Eksik güveni 0.5 varsaymak, söylenmemişi modele atfetmek olurdu."""
        report = calibrate([CalibrationPoint(0.9, True)], without_confidence=4)
        assert report.count == 1
        assert report.without_confidence == 4

    def test_serialisation_reports_both(self):
        payload = calibrate([CalibrationPoint(0.9, True)], without_confidence=4).to_dict()
        assert payload["count"] == 1
        assert payload["without_confidence"] == 4


class TestCollectFromPredictions:
    """Yalnızca doğrulanabilir tahminler kalibrasyona girer."""

    def build(self, effects):
        from rlens.verify.diff import diff_reports
        from rlens.verify.prediction import check_predictions

        def report(lcom4, cam=0.5, schema=2):
            return {
                "schema_version": schema,
                "generated_at": "2026-01-01T00:00:00+00:00",
                "modules": [
                    {
                        "module": "m",
                        "path": "m.py",
                        "classes": [
                            {
                                "name": "C",
                                "nom": 5,
                                "wmc": 5,
                                "lcom4": lcom4,
                                "dam": 0.5,
                                "dcc": 1,
                                "cam": cam,
                            }
                        ],
                        "functions": [],
                    }
                ],
            }

        delta = diff_reports(report(4), report(1))
        document = {
            "advices": [
                {"target": "m:C", "suggestions": [{"title": "s", "expected_effect": effects}]}
            ]
        }
        return check_predictions(document, delta)

    def test_hits_and_misses_become_points(self):
        result = self.build(
            [
                {"metric": "LCOM4", "direction": "down", "confidence": 0.9},
                {"metric": "NOM", "direction": "down", "confidence": 0.4},
            ]
        )
        report = collect_points(result)
        assert report.count == 2
        assert report.accuracy == 0.5

    def test_unverifiable_predictions_are_excluded(self):
        """Ölçemediğimiz tahminin güveni hakkında konuşamayız."""
        result = self.build([{"metric": "CC", "direction": "down", "confidence": 0.9}])
        report = collect_points(result)
        assert report.count == 0
        assert report.without_confidence == 0

    def test_predictions_without_confidence_are_counted_separately(self):
        result = self.build([{"metric": "LCOM4", "direction": "down"}])
        report = collect_points(result)
        assert report.count == 0
        assert report.without_confidence == 1

    def test_confidence_reaches_the_check(self):
        result = self.build([{"metric": "LCOM4", "direction": "down", "confidence": 0.7}])
        assert result.scores[0].checks[0].confidence == 0.7

    def test_non_numeric_confidence_is_dropped(self):
        result = self.build([{"metric": "LCOM4", "direction": "down", "confidence": "high"}])
        assert result.scores[0].checks[0].confidence is None
