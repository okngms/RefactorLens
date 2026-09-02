"""Presentation katmanı ve muğlak modüllerin davranış testleri."""

import pytest
from api.order_controller import OrderController
from api.report_view import ReportView
from domain.entities import Customer, OrderLine
from infra.email_client import EmailClient
from infra.order_repository import OrderRepository
from services.order_service import OrderService
from shared.helpers import normalise, registry_size
from shared.registry import Registry


@pytest.fixture
def repository():
    return OrderRepository()


@pytest.fixture
def controller(repository):
    return OrderController(OrderService(repository, EmailClient()), repository)


class TestOrderController:
    def test_create_delegates_to_the_service(self, controller):
        customer = Customer(1, "Ada", "ada@example.com")
        assert controller.create(customer, [OrderLine("A", 1, 1.0)]) == 1

    def test_cancel_delegates(self, controller):
        customer = Customer(1, "Ada", "ada@example.com")
        identifier = controller.create(customer, [OrderLine("A", 1, 1.0)])
        assert controller.cancel(identifier) is True

    def test_repository_is_exposed(self, controller, repository):
        """Sızıntının davranışsal kanıtı: infrastructure nesnesi dışarı veriliyor."""
        assert controller.repository() is repository


class TestReportView:
    @pytest.fixture
    def view(self, repository):
        return ReportView(repository, EmailClient())

    def test_title_is_padded(self, view):
        assert len(view.title()) == 40

    def test_describe_customer(self, view):
        customer = Customer(3, "Ada", "ada@example.com", tier="premium")
        described = view.describe_customer(customer)
        assert "Ada" in described
        assert "premium" in described

    def test_order_count(self, view):
        assert view.order_count() == 0

    def test_mail_summary(self, view):
        assert view.mail_summary("a@b.c")["subject"] == "0 orders"


class TestSharedModules:
    def test_normalise(self):
        assert normalise("  Key  ") == "key"

    def test_registry_round_trip(self):
        registry = Registry()
        registry.put(" Alpha ", "1")
        assert registry.get("alpha") == "1"

    def test_registry_size(self):
        registry = Registry()
        registry.put("a", "1")
        assert registry_size(registry) == 1

    def test_registry_size_rejects_other_types(self):
        with pytest.raises(TypeError):
            registry_size("not a registry")

    def test_circular_import_works_at_runtime(self):
        """Döngü gerçek bir SCC'dir ama çalışma zamanında sorun çıkarmaz."""
        assert registry_size(Registry()) == 0
