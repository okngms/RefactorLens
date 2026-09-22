"""v2.2 §5b: `god_class` kör etiketli örneklemi (`experiments/hardening/god_class_sample.py`).

Sabitlenenler: örneklem deterministik ve tabakalı; etiketleyenin gördüğü dosya
metrik ya da kapı sonucu taşımaz; eksik ya da bayat karar varken özet üretilmez;
kesinlik ve duyarlılık hücre büyüklükleriyle ağırlıklıdır (elle hesaplandı).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from god_class_sample import (  # noqa: E402
    CELLS,
    blind_view,
    cell_of,
    stratified_pick,
    verdict_problems,
    weighted_scores,
)


def _population(sizes: dict[str, int]) -> list[dict]:
    items = []
    for cell, size in sizes.items():
        for i in range(size):
            items.append(
                {
                    "id": f"{cell}-{i:02d}",
                    "project": "p",
                    "file": f"{cell}.py",
                    "line": i + 1,
                    "class": f"C{i}",
                    "cell": cell,
                    "lcom4": 9,
                }
            )
    return items


class TestCells:
    def test_four_cells(self):
        assert cell_of(True, True) == "both"
        assert cell_of(True, False) == "current_only"
        assert cell_of(False, True) == "r4_only"
        assert cell_of(False, False) == "neither"


class TestPick:
    def test_per_cell_and_small_cells_taken_whole(self):
        population = _population({"both": 20, "current_only": 3, "r4_only": 9, "neither": 8})
        picked = stratified_pick(population, 8, seed=1)
        counts = {cell: sum(1 for i in picked if i["cell"] == cell) for cell in CELLS}
        assert counts == {"both": 8, "current_only": 3, "r4_only": 8, "neither": 8}

    def test_deterministic_and_order_independent(self):
        population = _population({"both": 20, "current_only": 20, "r4_only": 20, "neither": 20})
        first = stratified_pick(population, 5, seed=7)
        second = stratified_pick(list(reversed(population)), 5, seed=7)
        assert [i["id"] for i in first] == [i["id"] for i in second]


class TestBlindness:
    def test_no_metric_or_cell_reaches_the_labeller(self):
        view = blind_view(_population({"both": 1})[0])
        assert set(view) == {"id", "project", "file", "line", "class"}


def _sample():
    return [{"id": "a", "class": "A", "file": "a.py"}, {"id": "b", "class": "B", "file": "b.py"}]


class TestVerdictProblems:
    def test_complete(self):
        verdicts = {
            "a": {"class": "A", "file": "a.py", "verdict": "god", "responsibilities": ["x", "y"]},
            "b": {"class": "B", "file": "b.py", "verdict": "unsure"},
        }
        assert verdict_problems(_sample(), verdicts) == []

    def test_missing_and_empty_and_stale(self):
        verdicts = {"a": {"class": "Other", "file": "a.py", "verdict": None}}
        problems = verdict_problems(_sample(), verdicts)
        assert any("different class" in p for p in problems)
        assert any("must be one of" in p for p in problems)
        assert any("b: no verdict entry" in p for p in problems)

    def test_god_needs_two_named_responsibilities(self):
        verdicts = {
            "a": {"class": "A", "file": "a.py", "verdict": "god", "responsibilities": ["x"]},
            "b": {"class": "B", "file": "b.py", "verdict": "not_god"},
        }
        assert any("two responsibilities" in p for p in verdict_problems(_sample(), verdicts))

    def test_extra_verdict(self):
        verdicts = {
            "a": {"class": "A", "file": "a.py", "verdict": "not_god"},
            "b": {"class": "B", "file": "b.py", "verdict": "not_god"},
            "z": {"class": "Z", "file": "z.py", "verdict": "god"},
        }
        assert any("not in the sample" in p for p in verdict_problems(_sample(), verdicts))


class TestWeightedScores:
    def test_hand_computed(self):
        # Hücre büyüklükleri: both 40, current_only 20, r4_only 10, neither 30.
        # Etiketler (her hücrede 2 örnek):
        #   both: god, god         → tahmini god 40
        #   current_only: god, not → 10
        #   r4_only: not, unsure   → etiketli 1, god 0 → 0
        #   neither: god, not      → 15
        # Bugünkü kapı (both + current_only): ateşlenen 60, doğru 50
        #   kesinlik 50/60 = 0.8333, duyarlılık 50/65 = 0.7692.
        # R4 (both + r4_only): ateşlenen 50, doğru 40 → 0.8; 40/65 = 0.6154.
        strata = {
            "b1": "both",
            "b2": "both",
            "c1": "current_only",
            "c2": "current_only",
            "r1": "r4_only",
            "r2": "r4_only",
            "n1": "neither",
            "n2": "neither",
        }
        labels = {
            "b1": "god",
            "b2": "god",
            "c1": "god",
            "c2": "not_god",
            "r1": "not_god",
            "r2": "unsure",
            "n1": "god",
            "n2": "not_god",
        }
        verdicts = {key: {"verdict": value} for key, value in labels.items()}
        sizes = {"both": 40, "current_only": 20, "r4_only": 10, "neither": 30}
        current = weighted_scores(strata, sizes, verdicts, "current")
        assert current["precision"] == 0.8333
        assert current["recall"] == 0.7692
        assert current["labelled_per_cell"]["r4_only"] == 1
        r4 = weighted_scores(strata, sizes, verdicts, "r4")
        assert r4["precision"] == 0.8
        assert r4["recall"] == 0.6154
