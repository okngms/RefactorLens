"""`explain --no-llm`: şablon katmanı (`docs/v2.1-explain.md` Blok 2).

Sabitlenenler:

* Her koku etiketi ve her eşik türü için bir kalıp; tanınmayan etiket için genel
  cümle.
* Çıktı deterministik: aynı rapor, aynı metin.
* Kalibrasyon sıfatı yok (`graded_terms` boş) — sayı tarif edilir,
  derecelendirilmez.
* `null` hiçbir zaman "0" olarak yazılmaz; hesaplanamayanlar nedeniyle listelenir.
* Şablon modülü hiçbir prompt modülüne bağlı değil (eşik sızıntısı tuzağı).

Fikstür değerleri elle hesaplandı (`examples/messy_project`, kendi config'i:
LCOM4 eşiği 2/4).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rlens.cli import app
from rlens.config import load_config
from rlens.explain.explainer import graded_terms
from rlens.explain.template import SMELL_TEMPLATES, translate

REPO_ROOT = Path(__file__).resolve().parent.parent
MESSY = REPO_ROOT / "examples" / "messy_project"
runner = CliRunner()


def flat(text: str) -> str:
    return " ".join(text.split())


@pytest.fixture(scope="module")
def messy():
    from rlens.analysis.scanner import scan_project

    config = load_config(search_from=MESSY)
    return scan_project(MESSY, config).to_dict(), config


def _cls(name, module="m", smells=(), **metrics):
    base = {
        "name": name,
        "module": module,
        "nom": 1,
        "wmc": 1,
        "lcom4": 1,
        "dcc": 0,
        "dam": 0.0,
        "cam": None,
        "cam_skipped_reason": "no_annotated_parameters",
        "layer": None,
        "methods": [],
        "smells": list(smells),
    }
    return base | metrics


def _payload(classes=(), functions=(), module_smells=()):
    return {
        "schema_version": 3,
        "rlens_version": "x",
        "modules": [
            {
                "path": "m.py",
                "module": "m",
                "classes": list(classes),
                "functions": list(functions),
                "instability": None,
                "smells": list(module_smells),
            }
        ],
    }


@pytest.fixture
def config(tmp_path):
    return load_config(search_from=tmp_path)


class TestGoldenMessyProject:
    def test_order_manager_thresholds(self, messy):
        payload, config = messy
        texts = [s.text for s in translate(payload, config).sentences]
        joined = "\n".join(texts)
        assert "god:OrderManager: NOM is 25, at or above the warning threshold (20)" in joined
        assert "god:OrderManager: LCOM4 is 4, at or above the critical threshold (4)" in joined
        assert "god:OrderManager: DCC is 8, at or above the warning threshold (7)" in joined
        # WMC 49 < 50: eşik bulgusu yok.
        assert "god:OrderManager: WMC" not in joined

    def test_feature_envy(self, messy):
        payload, config = messy
        texts = [s.text for s in translate(payload, config).sentences]
        assert (
            "god:OrderManager.mark_paid touches order 3 times and its own class 1 time "
            "(ratio 3, threshold 2)." in " ".join(texts)
        )

    def test_too_many_params(self, messy):
        payload, config = messy
        texts = [s.text for s in translate(payload, config).sentences]
        assert "utils.build_shipping_label takes 7 parameters (threshold 5)." in texts

    def test_deterministic(self, messy):
        payload, config = messy
        first = translate(payload, config)
        second = translate(json.loads(json.dumps(payload)), config)
        assert first == second

    def test_no_graded_terms_anywhere(self, messy):
        payload, config = messy
        reading = translate(payload, config)
        for text in [*reading.summary, *(s.text for s in reading.sentences), *reading.not_computed]:
            assert graded_terms(text) == [], text


class TestSmellTemplates:
    CASES = {
        "god_class": (
            {"nom": 26, "wmc": 56, "lcom4": 5, "thresholds": {"nom": 20, "wmc": 50, "lcom4": 3}},
            "m:C is flagged god_class: NOM 26 (threshold 20), WMC 56 (threshold 50) and "
            "LCOM4 5 (threshold 3) all meet their limits.",
        ),
        "data_class": (
            {
                "nom": 3,
                "wmc": 3,
                "dam": 1.0,
                "accessor_ratio": 1.0,
                "accessors": ["a", "b"],
                "lcom4": 3,
            },
            "m:C is flagged data_class: 3 methods, WMC 3, DAM 1, and 100% of its public "
            "methods are accessors (a, b). An LCOM4 of 3 is expected here: accessors of "
            "different fields share no state.",
        ),
        "long_method": (
            {"cc": 12, "loc": 45, "thresholds": {"cc": 10, "loc": 40}},
            "m:C is flagged long_method: CC 12 (threshold 10) and 45 lines of code (threshold 40).",
        ),
        "layer_misfit": (
            {"layer": "domain", "dcc": 9, "module_has_violation": True, "thresholds": {"dcc": 4}},
            "m:C sits in the domain layer, its module breaks a layer rule, and its DCC is 9 "
            "(threshold for this layer 4).",
        ),
    }

    @pytest.mark.parametrize("label", sorted(CASES))
    def test_each_label(self, label, config):
        evidence, expected = self.CASES[label]
        smell = {"label": label, "target": "m:C", "evidence": evidence, "note": ""}
        reading = translate(_payload([_cls("C", smells=[smell])]), config)
        assert expected in [s.text for s in reading.sentences]

    def test_every_known_label_has_a_template(self):
        from rlens.analysis import smells

        labels = {
            smells.GOD_CLASS,
            smells.DATA_CLASS,
            smells.FEATURE_ENVY,
            smells.LONG_METHOD,
            smells.TOO_MANY_PARAMS,
            smells.LAYER_MISFIT,
        }
        assert labels <= set(SMELL_TEMPLATES)

    def test_unknown_label_gets_a_generic_sentence(self, config):
        smell = {"label": "novel_smell", "target": "m:C", "evidence": {"x": 1}, "note": ""}
        reading = translate(_payload([_cls("C", smells=[smell])]), config)
        assert "m:C is flagged novel_smell." in [s.text for s in reading.sentences]


class TestThresholds:
    def test_entry_point_parameters_are_explained(self, config):
        function = {
            "name": "cmd",
            "lineno": 1,
            "cyclomatic_complexity": 1,
            "loc": 3,
            "param_count": 8,
            "max_nesting": 0,
            "entry_point": "cli",
        }
        reading = translate(_payload(functions=[function]), config)
        text = next(s.text for s in reading.sentences if "PARAMS" in s.text)
        assert text.startswith("m.cmd: PARAMS is 8, at or above the warning threshold (5).")
        assert "cli entry point" in text

    def test_null_metric_never_reads_as_zero(self, config):
        reading = translate(_payload([_cls("C", lcom4=None, dcc=None)]), config)
        assert not any("LCOM4 is" in s.text or "DCC is" in s.text for s in reading.sentences)
        assert any("LCOM4 was not computed for 1 class" in n for n in reading.not_computed)


class TestNotComputed:
    def test_reasons_are_counted(self, config):
        classes = [
            _cls("A", cam_skipped_reason="insufficient_annotations"),
            _cls("B", cam_skipped_reason="no_annotated_parameters"),
            _cls("C", cam_skipped_reason="no_annotated_parameters", dam=None),
        ]
        notes = translate(_payload(classes), config).not_computed
        assert "CAM was not computed for 2 classes (no annotated parameters)." in notes
        assert "CAM was not computed for 1 class (annotation coverage below threshold)." in notes
        assert "DAM was not computed for 1 class (no attributes)." in notes


class TestIsolation:
    """Şablon çıktısı prompt'a hiçbir yoldan bağlanmaz (Blok 2, eşik sızıntısı)."""

    @pytest.mark.parametrize(
        "module", ["src/rlens/explain/prompts.py", "src/rlens/advise/prompts.py"]
    )
    def test_prompt_modules_do_not_import_the_template(self, module):
        tree = ast.parse((REPO_ROOT / module).read_text(encoding="utf-8"))
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert "rlens.explain.template" not in imported


class TestCli:
    def test_no_llm_needs_no_provider(self, tmp_path, monkeypatch):
        def refuse(_config):
            raise AssertionError("--no-llm must not build a provider")

        monkeypatch.setattr("rlens.cli.get_provider", refuse)
        result = runner.invoke(
            app, ["explain", str(MESSY), "--no-llm", "--output-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        assert "LCOM4 is 4, at or above the critical threshold (4)" in flat(result.output)
        written = sorted(p.name for p in tmp_path.glob("explain-template-*"))
        assert len(written) == 2

    def test_no_llm_and_dry_run_conflict(self):
        result = runner.invoke(app, ["explain", str(MESSY), "--no-llm", "--dry-run"])
        assert result.exit_code == 1
        assert "--no-llm" in flat(result.output)

    def test_template_json(self, tmp_path):
        runner.invoke(app, ["explain", str(MESSY), "--no-llm", "--output-dir", str(tmp_path)])
        payload = json.loads(next(tmp_path.glob("explain-template-*.json")).read_text("utf-8"))
        assert payload["mode"] == "template"
        assert payload["sentences"]
        assert {"subject", "kind", "metrics", "text"} <= set(payload["sentences"][0])
