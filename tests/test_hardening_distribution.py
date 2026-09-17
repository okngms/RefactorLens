"""Sertleştirme Blok 1b: metrik dağılımı (`experiments/hardening/distribution.py`).

Eşikler bu tablodan türetilecek; tablonun yanlış olması eşiğin yanlış olması
demektir. Burada sabitlenenler:

* **Eşik kuralı** `Threshold.level` ile aynı: `değer >= eşik`. `>` yazılsaydı
  CC=10 gibi tam eşikteki değerler "aşmamış" sayılır ve pay düşük çıkardı.
* **Ağırlıklandırma.** Genel değer projelerin medyanıdır; yeterli değeri
  olmayan proje (< `MIN_VALUES`) katılmaz.
* **`null`** dağılıma girmez, payı ayrıca sayılır.
* **Eşik listesi** varsayılan config'ten okunur; config'e yeni eşik eklenince
  tablo onu kendiliğinden gösterir.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from distribution import (  # noqa: E402
    MIN_VALUES,
    MetricValues,
    aggregate,
    collect_report,
    default_thresholds,
    exceedance,
    median_of,
    percentile,
    render_tables,
    summarise_values,
)


class TestPercentile:
    def test_linear_interpolation(self):
        # NumPy `linear`: konum = (n-1) * q
        assert percentile([1, 2, 3, 4], 50) == 2.5
        assert percentile([1, 2, 3, 4], 90) == pytest.approx(3.7)
        assert percentile([10], 99) == 10

    def test_order_does_not_matter(self):
        assert percentile([4, 1, 3, 2], 75) == percentile([1, 2, 3, 4], 75) == 3.25

    def test_empty(self):
        assert percentile([], 50) is None


class TestExceedance:
    def test_value_equal_to_threshold_counts(self):
        """`Threshold.level` ile aynı kural: CC=10, `warn: 10`'u karşılar."""
        assert exceedance([9, 10, 11, 5], 10) == 0.5

    def test_empty(self):
        assert exceedance([], 10) is None


class TestSummaries:
    def test_nulls_are_counted_but_not_in_the_distribution(self):
        collected = MetricValues()
        for value in [1, None, 3, None]:
            collected.add(value)
        summary = summarise_values(collected)
        assert summary["n"] == 2
        assert summary["null_share"] == 0.5
        assert summary["p50"] == 2

    def test_eligibility_threshold(self):
        small = MetricValues(values=list(range(MIN_VALUES - 1)))
        enough = MetricValues(values=list(range(MIN_VALUES)))
        assert summarise_values(small)["eligible"] is False
        assert summarise_values(enough)["eligible"] is True

    def test_aggregate_is_median_of_eligible_projects(self):
        def project(p90, eligible=True):
            entry = {f"p{q}": p90 for q in (50, 75, 90, 95, 99)}
            return {**entry, "null_share": 0.0, "eligible": eligible}

        summaries = {
            "a": project(2),
            "b": project(4),
            "c": project(10),
            "tiny": project(1000, False),
        }
        result = aggregate(summaries, summaries, "x")
        assert result["projects"] == 3
        assert result["p90"] == 4

    def test_median_of_skips_none(self):
        assert median_of([None, 1, 3]) == 2
        assert median_of([None]) is None


def fn(**metrics):
    base = {"cyclomatic_complexity": 1, "loc": 2, "param_count": 0, "max_nesting": 0}
    return SimpleNamespace(**(base | metrics))


def klass(methods=(), **metrics):
    base = {"nom": 0, "wmc": 0, "lcom4": None, "dcc": 0, "dam": None, "cam": None}
    return SimpleNamespace(methods=list(methods), **(base | metrics))


class TestCollectReport:
    def test_methods_and_module_functions_are_both_function_units(self):
        module = SimpleNamespace(
            functions=[fn(cyclomatic_complexity=3)],
            classes=[klass([fn(cyclomatic_complexity=7)], nom=1, lcom4=1)],
            ca=0,
            ce=2,
            instability=1.0,
        )
        collected = collect_report(SimpleNamespace(modules=[module]))
        assert sorted(collected["cyclomatic_complexity"].values) == [3, 7]
        assert collected["nom"].values == [1]
        assert collected["dam"].nulls == 1
        assert collected["instability"].values == [1.0]


class TestThresholds:
    def test_default_thresholds_come_from_config(self):
        from rlens.config import DEFAULTS

        rows = {(row["label"], row["level"]): row["value"] for row in default_thresholds()}
        assert rows[("CC", "warn")] == DEFAULTS["thresholds"]["cyclomatic_complexity"]["warn"]
        assert rows[("PARAMS", "warn")] == DEFAULTS["thresholds"]["max_params"]["warn"]
        assert rows[("LOC", "long_method")] == DEFAULTS["smells"]["long_method"]["loc"]
        assert ("LCOM4", "critical") in rows

    def test_render_tables_has_every_section(self):
        empty_type = {"projects": 0, "p90": None}
        summary = {
            "schema_version": 3,
            "min_values": MIN_VALUES,
            "metrics": {
                "cyclomatic_complexity": {
                    "label": "CC",
                    "unit": "function",
                    "all": {
                        "projects": 1,
                        "p50": 2,
                        "p75": 4,
                        "p90": 8,
                        "p95": 12,
                        "p99": 20,
                        "null_share": 0.0,
                    },
                    "by_type": {
                        k: empty_type for k in ("library", "cli", "web_app", "ml_research")
                    },
                    "pooled": {"p90": 8, "p99": 24, "n": 10},
                }
            },
            "thresholds": [],
            "god_class_gate": {
                "all": {
                    "size_qualified": 1,
                    "fired": 1,
                    "gated_by_lcom4": 0,
                    "gated_only_because_of_call_edges": 0,
                }
            },
            "smell_rates": {k: {} for k in ("library", "cli", "web_app", "ml_research")},
        }
        text = render_tables(summary)
        for heading in (
            "Dağılım — tüm korpus",
            "p90 tür bazında",
            "Mevcut eşikler",
            "god_class",
            "Koku oranları",
        ):
            assert heading in text
        assert "| CC | function | 1 | 2 | 4 | 8 | 12 | 20 | %0.0 | 8 | 24 |" in text
