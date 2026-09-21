"""Sertleştirme Blok 1b: eşik kararı (K8) ve girdisi (`experiments/hardening/thresholds.py`).

Burada sabitlenenler:

* **Aday ölçümü** aracın eşik kuralıyla aynı: `değer >= eşik`, `None` asla
  işaretlenmez.
* **Varsayılanlar** kararla aynı: LCOM4 5/10. Kaynak `docs/04` §3.
* **Deney fikstürleri** v2.0.0 eşiklerini taşır. FINDINGS-1/2 o eşiklerle
  üretildi; sabitleme kaldırılırsa deney yeniden koşulduğunda prompt'taki
  bayraklar ve hedef seçimi değişir.
* **LCOM4 eşiği hiçbir kokuya girmez.** Şema sürümünün artmamasının gerekçesi
  budur (K8): eşik değişse de scan raporu aynı kalır.
"""

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from distribution import MIN_VALUES  # noqa: E402
from thresholds import (  # noqa: E402
    ProjectSample,
    aggregate,
    class_flag_shares,
    flagged,
    keyword_only_count,
    kwonly_summary,
    summarise_project,
)

from rlens.config import DEFAULTS, load_config  # noqa: E402

CLASS_RULES = {"nom": 20, "wmc": 50, "dcc": 7}


def _values(nom=1, wmc=1, dcc=0, lcom4=None):
    return {"nom": nom, "wmc": wmc, "dcc": dcc, "lcom4": lcom4}


class TestFlagged:
    def test_equal_to_threshold_counts(self):
        assert flagged({"lcom4": 5}, {"lcom4": 5}) == {"lcom4"}

    def test_none_never_flags(self):
        assert flagged({"lcom4": None}, {"lcom4": 1}) == set()

    def test_several(self):
        assert flagged(_values(nom=25, dcc=9), CLASS_RULES) == {"nom", "dcc"}


class TestClassFlagShares:
    def test_only_lcom4_excludes_classes_flagged_by_other_metrics(self):
        sample = ProjectSample(
            class_values=[
                _values(lcom4=6),  # yalnız LCOM4
                _values(lcom4=6, nom=25),  # LCOM4 ve NOM
                _values(lcom4=1),  # hiçbiri
                _values(lcom4=None, dcc=8),  # yalnız DCC; lcom4 null
            ]
        )
        shares = class_flag_shares(sample, CLASS_RULES, lcom4_warn=5)
        assert shares == {"any": 0.75, "only_lcom4": 0.25}

    def test_raising_the_lcom4_threshold_can_only_lower_the_shares(self):
        sample = ProjectSample(class_values=[_values(lcom4=v) for v in (1, 2, 3, 4, 5, 6)])
        low = class_flag_shares(sample, CLASS_RULES, lcom4_warn=2)
        high = class_flag_shares(sample, CLASS_RULES, lcom4_warn=5)
        assert high["any"] < low["any"]
        assert high["only_lcom4"] < low["only_lcom4"]

    def test_empty(self):
        assert class_flag_shares(ProjectSample(), CLASS_RULES, 5) == {
            "any": None,
            "only_lcom4": None,
        }


class TestKeywordOnly:
    def test_counts_names_after_star(self):
        node = ast.parse("def f(a, b, *, c, d, e): pass").body[0]
        assert keyword_only_count(node) == 3

    def test_after_varargs(self):
        node = ast.parse("def f(a, *args, c): pass").body[0]
        assert keyword_only_count(node) == 1

    def test_none(self):
        assert keyword_only_count(ast.parse("def f(a, b): pass").body[0]) == 0

    def test_summary(self):
        summaries = [
            {"too_many_params": 4, "rescued_by_kwonly": 1},
            {"too_many_params": 6, "rescued_by_kwonly": 3},
            {"too_many_params": 0, "rescued_by_kwonly": 0},
        ]
        result = kwonly_summary(summaries)
        assert result["firings"] == 10
        assert result["rescued"] == 4
        assert result["pooled_share"] == 0.4
        # Kokusu olmayan proje medyana katılmaz: medyan(0.25, 0.5)
        assert result["median_share"] == 0.375


class TestAggregate:
    def test_each_denominator_has_its_own_eligibility(self):
        big = ProjectSample(
            lcom4_computed=[1] * MIN_VALUES + [6] * MIN_VALUES,
            lcom4_informative=[6] * MIN_VALUES,
            class_values=[_values(lcom4=1)] * (2 * MIN_VALUES),
        )
        small = ProjectSample(lcom4_computed=[6], lcom4_informative=[6], class_values=[_values()])
        summaries = [summarise_project(big, CLASS_RULES), summarise_project(small, CLASS_RULES)]
        result = aggregate(summaries, 5)
        assert result["computed_projects"] == 1
        assert result["computed"] == 0.5
        assert result["informative"] == 1.0


class TestDecision:
    def test_default_lcom4_thresholds(self):
        assert DEFAULTS["thresholds"]["lcom4"] == {"warn": 5, "critical": 10}

    @pytest.mark.parametrize("fixture", ["messy_project", "layered_project"])
    def test_experiment_fixtures_keep_the_v2_thresholds(self, fixture):
        config = load_config(search_from=REPO_ROOT / "examples" / fixture)
        lcom4 = config.thresholds["lcom4"]
        assert (lcom4.warn, lcom4.critical) == (2, 4)

    def test_lcom4_threshold_reaches_no_smell(self, tmp_path):
        """Eşik değişince scan raporu değişmez; şema sürümü bu yüzden artmadı (K8)."""
        from rlens.analysis.scanner import scan_project

        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "__init__.py").write_text("")
        source = "class A:\n" + "".join(
            f"    def m{i}(self):\n        return self.a{i}\n" for i in range(6)
        )
        (tmp_path / "pkg" / "mod.py").write_text(source)
        reports = []
        for warn, critical in ((2, 4), (5, 10)):
            config_path = tmp_path / f"{warn}.yaml"
            config_path.write_text(
                "scan:\n  include: ['.']\n"
                f"thresholds:\n  lcom4: {{warn: {warn}, critical: {critical}}}\n"
            )
            report = scan_project(tmp_path, load_config(config_path)).to_dict()
            report.pop("generated_at", None)
            report.pop("root", None)
            reports.append(report)
        (cls,) = [c for m in reports[0]["modules"] for c in m["classes"]]
        assert cls["lcom4"] == 6
        assert reports[0] == reports[1]
