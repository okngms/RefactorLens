"""Tahmin denetimi testleri.

En kritik grup `TestUnverifiableIsNotAMiss`: doğrulanamayan tahmini yanlış
saymak, modeli bizim ölçüm boşluğumuz yüzünden cezalandırmak olurdu ve Faz 5'in
sayılarını sistematik biçimde bozardı.
"""

import pytest

from rlens.analysis.model import SCHEMA_VERSION
from rlens.verify.diff import diff_reports
from rlens.verify.prediction import (
    HIT,
    MISS,
    UNVERIFIABLE,
    check_predictions,
    parse_applied,
)


def report(*classes, functions=(), schema=SCHEMA_VERSION):
    return {
        "schema_version": schema,
        "generated_at": "2026-01-01T00:00:00+00:00",
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
    base = {"name": name, "nom": 5, "wmc": 10, "lcom4": 4, "dam": 0.5, "dcc": 3, "cam": 0.5}
    base.update(metrics)
    return base


def func(name="f", **metrics):
    base = {
        "name": name,
        "cyclomatic_complexity": 10,
        "loc": 20,
        "param_count": 3,
        "max_nesting": 2,
    }
    base.update(metrics)
    return base


def advice(*effects, target="m:C", title="Split the class", extra_suggestions=()):
    suggestions = [
        {
            "title": title,
            "rationale_metric_link": ["LCOM4"],
            "expected_effect": [{"metric": m, "direction": d} for m, d in effects],
        }
    ]
    suggestions.extend(extra_suggestions)
    return {"advices": [{"target": target, "suggestions": suggestions}]}


class TestBasicOutcomes:
    def test_correct_prediction_is_a_hit(self):
        delta = diff_reports(report(cls(lcom4=4)), report(cls(lcom4=1)))
        result = check_predictions(advice(("LCOM4", "down")), delta)
        assert result.scores[0].checks[0].outcome == HIT
        assert result.accuracy == 1.0

    def test_wrong_direction_is_a_miss(self):
        delta = diff_reports(report(cls(lcom4=4)), report(cls(lcom4=1)))
        result = check_predictions(advice(("LCOM4", "up")), delta)
        assert result.scores[0].checks[0].outcome == MISS
        assert result.accuracy == 0.0

    def test_predicting_same_when_nothing_changed(self):
        delta = diff_reports(report(cls(nom=5)), report(cls(nom=5)))
        result = check_predictions(advice(("NOM", "same")), delta)
        assert result.scores[0].checks[0].outcome == HIT

    def test_predicting_change_when_nothing_moved_is_a_miss(self):
        delta = diff_reports(report(cls(nom=5)), report(cls(nom=5)))
        result = check_predictions(advice(("NOM", "down")), delta)
        assert result.scores[0].checks[0].actual == "same"
        assert result.scores[0].checks[0].outcome == MISS

    def test_mixed_results(self):
        delta = diff_reports(report(cls(lcom4=4, dcc=3)), report(cls(lcom4=1, dcc=9)))
        result = check_predictions(advice(("LCOM4", "down"), ("DCC", "down")), delta)
        assert result.hits == 1
        assert result.misses == 1
        assert result.accuracy == 0.5


class TestUnverifiableIsNotAMiss:
    """Ölçemediğimiz tahmin, modelin hatası değildir."""

    def test_uncomputable_metric_is_unverifiable(self):
        delta = diff_reports(report(cls(cam=None)), report(cls(cam=None)))
        check = check_predictions(advice(("CAM", "up")), delta).scores[0].checks[0]
        assert check.outcome == UNVERIFIABLE
        assert "could not be computed" in check.reason

    def test_unverifiable_is_excluded_from_accuracy(self):
        """Payda doğrulanabilir tahminlerden oluşur."""
        delta = diff_reports(report(cls(lcom4=4, cam=None)), report(cls(lcom4=1, cam=None)))
        result = check_predictions(advice(("LCOM4", "down"), ("CAM", "up")), delta)
        assert result.hits == 1
        assert result.unverifiable == 1
        assert result.accuracy == 1.0  # 1/1, 1/2 değil

    def test_no_verifiable_predictions_gives_none_not_zero(self):
        """Sıfır 'hepsi yanlış' demek olurdu; doğrusu 'ölçemedik'."""
        delta = diff_reports(report(cls(cam=None)), report(cls(cam=None)))
        result = check_predictions(advice(("CAM", "up")), delta)
        assert result.accuracy is None

    def test_metric_not_applicable_to_kind(self):
        """Model sınıf için 'CC düşecek' derse bu ölçülemez."""
        delta = diff_reports(report(cls()), report(cls()))
        check = check_predictions(advice(("CC", "down")), delta).scores[0].checks[0]
        assert check.outcome == UNVERIFIABLE
        assert "not measured for a class" in check.reason

    def test_removed_target_is_unverifiable(self):
        """Sınıf tamamen kaldırıldıysa metrikleri yoktur."""
        delta = diff_reports(report(cls()), report())
        check = check_predictions(advice(("LCOM4", "down")), delta).scores[0].checks[0]
        assert check.outcome == UNVERIFIABLE
        assert "no longer exists" in check.reason

    def test_unknown_target_is_unverifiable(self):
        delta = diff_reports(report(cls()), report(cls()))
        result = check_predictions(advice(("LCOM4", "down"), target="m:Ghost"), delta)
        check = result.scores[0].checks[0]
        assert check.outcome == UNVERIFIABLE
        assert "not found" in check.reason


class TestFunctionTargets:
    def test_function_metrics_are_checked(self):
        before = report(functions=[func(cyclomatic_complexity=15)])
        after = report(functions=[func(cyclomatic_complexity=5)])
        delta = diff_reports(before, after)
        result = check_predictions(advice(("CC", "down"), target="m:f"), delta)
        assert result.scores[0].checks[0].outcome == HIT

    def test_class_metric_on_a_function_is_unverifiable(self):
        before = report(functions=[func()])
        after = report(functions=[func()])
        delta = diff_reports(before, after)
        check = (
            check_predictions(advice(("LCOM4", "down"), target="m:f"), delta).scores[0].checks[0]
        )
        assert check.outcome == UNVERIFIABLE
        assert "not measured for a function" in check.reason


class TestAppliedFilter:
    """Uygulanmamış önerinin tahminini 'tutmadı' saymak anlamsızdır."""

    @pytest.fixture
    def two_suggestions(self):
        return advice(
            ("LCOM4", "down"),
            title="First",
            extra_suggestions=[
                {
                    "title": "Second",
                    "rationale_metric_link": ["DCC"],
                    "expected_effect": [{"metric": "DCC", "direction": "down"}],
                }
            ],
        )

    def test_without_filter_all_suggestions_are_checked(self, two_suggestions):
        delta = diff_reports(report(cls(lcom4=4, dcc=3)), report(cls(lcom4=1, dcc=3)))
        result = check_predictions(two_suggestions, delta)
        assert len(result.scores) == 2
        assert result.filtered is False

    def test_filter_limits_to_the_applied_suggestion(self, two_suggestions):
        delta = diff_reports(report(cls(lcom4=4, dcc=3)), report(cls(lcom4=1, dcc=3)))
        result = check_predictions(two_suggestions, delta, applied={"m:C": [1]})
        assert len(result.scores) == 1
        assert result.scores[0].title == "First"
        assert result.filtered is True

    def test_filter_changes_the_accuracy(self, two_suggestions):
        """İkinci öneri uygulanmadığı için onun 'tutmaması' sayıyı bozuyordu."""
        delta = diff_reports(report(cls(lcom4=4, dcc=3)), report(cls(lcom4=1, dcc=3)))
        unfiltered = check_predictions(two_suggestions, delta)
        filtered = check_predictions(two_suggestions, delta, applied={"m:C": [1]})
        assert unfiltered.accuracy == 0.5
        assert filtered.accuracy == 1.0

    def test_unlisted_target_is_skipped_entirely(self, two_suggestions):
        delta = diff_reports(report(cls()), report(cls()))
        result = check_predictions(two_suggestions, delta, applied={"m:Other": [1]})
        assert result.scores == []


class TestParseApplied:
    def test_single_index(self):
        assert parse_applied(["god:OrderManager=1"]) == {"god:OrderManager": [1]}

    def test_multiple_indices(self):
        assert parse_applied(["m:C=1,3"]) == {"m:C": [1, 3]}

    def test_multiple_targets(self):
        assert parse_applied(["m:A=1", "m:B=2"]) == {"m:A": [1], "m:B": [2]}

    def test_whitespace_is_tolerated(self):
        assert parse_applied([" m:C = 1 , 2 "]) == {"m:C": [1, 2]}

    def test_missing_equals_is_an_error(self):
        with pytest.raises(ValueError, match="TARGET=INDEX"):
            parse_applied(["god:OrderManager"])

    def test_non_numeric_index_is_an_error(self):
        with pytest.raises(ValueError, match="positive number"):
            parse_applied(["m:C=first"])

    def test_zero_index_is_an_error(self):
        """Öneriler 1'den numaralanır; 0 kullanıcı hatasıdır."""
        with pytest.raises(ValueError, match="positive number"):
            parse_applied(["m:C=0"])


class TestIncompatibility:
    def test_schema_mismatch_is_carried_into_the_report(self):
        delta = diff_reports(report(cls(), schema=1), report(cls(), schema=2))
        result = check_predictions(advice(("LCOM4", "down")), delta)
        assert result.comparable is False
        assert result.incompatibility


class TestSerialisation:
    def test_round_trip(self):
        delta = diff_reports(report(cls(lcom4=4)), report(cls(lcom4=1)))
        payload = check_predictions(advice(("LCOM4", "down")), delta).to_dict()
        assert payload["accuracy"] == 1.0
        assert payload["suggestions"][0]["checks"][0]["outcome"] == HIT

    def test_empty_document(self):
        delta = diff_reports(report(), report())
        result = check_predictions({"advices": []}, delta)
        assert result.scores == []
        assert result.accuracy is None
