"""LensBench altyapısı (v2.4 Aşama 6): suite, dondurma, koşu, kayıt, rapor.

Gerçek model çağrısı yok: sağlayıcı istemin türüne göre yanıt veren bir
sahte. Karar kuralları elle kurulmuş tahmin kümeleriyle sınanır; eşikler ön
kayıttakilerle aynı (`docs/lensbench-v1-onkayit.md`).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from apply_support import SHOP, TESTS
from typer.testing import CliRunner

from rlens.bench.report import (
    INSUFFICIENT,
    REFUTED,
    SUPPORTED,
    Prediction,
    h1,
    h3,
    h4,
    h5,
    load_results,
    report_markdown,
)
from rlens.bench.runner import JOURNAL, estimate_calls, plan, run_bench
from rlens.bench.suite import BenchError, load_models, load_suite, project_hash
from rlens.cli import app

ROOT = Path(__file__).resolve().parent.parent
SUITE = ROOT / "bench" / "lensbench-v1" / "suite.yaml"
MODELS = ROOT / "bench" / "lensbench-v1" / "models.yaml"
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


class TestRealSuite:
    def test_shape(self):
        suite = load_suite(SUITE)
        assert (len(suite.targets), len(suite.conditions), suite.repeats) == (4, 4, 3)
        assert len(plan(suite)) == 48
        assert [c.name for c in suite.conditions] == ["base", "no-arch", "metric-rules", "loop3"]

    def test_call_estimate(self):
        """En az: 36 birim × 2 + 12 testsiz birim × 3 = 108.
        En çok: iterasyon başına 4 (+1 testsiz); loop3 üç iterasyon."""
        low, high = estimate_calls(load_suite(SUITE))
        assert low == 36 * 2 + 12 * 3
        tested = 9 * (1 + 1 + 1 + 3) * 4  # 3 hedef × 3 tekrar × koşulların iterasyonları × 4
        untested = 3 * (1 + 1 + 1 + 3) * 5
        assert high == tested + untested

    def test_every_target_exists_in_its_project(self):
        from rlens.advise.selector import target_for
        from rlens.analysis.scanner import scan_project
        from rlens.config import load_config

        for target in load_suite(SUITE).targets:
            project = ROOT / target.project
            config = load_config(search_from=project)
            assert target_for(scan_project(project, config), config, target.target), target


class TestSuiteFile:
    def test_missing_key(self, tmp_path):
        (tmp_path / "s.yaml").write_text("name: x\nrepeats: 1\n", encoding="utf-8")
        with pytest.raises(BenchError, match="missing `temperature`"):
            load_suite(tmp_path / "s.yaml")

    def test_project_hash_ignores_caches_and_line_endings(self, tmp_path):
        (tmp_path / "a.py").write_bytes(b"x = 1\n")
        before = project_hash(tmp_path)
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "a.pyc").write_bytes(b"junk")
        (tmp_path / "a.py").write_bytes(b"x = 1\r\n")
        assert project_hash(tmp_path) == before
        (tmp_path / "a.py").write_bytes(b"x = 2\n")
        assert project_hash(tmp_path) != before


ADVICE = json.dumps(
    {
        "target": "app.shop:Pricing",
        "diagnosis": "",
        "suggestions": [
            {
                "title": "Tidy",
                "rationale_metric_link": ["WMC"],
                "expected_effect": [{"metric": "WMC", "direction": "down", "confidence": 0.8}],
                "sketch": "Do it.",
            }
        ],
        "risk_notes": "",
    }
)


class Scripted:
    """İstemin türüne göre yanıt: öneri JSON'u ya da uygulanamayan patch."""

    name = "fake"

    def __init__(self):
        self.calls = 0

    def generate(self, system, user, config, temperature):
        self.calls += 1
        if "## Suggestion to apply" in user:
            return "no diff here"
        return ADVICE


@pytest.fixture
def mini(tmp_path):
    repo = tmp_path / "repo"
    project = repo / "proj"
    (project / "app").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "app" / "__init__.py").write_text("", encoding="utf-8")
    (project / "app" / "shop.py").write_text(SHOP, encoding="utf-8")
    (project / "tests" / "test_shop.py").write_text(TESTS, encoding="utf-8")
    (project / "rlens.yaml").write_text(
        "scan:\n  include: ['.']\n  exclude: ['tests/']\n", encoding="utf-8"
    )
    suite = tmp_path / "suite.yaml"
    suite.write_text(
        "name: mini\nrepeats: 2\ntemperature: 0.2\n"
        "conditions:\n  - {name: base, arch_context: true, metric_rules: false, max_iter: 1}\n"
        "targets:\n  - project: proj\n    target: app.shop:Pricing\n"
        "    tests: '{python} -m pytest tests -q -p no:cacheprovider'\n",
        encoding="utf-8",
    )
    return repo, load_suite(suite)


@needs_git
class TestRun:
    def test_results_carry_hashes_and_every_unit(self, mini, tmp_path):
        repo, suite = mini
        provider = Scripted()
        path = run_bench(suite, repo, "fake", "m1", provider, tmp_path / "out")
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 1
        assert set(payload) >= {"suite_hash", "prompt_hash", "project_hashes", "rlens_version"}
        assert [(u["condition"], u["repeat"]) for u in payload["units"]] == [
            ("base", 1),
            ("base", 2),
        ]
        # Her tekrar: öneri + patch + patch onarımı = 3 çağrı; önbellek yok.
        assert provider.calls == 6
        assert payload["units"][0]["loop"]["iterations"][0]["outcome"] == "rejected"

    def test_a_restarted_run_skips_finished_units(self, mini, tmp_path):
        repo, suite = mini
        run_bench(suite, repo, "fake", "m1", Scripted(), tmp_path / "out")

        class Refuse:
            name = "fake"

            def generate(self, *args):
                raise AssertionError("finished units must come from the journal")

        path = run_bench(suite, repo, "fake", "m1", Refuse(), tmp_path / "out")
        assert len(json.loads(path.read_text(encoding="utf-8"))["units"]) == 2
        assert (tmp_path / "out" / JOURNAL).exists()

    def test_the_source_project_is_not_touched(self, mini, tmp_path):
        repo, suite = mini
        before = project_hash(repo / "proj")
        run_bench(suite, repo, "fake", "m1", Scripted(), tmp_path / "out")
        assert project_hash(repo / "proj") == before
        assert not (repo / "proj" / ".git").exists()


def p(
    model="a",
    condition="base",
    iteration=1,
    last=True,
    metric="WMC",
    predicted="down",
    outcome="hit",
    confidence=None,
    kind="extract_method",
    wrappers=False,
):
    return Prediction(
        model,
        "t",
        condition,
        iteration,
        last,
        metric,
        predicted,
        outcome,
        confidence,
        kind,
        wrappers,
    )


def many(n, **kwargs):
    return [p(**kwargs) for _ in range(n)]


class TestVerdicts:
    def test_h1_supported(self):
        items = []
        for model in "abcd":
            items += many(
                10, model=model, condition="loop3", iteration=1, last=False, outcome="miss"
            )
            items += many(10, model=model, condition="loop3", iteration=3, last=True, outcome="hit")
        verdict, gains = h1(items)
        assert verdict == SUPPORTED
        assert gains == {m: 1.0 for m in "abcd"}

    def test_h1_needs_four_models(self):
        items = many(10, condition="loop3", iteration=1, last=False) + many(
            10, condition="loop3", iteration=2, last=True
        )
        assert h1(items)[0] == INSUFFICIENT

    def test_h3_supported_and_refuted(self):
        over = []
        for model in "abcd":
            over += many(10, model=model, outcome="miss", confidence=0.9)
        assert h3(over)[0] == SUPPORTED
        humble = []
        for model in "abcd":
            humble += many(10, model=model, outcome="hit", confidence=0.6)
        assert h3(humble)[0] == REFUTED

    def test_h4_spread(self):
        items = many(20, kind="extract_class", outcome="hit") + many(
            20, kind="extract_method", outcome="miss"
        )
        assert h4(items) == (SUPPORTED, {"extract_class": 1.0, "extract_method": 0.0})

    def test_h5_wrappers(self):
        items = many(10, metric="NOM", outcome="miss", wrappers=True) + many(
            10, metric="NOM", outcome="hit", wrappers=False
        )
        verdict, rates = h5(items)
        assert verdict == SUPPORTED
        assert (rates["with_wrappers"], rates["without_wrappers"]) == (1.0, 0.0)

    def test_unverifiable_never_counts(self):
        items = many(10, metric="NOM", outcome="unverifiable", wrappers=True)
        assert h5(items)[0] == INSUFFICIENT


@needs_git
class TestReportAndCli:
    def test_mismatched_results_are_refused(self, mini, tmp_path):
        repo, suite = mini
        path = run_bench(suite, repo, "fake", "m1", Scripted(), tmp_path / "out")
        other = json.loads(path.read_text(encoding="utf-8"))
        other["prompt_hash"] = "different"
        second = tmp_path / "other.json"
        second.write_text(json.dumps(other), encoding="utf-8")
        with pytest.raises(BenchError, match="prompt_hash"):
            load_results([path, second])

    def test_report_has_every_section(self, mini, tmp_path):
        repo, suite = mini
        path = run_bench(suite, repo, "fake", "m1", Scripted(), tmp_path / "out")
        text = report_markdown(load_results([path]))
        for heading in ("## Per model", "## Per metric", "## Per condition", "H1", "H5", "H2"):
            assert heading in text

    def test_cli_dry_run_states_the_cost(self):
        result = CliRunner().invoke(app, ["bench", "run", "--suite", str(SUITE), "--dry-run"])
        assert result.exit_code == 0, result.output
        output = " ".join(result.output.split())
        assert "48 runs" in output
        assert "108" in output

    def test_cli_report(self, mini, tmp_path):
        repo, suite = mini
        path = run_bench(suite, repo, "fake", "m1", Scripted(), tmp_path / "out")
        out = tmp_path / "report.md"
        result = CliRunner().invoke(app, ["bench", "report", str(path), "-o", str(out)])
        assert result.exit_code == 0, result.output
        assert out.read_text(encoding="utf-8").startswith("# LensBench report")


class TestModels:
    def test_the_primary_set(self):
        # N4: qwen çıktı (ücretsiz katmanda çağrılamıyor); Gemini satırı
        # GEMINI_API_KEY gelince eklenecek ve bu liste üçe çıkacak.
        models = load_models(MODELS)
        assert [(m.provider, m.model) for m in models if m.primary] == [
            ("groq", "openai/gpt-oss-120b"),
            ("groq", "openai/gpt-oss-20b"),
        ]
        assert models[0].label == "groq/openai/gpt-oss-120b"

    def test_a_model_without_primary_is_refused(self, tmp_path):
        (tmp_path / "m.yaml").write_text(
            "models:\n  - {provider: groq, model: x}\n", encoding="utf-8"
        )
        with pytest.raises(BenchError, match="primary"):
            load_models(tmp_path / "m.yaml")

    def test_models_added_later_never_change_a_verdict(self):
        """Birincil üç model H3'te aşırı güvenli değil; sonradan eklenen bir model
        ne kadar aşırı güvenli olursa olsun hüküm değişmez."""
        items = []
        for model in ("a", "b", "c"):
            items += many(10, model=model, outcome="hit", confidence=0.6)
        later = many(10, model="z", outcome="miss", confidence=0.99)
        from rlens.bench.report import verdict_items

        primary = verdict_items(items + later, {"a", "b", "c"})
        assert h3(primary)[0] == REFUTED
        assert {p.model for p in primary} == {"a", "b", "c"}

    def test_three_models_are_enough_and_all_must_agree(self):
        items = []
        for model, outcome in (("a", "miss"), ("b", "miss"), ("c", "hit")):
            items += many(10, model=model, outcome=outcome, confidence=0.9)
        # İki model aşırı güvenli, biri değil: üçte üç şartı sağlanmaz.
        from rlens.bench.report import INCONCLUSIVE

        assert h3(items)[0] == INCONCLUSIVE

    def test_dry_run_with_the_models_file(self):
        result = CliRunner().invoke(
            app, ["bench", "run", "--suite", str(SUITE), "--models", str(MODELS), "--dry-run"]
        )
        assert result.exit_code == 0, result.output
        output = " ".join(result.output.split())
        assert "2 models" in output
        assert "between 216 and 612 model calls in total" in output


class TestRotation:
    """Kotaya takılan model bırakılır, sıradakine geçilir; hepsi takılınca beklenir."""

    def entries(self):
        from rlens.bench.suite import ModelEntry

        return [ModelEntry("groq", "a", True), ModelEntry("groq", "b", True)]

    def test_a_limited_model_does_not_stop_the_others(self):
        from rlens.bench.runner import run_rotation
        from rlens.providers.base import ProviderRateLimited

        def run_one(entry):
            if entry.model == "a":
                raise ProviderRateLimited("HTTP 429 tokens per day")
            return Path(f"{entry.model}.json")

        done, blocked = run_rotation(self.entries(), run_one, log=lambda _: None)
        assert done == {"groq/b": Path("b.json")}
        assert [e.label for e in blocked] == ["groq/a"]

    def test_waiting_retries_the_blocked_until_done(self):
        from rlens.bench.runner import run_rotation
        from rlens.providers.base import ProviderRateLimited

        attempts = {"a": 0}
        slept = []

        def run_one(entry):
            if entry.model == "a":
                attempts["a"] += 1
                if attempts["a"] < 3:
                    raise ProviderRateLimited("HTTP 429")
            return Path(f"{entry.model}.json")

        done, blocked = run_rotation(
            self.entries(), run_one, wait_minutes=10, sleep=slept.append, log=lambda _: None
        )
        assert blocked == []
        assert set(done) == {"groq/a", "groq/b"}
        assert slept == [600, 600]

    def test_other_provider_errors_stop_the_run(self):
        from rlens.bench.runner import run_rotation
        from rlens.providers.base import ProviderError

        def run_one(entry):
            raise ProviderError("Authentication failed")

        with pytest.raises(ProviderError, match="Authentication"):
            run_rotation(self.entries(), run_one, wait_minutes=10, log=lambda _: None)


def test_bench_advice_calls_get_the_patch_output_limit(mini):
    """N3: `advise` çağrıları da `apply.max_output_tokens` ile; sağlayıcının
    varsayılanı gpt-oss-20b'nin yanıtını kesiyordu."""
    from rlens.bench.runner import unit_config

    repo, suite = mini
    config = unit_config(repo / "proj", suite, suite.targets[0], "groq", "m", "python")
    assert config.provider.max_output_tokens == config.apply.max_output_tokens == 16384
