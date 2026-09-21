"""Framework giriş noktaları (sertleştirme Blok 1b, madde 4).

Bir fonksiyonun parametre listesi iki durumda yazarın tasarımı değildir:

* **Framework imzayı dikte eder** — Django sinyal alıcısı, pytest fixture'ı.
* **Parametreler framework'e bildirilen dış arayüzdür** — CLI seçenekleri,
  HTTP yol/sorgu parametreleri. Onları azaltmak arayüzü değiştirmek demektir.

Bu fonksiyonlarda `too_many_params` kokusu üretilmez ve `advise` parametre
eşiğini hedef gerekçesi saymaz. **Metrik değişmez**: 29 parametre 29'dur ve
terminal onu yine eşik rengiyle gösterir.

Yanlış pozitif yanlış negatiften pahalıdır: tanınan her fonksiyon gerçek bir
kokuyu gizleyebilir. Bu yüzden tanıma dar tutulur ve tanınmaması gerekenler de
burada sabittir (Celery görevi, `@classmethod`, belge dekoratörleri).

Korpus ölçümü (`experiments/hardening/entry-points.md`): 5+ parametreli 2238
fonksiyonun 17'si giriş noktası; ama black'in `main`'i gibi tek bir CLI komutu
29 parametre taşıyabilir.
"""

import ast
import textwrap

import pytest

from rlens.analysis.entry_points import entry_point_kind
from rlens.analysis.func_metrics import code_lines, measure_function
from rlens.analysis.model import FunctionReport
from rlens.analysis.smells import TOO_MANY_PARAMS, detect_function_smells
from rlens.config import load_config


def function(decorators: str) -> ast.FunctionDef:
    source = textwrap.dedent(decorators).strip() + "\ndef f(a, b, c, d, e, g):\n    return a\n"
    return ast.parse(source).body[0]


class TestRecognised:
    @pytest.mark.parametrize(
        "decorators",
        [
            "@click.command()",
            "@click.group()",
            '@click.option("--verbose", is_flag=True)',
            '@click.argument("src", nargs=-1)',
            "@click.pass_context",
            "@cli.command()",
            "@app.command()",
            '@app.command("run")',
            "@app.callback()",
            "@manager.command()",
            '@click.command()\n@click.option("--x")\n@click.option("--y")',
        ],
    )
    def test_cli(self, decorators):
        assert entry_point_kind(function(decorators)) == "cli"

    @pytest.mark.parametrize(
        "decorators",
        [
            '@router.get("/items/{item_id}")',
            '@app.post("/", status_code=201)',
            '@router.api_route("/x", methods=["GET"])',
            '@app.websocket("/ws")',
            '@bp.route("/login", methods=["POST"])',
            '@app.route("/")',
            '@router.get(path="/items")',
            '@login_required\n@app.route("/admin")',
        ],
    )
    def test_web_route(self, decorators):
        assert entry_point_kind(function(decorators)) == "web_route"

    @pytest.mark.parametrize(
        "decorators",
        [
            "@receiver(post_save, sender=Location)",
            '@event.listens_for(Engine, "connect")',
        ],
    )
    def test_signal_handler(self, decorators):
        assert entry_point_kind(function(decorators)) == "signal_handler"

    @pytest.mark.parametrize(
        "decorators", ["@pytest.fixture", '@pytest.fixture(scope="module")', "@fixture"]
    )
    def test_fixture(self, decorators):
        assert entry_point_kind(function(decorators)) == "fixture"


class TestNotRecognised:
    @pytest.mark.parametrize(
        "decorators",
        [
            "",
            "@classmethod",
            "@staticmethod",
            "@property",
            "@doc(klass='DataFrame')",
            "@final",
            '@app.task(name="export")',
            "@shared_task",
            "@lru_cache(maxsize=None)",
            '@cache.get("key")',
            "@router.get",
            '@settings.option("value")',
            "@contextmanager",
        ],
    )
    def test_not_an_entry_point(self, decorators):
        """Celery görevinin parametreleri yazarın seçtiği mesaj içeriğidir; koku olabilir."""
        assert entry_point_kind(function(decorators)) is None


def make_report(params: int, entry_point: str | None, cc: int = 1) -> FunctionReport:
    return FunctionReport(
        name="main",
        lineno=1,
        cyclomatic_complexity=cc,
        loc=5,
        param_count=params,
        max_nesting=0,
        entry_point=entry_point,
    )


class TestEffect:
    def test_measure_function_records_the_kind(self):
        source = (
            '@click.command()\n@click.option("--x")\ndef main(x, y, z, a, b, c):\n    return x\n'
        )
        node = ast.parse(source).body[0]
        report = measure_function(node, code_lines=code_lines(source))
        assert report.entry_point == "cli"
        assert report.param_count == 6

    def test_plain_function_has_no_kind(self):
        source = "def main(x):\n    return x\n"
        report = measure_function(ast.parse(source).body[0], code_lines=code_lines(source))
        assert report.entry_point is None

    def test_too_many_params_is_not_emitted_for_entry_points(self, tmp_path):
        config = load_config(search_from=tmp_path)
        smells = detect_function_smells(make_report(31, "cli"), "black", config)
        assert TOO_MANY_PARAMS not in {smell.label for smell in smells}

    def test_too_many_params_is_still_emitted_otherwise(self, tmp_path):
        config = load_config(search_from=tmp_path)
        smells = detect_function_smells(make_report(6, None), "tasks", config)
        labels = {smell.label for smell in smells}
        assert TOO_MANY_PARAMS in labels

    def test_evidence_fields_are_unchanged(self, tmp_path):
        """Kanıt alanları FINDINGS için sabit; giriş noktası kuralı onlara dokunmaz."""
        config = load_config(search_from=tmp_path)
        (smell,) = [
            s
            for s in detect_function_smells(make_report(6, None), "t", config)
            if s.label == TOO_MANY_PARAMS
        ]
        assert set(smell.evidence) == {"params", "thresholds"}

    def test_other_smells_still_apply_to_entry_points(self, tmp_path):
        """Giriş noktası uzun ve dallanmalıysa `long_method` yine verilir."""
        config = load_config(search_from=tmp_path)
        report = make_report(31, "cli", cc=25)
        report.loc = 120
        labels = {smell.label for smell in detect_function_smells(report, "black", config)}
        assert "long_method" in labels
        assert TOO_MANY_PARAMS not in labels


class TestAdviceSelection:
    """Parametre eşiği giriş noktası için hedef gerekçesi değildir."""

    def project(self, *functions: FunctionReport):
        from rlens.analysis.model import ModuleReport, ProjectReport

        return ProjectReport(
            root="/tmp",
            generated_at="2026-09-18T00:00:00+00:00",
            rlens_version="test",
            modules=[ModuleReport(path="cli.py", module="cli", functions=list(functions))],
        )

    def test_entry_point_with_only_params_over_threshold_is_not_a_target(self, tmp_path):
        from rlens.advise.selector import collect_targets

        config = load_config(search_from=tmp_path)
        report = self.project(make_report(11, "cli"))
        assert collect_targets(report, config) == []

    def test_entry_point_over_another_threshold_is_a_target_without_the_params_flag(self, tmp_path):
        from rlens.advise.selector import collect_targets

        config = load_config(search_from=tmp_path)
        report = self.project(make_report(11, "cli", cc=15))
        (target,) = collect_targets(report, config)
        assert "cyclomatic_complexity" in target.threshold_flags
        assert "param_count" not in target.threshold_flags

    def test_explicit_target_also_drops_the_params_flag(self, tmp_path):
        from rlens.advise.selector import target_for

        config = load_config(search_from=tmp_path)
        report = self.project(make_report(11, "cli"))
        target = target_for(report, config, "cli:main")
        assert target is not None
        assert "param_count" not in target.threshold_flags

    def test_plain_function_keeps_the_params_flag(self, tmp_path):
        from rlens.advise.selector import collect_targets

        config = load_config(search_from=tmp_path)
        (target,) = collect_targets(self.project(make_report(11, None)), config)
        assert "param_count" in target.threshold_flags


class TestTerminal:
    def test_metric_flag_is_kept_and_the_row_says_why(self, tmp_path):
        """Terminal metriği gizlemez; satır giriş noktası olduğunu söyler."""
        from rlens.report.terminal import function_violations

        config = load_config(search_from=tmp_path)
        assert "param_count" in function_violations(make_report(11, "cli"), config)

    def test_function_table_marks_entry_points(self, tmp_path):
        from rich.console import Console

        from rlens.analysis.model import ModuleReport, ProjectReport
        from rlens.report.terminal import render_report

        config = load_config(search_from=tmp_path)
        report = ProjectReport(
            root="/tmp",
            generated_at="2026-09-18T00:00:00+00:00",
            rlens_version="test",
            modules=[ModuleReport(path="cli.py", module="cli", functions=[make_report(11, "cli")])],
        )
        console = Console(record=True, width=160)
        render_report(report, config, console)
        assert "cli.main [cli]" in console.export_text()
