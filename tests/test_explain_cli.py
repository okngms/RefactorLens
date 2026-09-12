"""`rlens explain` komut yüzeyi ve uçtan uca akışı.

Buradaki `TestNoRawThresholds`, `test_explain.py`'dakinin **CLI seviyesindeki**
eşi. İkisi birden gerekli: prompt kurucusu temiz olsa bile komut, raporu başka
bir yoldan biçimlendirip eşiği sızdırabilir. `advise` tarafında da aynı ikili
kontrol var.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rlens.analysis.model import EXPLAIN_SCHEMA_VERSION
from rlens.cli import app, explain


def flat(text: str) -> str:
    """Satır sarmasını düzler.

    rich, terminal genişliğine göre sarar; runner'ın genişliği makineden
    makineye değişir. Sarma bir cümleyi ikiye böldüğünde alt dize araması
    kodla ilgisi olmayan bir sebeple başarısız olur. Testler metnin
    kendisini ölçmeli, nerede sardığını değil.
    """
    return " ".join(text.split())


runner = CliRunner()


class FakeProvider:
    """Sırayla verilen cevapları döndüren sahte sağlayıcı."""

    name = "fake"

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def generate(self, system, user, config, temperature=0.2):
        self.calls.append((system, user))
        return self.replies.pop(0) if self.replies else ""


REPLY = json.dumps(
    {
        "summary": "The measurements cover four classes.",
        "findings": [
            {
                "statement": "Its methods split into two groups that share no attributes.",
                "subjects": ["mod:Widget"],
                "metric_link": ["LCOM4", "NOM"],
            },
            {"statement": "No metric named here.", "subjects": ["mod:Other"]},
        ],
        "not_shown": "Module-level functions are outside these metrics.",
    }
)


@pytest.fixture
def project(tmp_path):
    """İki bileşenli bir sınıf — LCOM4 2, eşik ihlali var."""
    (tmp_path / "rlens.yaml").write_text(
        "scan:\n  include: ['.']\n  output_dir: out/\n", encoding="utf-8"
    )
    (tmp_path / "mod.py").write_text(
        "class Widget:\n"
        "    def __init__(self):\n        self.a = 1\n        self.b = 2\n"
        "    def touch_a(self):\n        return self.a\n"
        "    def touch_b(self):\n        return self.b\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def fake(monkeypatch):
    provider = FakeProvider(REPLY)
    monkeypatch.setattr("rlens.cli.get_provider", lambda config: provider)
    return provider


class TestSurface:
    def test_help_lists_explain(self):
        assert "explain" in runner.invoke(app, ["--help"]).output

    def test_it_says_it_gives_no_advice(self):
        # `--help` çıktısı dar terminalde açıklamaları kırpar; söz verilen şey
        # komutun kendi docstring'idir, listede kaç karakterinin göründüğü değil.
        assert "no advice" in (explain.__doc__ or "")


class TestDryRun:
    def test_it_needs_no_api_key(self, project):
        result = runner.invoke(app, ["explain", str(project), "--dry-run"])
        assert result.exit_code == 0

    def test_it_prints_both_halves_of_the_prompt(self, project):
        output = runner.invoke(app, ["explain", str(project), "--dry-run"]).output
        assert "--- system ---" in output
        assert "--- user ---" in output

    def test_it_makes_no_call(self, project, fake):
        runner.invoke(app, ["explain", str(project), "--dry-run"])
        assert fake.calls == []


class TestNoRawThresholds:
    """CLI seviyesinde eşik sızıntısı kontrolü.

    "thresholds" **kelimesi** sistem talimatında geçer — modele eşiklerin başka
    bir dil için kalibre edildiği söylenir, bu kasıtlı. Sızıntı olan şey
    değerlerdir, o yüzden test kullanıcı bloğunu ayrı alır.
    """

    @staticmethod
    def user_block(project) -> str:
        """Kullanıcı bloğu, proje yolu maskelenmiş.

        Maskeleme şart: `tmp_path` dizin adına **test adını** koyar ve prompt
        proje kökünü basar. Maskelenmezse `test_..._thresholds_...` adlı bir
        test kendi adı yüzünden başarısız olur — ölçtüğü şeyle ilgisi olmayan
        bir sebeple.
        """
        output = runner.invoke(app, ["explain", str(project), "--dry-run"]).output
        block = output.split("--- user ---", 1)[1]
        # `## Project` başlığı proje kökünü basar ve `tmp_path` dizin adına
        # **test adını** koyar. Üstelik dar terminalde yol satır ortasından
        # bölünür, yani yolu metinle maskelemek de yetmez. Ölçüm bölümünden
        # itibaren bakmak ikisini birden çözer.
        return block.split("## Class measurements", 1)[1]

    def test_the_prompt_carries_measurements(self, project):
        assert "LCOM4=2" in self.user_block(project)

    def test_the_evidence_thresholds_field_never_reaches_it(self, project):
        assert "thresholds" not in self.user_block(project)

    def test_no_default_limit_value_appears(self, project):
        block = self.user_block(project)
        # lcom4 {warn:2, critical:4}, nom {warn:20}, wmc {warn:50}
        for leaked in ("critical", "warn=", "=warn", "limit"):
            assert leaked not in block


class TestEndToEnd:
    def test_it_prints_the_observations(self, project, fake):
        result = runner.invoke(app, ["explain", str(project), "--no-report"])
        assert result.exit_code == 0
        assert "share no attributes" in flat(result.output)

    def test_an_unlinked_observation_is_shown_as_such(self, project, fake):
        output = runner.invoke(app, ["explain", str(project), "--no-report"]).output
        assert "unlinked" in flat(output)
        assert "No metric named here" in flat(output)

    def test_it_says_the_output_is_not_scored(self, project, fake):
        output = runner.invoke(app, ["explain", str(project), "--no-report"]).output
        assert "not scored" in flat(output)

    def test_it_writes_both_report_files(self, project, fake):
        runner.invoke(app, ["explain", str(project)])
        written = sorted(p.name for p in (project / "out").glob("explain-*"))
        assert len(written) == 2
        assert any(name.endswith(".json") for name in written)
        assert any(name.endswith(".md") for name in written)

    def test_the_json_carries_its_own_schema_version(self, project, fake):
        runner.invoke(app, ["explain", str(project)])
        payload = json.loads(
            next((project / "out").glob("explain-*.json")).read_text(encoding="utf-8")
        )
        assert payload["schema_version"] == EXPLAIN_SCHEMA_VERSION
        assert payload["unlinked_count"] == 1
        assert payload["graded_count"] == 0

    def test_the_json_records_which_version_produced_it(self, project, fake):
        # Şema sürümü formatı söyler, araç sürümü metrik kurallarını. İkisi de
        # olmadan eski bir rapor okunabilir ama yorumlanamaz.
        from rlens import __version__

        runner.invoke(app, ["explain", str(project)])
        payload = json.loads(
            next((project / "out").glob("explain-*.json")).read_text(encoding="utf-8")
        )
        assert payload["rlens_version"] == __version__

    def test_an_existing_report_can_be_reused(self, project, fake):
        runner.invoke(app, ["scan", str(project)])
        report = next((project / "out").glob("scan-*.json"))
        result = runner.invoke(
            app, ["explain", str(project), "--report", str(report), "--no-report"]
        )
        assert result.exit_code == 0
        assert "share no attributes" in flat(result.output)


class TestEmptyProject:
    def test_it_says_there_is_nothing_to_read(self, tmp_path, fake):
        (tmp_path / "rlens.yaml").write_text("scan:\n  include: ['.']\n", encoding="utf-8")
        (tmp_path / "mod.py").write_text("def go():\n    return 1\n", encoding="utf-8")
        result = runner.invoke(app, ["explain", str(tmp_path), "--no-report"])
        assert result.exit_code == 0
        assert "nothing to read back" in flat(result.output)
        assert fake.calls == []


class TestUnparseableReply:
    def test_the_raw_text_survives(self, project, monkeypatch):
        monkeypatch.setattr(
            "rlens.cli.get_provider", lambda config: FakeProvider("I cannot help with that.")
        )
        result = runner.invoke(app, ["explain", str(project), "--no-report"])
        assert result.exit_code == 0
        assert "could not be parsed" in flat(result.output)
        assert "I cannot help with that." in flat(result.output)


class TestSingularPlural:
    """'1 observations' iki kez yakalandı; sayaç testi kalıcı."""

    def test_one_finding_is_singular(self, project, monkeypatch):
        reply = json.dumps(
            {
                "summary": "",
                "findings": [
                    {"statement": "One.", "subjects": ["mod:Widget"], "metric_link": ["NOM"]}
                ],
                "not_shown": "",
            }
        )
        monkeypatch.setattr("rlens.cli.get_provider", lambda config: FakeProvider(reply))
        output = runner.invoke(app, ["explain", str(project), "--no-report"]).output
        assert "1 finding" in flat(output)
        assert "1 findings" not in flat(output)


def test_the_markdown_says_it_is_not_a_verdict(project, fake):
    runner.invoke(app, ["explain", str(project)])
    markdown = next((project / "out").glob("explain-*.md")).read_text(encoding="utf-8")
    assert "not a verdict" in flat(markdown)
    assert Path(markdown).name  # dosya boş değil


class TestGradedLanguageSurfaces:
    """Talimat çiğnendiğinde kullanıcı bunu görür."""

    def test_the_terminal_names_the_words(self, project, monkeypatch):
        reply = json.dumps(
            {
                "summary": "",
                "findings": [
                    {
                        "statement": "LCOM4=2 indicates low cohesion.",
                        "subjects": ["mod:Widget"],
                        "metric_link": ["LCOM4"],
                    }
                ],
                "not_shown": "",
            }
        )
        monkeypatch.setattr("rlens.cli.get_provider", lambda config: FakeProvider(reply))
        output = flat(runner.invoke(app, ["explain", str(project), "--no-report"]).output)
        assert "graded language: low" in output
        assert "calibrated for another language" in output

    def test_the_finding_is_not_dropped(self, project, monkeypatch):
        reply = json.dumps(
            {
                "summary": "",
                "findings": [
                    {
                        "statement": "WMC=2 is high.",
                        "subjects": ["mod:Widget"],
                        "metric_link": ["WMC"],
                    }
                ],
                "not_shown": "",
            }
        )
        monkeypatch.setattr("rlens.cli.get_provider", lambda config: FakeProvider(reply))
        runner.invoke(app, ["explain", str(project)])
        payload = json.loads(
            next((project / "out").glob("explain-*.json")).read_text(encoding="utf-8")
        )
        assert payload["graded_count"] == 1
        assert payload["findings"][0]["graded_terms"] == ["high"]
