"""Faz 5a deney betiklerinin mantığı.

108 çağrılık bir deneyde bir hata pahalıdır ve genelde ancak veri toplandıktan
sonra fark edilir. Bu testler koşul matrisi, yol şeması ve önbellek tuzunu
ağa çıkmadan doğrular.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments"))

from analyse_advice_v2 import (  # noqa: E402
    CONDITION_LABELS,
    Run,
    condition_summary,
    consistency,
    load_runs,
    ratio,
    smell_addressing,
)
from run_advice_v2 import CONDITIONS, output_path, plan, slug  # noqa: E402

LAYERED = REPO_ROOT / "examples" / "layered_project"


class TestConditionMatrix:
    def test_four_cells(self):
        assert len(CONDITIONS) == 4

    def test_every_combination_is_present(self):
        assert set(CONDITIONS.values()) == {
            (False, False),
            (True, False),
            (False, True),
            (True, True),
        }

    def test_every_condition_has_a_label(self):
        assert set(CONDITION_LABELS) == set(CONDITIONS)

    def test_arch_flag_matches_the_name(self):
        assert CONDITIONS["arch"][0] is True
        assert CONDITIONS["plain"][0] is False

    def test_rules_flag_matches_the_name(self):
        assert CONDITIONS["rules"][1] is True
        assert CONDITIONS["arch_rules"] == (True, True)


class TestPaths:
    def test_slug_replaces_separators(self):
        assert slug("openai/gpt-oss-120b") == "openai_gpt-oss-120b"
        assert slug("god:OrderManager") == "god_OrderManager"

    def test_condition_is_the_first_level(self, tmp_path):
        path = output_path(tmp_path, "arch", "a/b", "m:C", 2)
        assert path.relative_to(tmp_path).parts == ("arch", "a_b", "m_C", "rep2.json")

    def test_conditions_do_not_collide(self, tmp_path):
        first = output_path(tmp_path, "arch", "m", "t", 1)
        second = output_path(tmp_path, "rules", "m", "t", 1)
        assert first != second


class TestPlan:
    class FakeTarget:
        qualified_name = "m:C"

    def test_total_is_the_product(self, tmp_path):
        contexts = [(self.FakeTarget(), None)]
        pending, skipped = plan(contexts, ["m1", "m2"], 3, tmp_path)
        assert len(pending) == 4 * 2 * 3
        assert skipped == 0

    def test_existing_runs_are_skipped(self, tmp_path):
        contexts = [(self.FakeTarget(), None)]
        path = output_path(tmp_path, "plain", "m1", "m:C", 1)
        path.parent.mkdir(parents=True)
        path.write_text("{}", encoding="utf-8")
        pending, skipped = plan(contexts, ["m1"], 1, tmp_path)
        assert skipped == 1
        assert len(pending) == 3

    def test_every_cell_appears_once(self, tmp_path):
        contexts = [(self.FakeTarget(), None)]
        pending, _ = plan(contexts, ["m1"], 2, tmp_path)
        keys = {(c, m, r) for c, m, r, _, _ in pending}
        assert len(keys) == len(pending)


class TestCacheSalt:
    """Tuz olmadan tekrarlar birbirinin kopyası olur ve varyans görünmez."""

    def test_repetitions_get_different_keys(self):
        from rlens.llm.cache import prompt_hash

        first = prompt_hash("groq", "m", "prompt", "rep1")
        second = prompt_hash("groq", "m", "prompt", "rep2")
        assert first != second

    def test_no_salt_is_the_default(self):
        from rlens.llm.cache import prompt_hash

        assert prompt_hash("groq", "m", "p") == prompt_hash("groq", "m", "p", "")

    def test_same_salt_is_stable(self):
        from rlens.llm.cache import prompt_hash

        assert prompt_hash("groq", "m", "p", "rep1") == prompt_hash("groq", "m", "p", "rep1")

    def test_request_advice_passes_it_through(self, tmp_path):
        """Aynı prompt, farklı tekrar → önbellek ıskası, gerçek çağrı."""
        from rlens.advise.advisor import request_advice
        from rlens.advise.context import build_context
        from rlens.advise.selector import select_targets
        from rlens.analysis.scanner import scan_project_with_sources
        from rlens.config import CacheConfig, load_config
        from rlens.llm.cache import ResponseCache

        config = load_config(search_from=LAYERED)
        result = scan_project_with_sources(LAYERED, config)
        target = select_targets(result.report, config, 1)[0]
        context = build_context(
            target, result.modules, result.project_classes, config.advise.max_context_tokens
        )

        calls = {"n": 0}

        class Counting:
            name = "groq"

            def generate(self, system, user, cfg, temperature=0.2):
                calls["n"] += 1
                return json.dumps(
                    {"target": target.qualified_name, "suggestions": [], "diagnosis": "d"}
                )

        cache = ResponseCache(CacheConfig(enabled=True, directory=str(tmp_path)))
        provider = Counting()
        request_advice(provider, context, config, cache=cache, cache_salt="rep1")
        request_advice(provider, context, config, cache=cache, cache_salt="rep2")
        assert calls["n"] == 2

        request_advice(provider, context, config, cache=cache, cache_salt="rep1")
        assert calls["n"] == 2


def make_run(condition="arch", model="m", target="m:C", repetition=1, **fields):
    suggestion = {
        "title": "s",
        "rationale_metric_link": fields.get("links", ["LCOM4"]),
        "expected_effect": fields.get("effects", []),
        "status": fields.get("status", "linked"),
        "addresses_smells": fields.get("smells", []),
        "target_layer_after": fields.get("layer"),
        "claims_constraints_respected": fields.get("claims"),
        "constraint_agreement": fields.get("agreement"),
    }
    return Run(
        condition=condition,
        model=model,
        target=target,
        repetition=repetition,
        suggestions=[suggestion],
    )


class TestConditionSummary:
    def test_rejected_rate(self):
        runs = [make_run(status="rejected"), make_run()]
        summary = condition_summary(runs)
        assert summary["rejected"] == 1
        assert summary["rejected_rate"] == 0.5

    def test_disagreement_rate_uses_claims_as_denominator(self):
        """Beyanda bulunmayan öneri paydaya girmez."""
        runs = [
            make_run(claims=True, agreement=False),
            make_run(claims=True, agreement=True),
            make_run(),
        ]
        summary = condition_summary(runs)
        assert summary["claimed_constraints"] == 2
        assert summary["disagreement_rate"] == 0.5

    def test_confidence_rate(self):
        runs = [
            make_run(effects=[{"metric": "NOM", "direction": "down", "confidence": 0.8}]),
            make_run(effects=[{"metric": "NOM", "direction": "down"}]),
        ]
        assert condition_summary(runs)["confidence_rate"] == 0.5

    def test_empty_denominator_is_none(self):
        """Sıfır yanıltıcı olurdu."""
        assert ratio(0, 0) is None


class TestSmellAddressing:
    def test_a_real_label_is_not_wrong(self):
        runs = [make_run(smells=["god_class"])]
        row = smell_addressing(runs, {"m:C": {"god_class"}})[0]
        assert row["wrong"] == 0

    def test_an_invented_label_is_counted(self):
        runs = [make_run(smells=["shotgun_surgery"])]
        row = smell_addressing(runs, {"m:C": {"god_class"}})[0]
        assert row["wrong"] == 1
        assert row["wrong_rate"] == 1.0

    def test_a_label_the_target_lacks_is_wrong(self):
        """Başka sınıfta olan etiket bu hedefte yoktur."""
        runs = [make_run(target="m:Other", smells=["god_class"])]
        row = smell_addressing(runs, {"m:C": {"god_class"}})[0]
        assert row["wrong"] == 1


class TestConsistency:
    def test_identical_runs_score_one(self):
        runs = [make_run(repetition=i) for i in (1, 2, 3)]
        assert consistency(runs)[0]["evidence"] == 1.0

    def test_disjoint_runs_score_zero(self):
        runs = [
            make_run(repetition=1, links=["LCOM4"]),
            make_run(repetition=2, links=["DCC"]),
        ]
        assert consistency(runs)[0]["evidence"] == 0.0

    def test_a_single_repetition_is_skipped(self):
        assert consistency([make_run()]) == []

    def test_conditions_are_kept_apart(self):
        runs = [
            make_run(condition="arch", repetition=1),
            make_run(condition="arch", repetition=2),
            make_run(condition="plain", repetition=1),
            make_run(condition="plain", repetition=2),
        ]
        assert len({row["condition"] for row in consistency(runs)}) == 2


class TestLoadRuns:
    def test_condition_comes_from_the_file_not_the_path(self, tmp_path):
        """Dizin adı taşınabilir; içerik taşınmaz."""
        path = tmp_path / "wrongdir" / "m" / "t" / "rep1.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "condition": "arch_rules",
                    "model": "m1",
                    "advices": [{"target": "m:C", "suggestions": []}],
                }
            ),
            encoding="utf-8",
        )
        assert load_runs(tmp_path)[0].condition == "arch_rules"

    def test_empty_directory(self, tmp_path):
        assert load_runs(tmp_path) == []
