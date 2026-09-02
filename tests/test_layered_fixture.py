"""Katmanlı fikstürün altın değerleri.

`examples/layered_project/ARCH_SMELLS.md` bir sözleşmedir; bu dosya onu
uygular. v2'nin katman ve koku özellikleri henüz yazılmadı, ama fikstürün
**metrik profili** şimdiden sabitlenmeli: kokular o profile göre tanımlanacak
ve fikstür sessizce kayarsa kural testleri nedeni anlaşılmadan kırılır.
"""

from pathlib import Path

import pytest

from rlens.analysis.scanner import scan_project
from rlens.config import load_config

FIXTURE = Path(__file__).resolve().parent.parent / "examples" / "layered_project"


@pytest.fixture(scope="module")
def report():
    return scan_project(FIXTURE, load_config(search_from=FIXTURE))


@pytest.fixture(scope="module")
def classes(report):
    return {cls.name: cls for cls in report.iter_classes()}


def test_every_layer_is_scanned(report):
    modules = {m.module for m in report.modules}
    for expected in (
        "src.api.order_controller",
        "src.services.order_service",
        "src.domain.entities",
        "src.infra.order_repository",
        "src.shared.registry",
    ):
        assert expected in modules


def test_tests_directory_is_excluded(report):
    assert all("tests" not in m.path for m in report.modules)


def test_nothing_is_skipped(report):
    assert report.skipped_files == []


class TestGodClass:
    """ARCH_SMELLS.md: NOM 26, WMC 56, LCOM4 5."""

    def test_measurements(self, classes):
        service = classes["OrderService"]
        assert (service.nom, service.wmc, service.lcom4) == (26, 56, 5)

    def test_god_class_rule_fires(self, classes):
        service = classes["OrderService"]
        assert service.nom >= 20 and service.wmc >= 50 and service.lcom4 >= 3

    def test_wmc_margin_is_documented(self, classes):
        """Eşiğe yakınlık ARCH_SMELLS.md'de uyarı olarak yazılı."""
        assert classes["OrderService"].wmc - 50 == 6


class TestDataClass:
    """v1'de belgelenen LCOM4 yanlış pozitifinin birebir kopyası."""

    def test_customer_looks_uncohesive_by_lcom4(self, classes):
        assert classes["Customer"].lcom4 == 4

    def test_but_matches_the_data_class_shape(self, classes):
        customer = classes["Customer"]
        assert customer.nom <= 5
        assert customer.wmc <= customer.nom + 2
        assert customer.dam >= 0.5

    def test_accessor_ratio(self, classes):
        """5 metodun 4'ü tek satırlık erişimci."""
        customer = classes["Customer"]
        assert len(customer.methods) == 5
        accessors = [m for m in customer.methods if m.cyclomatic_complexity == 1 and m.loc == 2]
        assert len(accessors) / len(customer.methods) >= 0.7


class TestCleanClasses:
    """Metrikleri kötü olmayan sınıflar koku etiketlerini tetiklememeli."""

    @pytest.mark.parametrize(
        "name", ["PricingService", "EmailClient", "OrderRepository", "Registry"]
    )
    def test_small_classes_stay_small(self, classes, name):
        cls = classes[name]
        assert cls.nom <= 5
        assert cls.wmc <= 10

    def test_pricing_service_is_cohesive(self, classes):
        assert classes["PricingService"].lcom4 == 1


class TestArchitectureIsSeparableFromMetrics:
    """Fikstürün varlık sebebi: kötü metrik ≠ mimari ihlal."""

    def test_god_class_has_legal_imports(self, report):
        """OrderService bir god class'tır ama application katmanı kurallarına uyar."""
        service_module = next(
            m for m in report.modules if m.module == "src.services.order_service"
        )
        source = (FIXTURE / service_module.path).read_text(encoding="utf-8")
        assert "from domain." in source

    def test_domain_policy_violates_direction(self):
        """LV-DIR: domain infrastructure'a bağımlı — metrikleri temiz olmasına rağmen."""
        source = (FIXTURE / "src" / "domain" / "policies.py").read_text(encoding="utf-8")
        assert "from infra.order_repository import" in source

    def test_presentation_skips_application(self):
        """LV-SKIP: report_view application'ı atlayıp infra'ya iniyor."""
        source = (FIXTURE / "src" / "api" / "report_view.py").read_text(encoding="utf-8")
        assert "from infra." in source
        assert "from services." not in source

    def test_controller_leaks_an_infrastructure_type(self):
        """LV-LEAK: annotation olmadan tespit edilemez; burada bilerek var."""
        source = (FIXTURE / "src" / "api" / "order_controller.py").read_text(encoding="utf-8")
        assert "def repository(self) -> OrderRepository:" in source

    def test_shared_modules_form_a_cycle(self):
        helpers = (FIXTURE / "src" / "shared" / "helpers.py").read_text(encoding="utf-8")
        registry = (FIXTURE / "src" / "shared" / "registry.py").read_text(encoding="utf-8")
        assert "import shared.registry" in helpers
        assert "import shared.helpers" in registry
