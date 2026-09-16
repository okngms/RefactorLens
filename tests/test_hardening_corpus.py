"""Sertleştirme Blok 1b: kalibrasyon korpusu (`experiments/hardening/corpus.py`).

Korpus eşiklerin kaynağı olacak; üç şeyin sessizce bozulmaması gerekir:

* **Doğruluk setiyle tutarlılık.** `projects.txt`'teki 12 proje korpusta
  birebir aynı commit ve kapsamla durmalı; yoksa Blok 1'in doğruluk sayıları
  ile Blok 1b'nin dağılımı farklı kodu anlatır.
* **Config.** `.cache/` bu deponun içinde; config'i yukarı doğru aramak
  RefactorLens'in kendi `rlens.yaml`'ını (`include: ["src/"]`) bulur ve
  taramayı sessizce boşaltır.
* **Ölçülen mantık payı.** İlk tanım veri tablolarını mantık saydı ve
  netbox'ı %48 ölçülmüş gösterdi. Hangi satırın mantık olduğu burada sabittir.
"""

import ast
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from compare_radon import PROJECTS_FILE, Project, load_projects  # noqa: E402
from corpus import (  # noqa: E402
    CORPUS_FILE,
    PROJECT_TYPES,
    accuracy_set_mismatches,
    line_coverage,
    load_corpus,
    project_config,
    skip_category,
)


def tree(source: str) -> ast.Module:
    return ast.parse(textwrap.dedent(source).strip())


class TestCorpusFile:
    def test_corpus_is_balanced_across_types(self):
        corpus = load_corpus(CORPUS_FILE)
        counts = {kind: sum(1 for p in corpus if p.type == kind) for kind in PROJECT_TYPES}
        assert all(count >= 5 for count in counts.values()), counts
        assert len(corpus) == sum(counts.values())

    def test_accuracy_set_is_a_verbatim_subset(self):
        """Blok 1'in 12 projesi korpusta aynı commit, kapsam ve dışlamayla."""
        mismatches = accuracy_set_mismatches(load_corpus(CORPUS_FILE), load_projects(PROJECTS_FILE))
        assert mismatches == []

    def test_mismatch_is_reported(self):
        corpus = load_corpus(CORPUS_FILE)
        drifted = [Project("requests", "psf/requests", "v2.32.3", "f" * 40, "src/requests")]
        missing = [Project("nowhere", "a/b", "v1", "a" * 40, "src")]
        assert accuracy_set_mismatches(corpus, drifted) == ["requests: differs from projects.txt"]
        assert accuracy_set_mismatches(corpus, missing) == ["nowhere: missing from corpus"]

    @pytest.mark.parametrize(
        ("line", "message"),
        [
            ("demo  library  a/b  v1  abc  src", "40-char"),
            ("demo  toolkit  a/b  v1  " + "a" * 40 + "  src", "unknown type"),
            ("demo  library  a/b  v1  " + "a" * 40, "at least 6 columns"),
        ],
    )
    def test_invalid_rows_are_rejected(self, tmp_path, line, message):
        listing = tmp_path / "corpus.txt"
        listing.write_text(line + "\n")
        with pytest.raises(ValueError, match=message):
            load_corpus(listing)

    def test_duplicate_names_are_rejected(self, tmp_path):
        row = "demo  cli  a/b  v1  " + "a" * 40 + "  src\n"
        listing = tmp_path / "corpus.txt"
        listing.write_text(row + row)
        with pytest.raises(ValueError, match="duplicate"):
            load_corpus(listing)


class TestProjectConfig:
    def test_defaults_are_kept_and_extras_appended(self, tmp_path):
        project = Project("mealie", "a/b", "v1", "a" * 40, "mealie", ("alembic",))
        config = project_config(project, tmp_path)
        excludes = list(config.scan.exclude)
        assert "tests/" in excludes
        assert "migrations/" in excludes
        assert excludes[-1] == "alembic/"
        assert list(config.scan.include) == ["."]

    def test_enclosing_repository_config_is_not_used(self, tmp_path):
        """Üst dizindeki `rlens.yaml` (bu deponunki gibi) taramayı etkilememeli."""
        (tmp_path / "rlens.yaml").write_text('scan:\n  include: ["src/"]\n')
        workdir = tmp_path / "nested" / "work"
        workdir.mkdir(parents=True)
        project = Project("demo", "a/b", "v1", "a" * 40, ".")
        assert list(project_config(project, workdir).scan.include) == ["."]


class TestLineCoverage:
    def test_imports_and_module_docstring_are_not_logic(self):
        module = tree(
            '''
            """Module docstring."""
            import os
            from typing import (
                Any,
            )

            def f():
                return 1
            '''
        )
        assert line_coverage(module) == (2, 2)

    def test_literal_data_outside_units_is_not_logic(self):
        """netbox'ın 111 bin satırlık liman kodu tablosu gibi."""
        module = tree(
            """
            CODES = {
                "a": 1,
                "b": 2,
            }
            __all__ = ["f"]

            def f():
                return CODES
            """
        )
        assert line_coverage(module) == (2, 2)

    def test_literal_inside_a_unit_stays_measured(self):
        module = tree(
            """
            def f():
                table = {
                    "a": 1,
                }
                return table
            """
        )
        logic, measured = line_coverage(module)
        assert logic == measured == 5

    def test_module_level_calls_are_unmeasured_logic(self):
        """httpie'nin `parser.add_argument(...)` yığını gibi."""
        module = tree(
            """
            parser = make_parser()
            parser.add_argument(
                "--verbose",
            )
            """
        )
        assert line_coverage(module) == (4, 0)

    def test_script_control_flow_is_unmeasured_logic(self):
        """nanoGPT'nin en üst düzeydeki eğitim döngüsü gibi."""
        module = tree(
            """
            step = 0
            while step < 10:
                if step % 2:
                    step += 1
                step += 1
            """
        )
        logic, measured = line_coverage(module)
        assert measured == 0
        # `step = 0` düz sabit atamadır ve veri sayılır — nanoGPT'nin
        # `batch_size = 12` gibi yapılandırma sabitleriyle aynı kural. Sınır
        # belirsiz ama tutarlı: değeri hesaplanan atama mantıktır, sabit değildir.
        assert logic == 4

    def test_decorators_belong_to_the_unit(self):
        module = tree(
            """
            @app.command(
                name="run",
            )
            def run():
                return 1
            """
        )
        logic, measured = line_coverage(module)
        assert logic == measured == 5

    def test_definitions_under_if_are_unmeasured(self):
        """Raporda olmayan birim burada da ölçülmemiş sayılır (metric-accuracy §1)."""
        module = tree(
            """
            if TYPE_CHECKING:
                def helper():
                    return 1
            """
        )
        logic, measured = line_coverage(module)
        assert measured == 0
        assert logic == 3

    def test_attribute_docstrings_are_not_logic(self):
        module = tree(
            '''
            class Model:
                x: int
                """The x."""

            y = compute()
            """The y."""
            '''
        )
        logic, measured = line_coverage(module)
        assert (logic, measured) == (4, 3)

    def test_empty_module(self):
        assert line_coverage(tree("")) == (0, 0)


def test_skip_category_drops_line_numbers():
    assert skip_category("syntax error (line 12): invalid syntax") == "syntax error"
    assert skip_category("not readable as utf-8") == "not readable as utf-8"
    assert skip_category("unreadable: Permission denied") == "unreadable"
