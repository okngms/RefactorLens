"""`rlens loop`: advise → apply → verify → geri besleme (v2.4 Aşama 3).

Sabitlenenler (`docs/02` §4, §11):

* Her iterasyon HEAD'den bağımsız bir denemedir; ikinci iterasyonun öneri
  istemi bir öncekinin tahmin sonuçlarını taşır.
* Durma: tahminlerin hepsi doğrulanabilir ve doğru **ve** kapı geçti; ya da
  `max_iter`; ya da bütçe.
* Geri besleme bloğu ham eşik sayısı taşımaz (invariant: bütün prompt).
* İterasyon başına doğruluk, kapı, `suspicious`, maliyet ve Brier raporda;
  Brier elle hesaplanmış değerle test edilir.
"""

from __future__ import annotations

import json
import shutil

import pytest
from apply_support import (
    BROKEN_SHOP,
    IMPROVED_SHOP,
    TARGET,
    FakeProvider,
    diff_for,
    make_repo,
    reply,
)
from typer.testing import CliRunner

from rlens.cli import app
from rlens.config import load_config
from rlens.loop.feedback import build_feedback
from rlens.loop.runner import (
    ALL_HELD,
    BUDGET,
    MAX_ITER,
    iteration_calibration,
    run_loop,
)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def advice_reply(direction: str, confidence: float | None = None) -> str:
    effect = {"metric": "WMC", "direction": direction}
    if confidence is not None:
        effect["confidence"] = confidence
    return json.dumps(
        {
            "target": TARGET,
            "diagnosis": "price branches on kind",
            "suggestions": [
                {
                    "title": "Replace the branches with a lookup table",
                    "rationale_metric_link": ["WMC"],
                    "expected_effect": [effect],
                    "sketch": "Turn the if chain in price into a dict lookup.",
                }
            ],
            "risk_notes": "",
        }
    )


PATCH = reply(diff_for(IMPROVED_SHOP))


@pytest.fixture
def repo(tmp_path):
    root = make_repo(tmp_path)
    # Fikstürün tek sınıfı varsayılan eşiklerin altında; `advise` hedefi adıyla alır.
    return root


def loop(repo, provider, max_iter=3):
    return run_loop(repo, TARGET, load_config(search_from=repo), provider, max_iter=max_iter)


class TestStopping:
    def test_stops_when_every_prediction_held(self, repo):
        provider = FakeProvider(advice_reply("up"), PATCH, advice_reply("down"), PATCH)
        result = loop(repo, provider)
        assert result.stop_reason == ALL_HELD
        assert [i.outcome for i in result.iterations] == ["improved", "improved"]
        assert [(i.hits, i.misses) for i in result.iterations] == [(0, 1), (1, 0)]
        assert all(i.branch for i in result.iterations)

    def test_the_second_request_carries_the_feedback(self, repo):
        provider = FakeProvider(advice_reply("up"), PATCH, advice_reply("down"), PATCH)
        loop(repo, provider)
        first, second = provider.prompts[0], provider.prompts[2]
        assert "Feedback from previous attempt" not in first
        assert "Prediction WMC: up — actual: down (✗)" in second
        assert "Behavior gate: passed." in second

    def test_max_iter(self, repo):
        provider = FakeProvider(advice_reply("up"), PATCH, advice_reply("up"), PATCH)
        result = loop(repo, provider, max_iter=2)
        assert result.stop_reason == MAX_ITER
        assert len(result.iterations) == 2

    def test_budget(self, repo):
        (repo / "rlens.yaml").write_text(
            (repo / "rlens.yaml").read_text(encoding="utf-8")
            + "budget:\n  max_calls_per_run: 3\n  max_tokens_per_call: 4000\n",
            encoding="utf-8",
        )
        from apply_support import git

        git(repo, "commit", "-qam", "budget")
        provider = FakeProvider(advice_reply("up"), PATCH, advice_reply("up"), PATCH)
        result = loop(repo, provider)
        assert result.stop_reason == BUDGET
        assert len(result.iterations) == 1

    def test_a_broken_patch_is_fed_back(self, repo):
        broken = reply(diff_for(BROKEN_SHOP))
        provider = FakeProvider(advice_reply("down"), broken, advice_reply("down"), PATCH)
        result = loop(repo, provider)
        assert [i.outcome for i in result.iterations] == ["broken", "improved"]
        assert "Behavior gate: failed" in provider.prompts[2]
        assert result.stop_reason == ALL_HELD


class TestFeedback:
    def test_no_threshold_number_reaches_the_prompt(self, repo):
        """Invariant: geri besleme bloğu da dahil bütün istem eşiksiz."""
        config = load_config(search_from=repo)
        provider = FakeProvider(advice_reply("up"), PATCH, advice_reply("down"), PATCH)
        loop(repo, provider)
        second = provider.prompts[2]
        for key, threshold in config.thresholds.items():
            assert f"{key}: {threshold.warn}" not in second
            assert f"threshold {threshold.warn}" not in second
        assert "threshold" not in build_feedback_text(provider)

    def test_unverifiable_and_rejected(self):
        from rlens.apply.runner import REJECTED, ApplyResult

        result = ApplyResult(TARGET, 1, "Split it", "r1", outcome=REJECTED)
        result.rejections = ["The reply contains no ```diff block."]
        text = build_feedback(result)
        assert "could not be applied: The reply contains no ```diff block." in text
        assert "Prediction" not in text


def build_feedback_text(provider) -> str:
    prompt = provider.prompts[2]
    return prompt[prompt.index("## Feedback from previous attempt") :]


class TestCalibration:
    def test_brier_gold_value(self):
        """Elle: (0.9 − 1)² = 0.01, (0.6 − 0)² = 0.36 → ortalama 0.185.

        Güvensiz tahmin dışarıda kalır, sayılır; doğrulanamayan hiç girmez.
        """
        predictions = {
            "suggestions": [
                {
                    "checks": [
                        {"metric": "WMC", "outcome": "hit", "confidence": 0.9},
                        {"metric": "NOM", "outcome": "miss", "confidence": 0.6},
                        {"metric": "DCC", "outcome": "hit", "confidence": None},
                        {"metric": "CAM", "outcome": "unverifiable", "confidence": 0.8},
                    ]
                }
            ]
        }
        report = iteration_calibration(predictions)
        assert report.brier == 0.185
        assert report.without_confidence == 1

    def test_per_iteration_brier_is_reported(self, repo):
        provider = FakeProvider(advice_reply("up", 0.8), PATCH, advice_reply("down", 0.7), PATCH)
        result = loop(repo, provider)
        # (0.8 − 0)² = 0.64 ; (0.7 − 1)² = 0.09
        assert [i.brier for i in result.iterations] == [0.64, 0.09]
        assert result.to_dict()["overall"]["brier"] == round((0.64 + 0.09) / 2, 4)


class TestReport:
    def test_cost_and_counts_per_iteration(self, repo):
        provider = FakeProvider(advice_reply("up"), PATCH, advice_reply("down"), PATCH)
        payload = loop(repo, provider).to_dict()
        assert payload["schema_version"] == 1
        assert [i["calls"] for i in payload["iterations"]] == [2, 2]
        assert payload["overall"]["accuracy"] == 0.5
        assert payload["overall"]["gate_pass_rate"] == 1.0
        assert payload["overall"]["suspicious_rate"] == 0.0

    def test_cli_writes_a_report(self, repo, monkeypatch):
        provider = FakeProvider(advice_reply("up"), PATCH, advice_reply("down"), PATCH)
        monkeypatch.setattr("rlens.cli.get_provider", lambda config: provider)
        out = repo.parent / "out"
        result = CliRunner().invoke(
            app, ["loop", str(repo), "--target", TARGET, "-o", str(out), "--no-cache"]
        )
        assert result.exit_code == 0, result.output
        output = " ".join(result.output.split())
        assert "stopped: every prediction held" in output
        assert json.loads(next(out.glob("loop-*.json")).read_text("utf-8"))["iterations"]
        assert list(out.glob("loop-*.md"))


class TestProviderLimit:
    """Sağlayıcı sınırı ölçüm boşluğudur, modelin hatası değil (ön kayıt işletme notu)."""

    def test_a_too_large_request_ends_the_run_and_keeps_finished_iterations(self, repo):
        from rlens.loop.runner import PROVIDER_LIMIT
        from rlens.providers.base import ProviderRequestTooLarge

        class Limited(FakeProvider):
            def generate(self, system, user, config, temperature):
                if len(self.prompts) == 2:
                    self.prompts.append(user)
                    raise ProviderRequestTooLarge("HTTP 413: request too large")
                return super().generate(system, user, config, temperature)

        result = loop(repo, Limited(advice_reply("up"), PATCH, advice_reply("down"), PATCH))
        assert result.stop_reason == PROVIDER_LIMIT
        assert [i.outcome for i in result.iterations] == ["improved"]

    def test_a_too_large_repair_is_not_counted_as_a_rejected_patch(self, repo):
        from rlens.loop.runner import PROVIDER_LIMIT
        from rlens.providers.base import ProviderRequestTooLarge

        class Limited(FakeProvider):
            def generate(self, system, user, config, temperature):
                if len(self.prompts) == 2:  # öneri, patch, sonra onarım
                    self.prompts.append(user)
                    raise ProviderRequestTooLarge("HTTP 413")
                return super().generate(system, user, config, temperature)

        result = loop(repo, Limited(advice_reply("up"), "no diff here"))
        assert result.stop_reason == PROVIDER_LIMIT
        assert result.iterations == []

    def test_a_too_large_advice_repair_is_not_an_unstructured_reply(self, repo):
        from rlens.loop.runner import PROVIDER_LIMIT
        from rlens.providers.base import ProviderRequestTooLarge

        class Limited(FakeProvider):
            def generate(self, system, user, config, temperature):
                if len(self.prompts) == 1:
                    self.prompts.append(user)
                    raise ProviderRequestTooLarge("HTTP 413")
                return super().generate(system, user, config, temperature)

        result = loop(repo, Limited("not json"))
        assert result.stop_reason == PROVIDER_LIMIT

    def test_a_cut_off_advice_reply_is_a_measurement_gap(self, repo):
        from rlens.loop.runner import OUTPUT_LIMIT
        from rlens.providers.base import ProviderTruncated

        class Cutting(FakeProvider):
            def generate(self, system, user, config, temperature):
                if len(self.prompts) == 2:
                    self.prompts.append(user)
                    raise ProviderTruncated("finish_reason: length", partial="{")
                return super().generate(system, user, config, temperature)

        result = loop(repo, Cutting(advice_reply("up"), PATCH, advice_reply("down"), PATCH))
        assert result.stop_reason == OUTPUT_LIMIT
        assert [i.outcome for i in result.iterations] == ["improved"]
