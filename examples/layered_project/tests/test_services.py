"""Application katmanı davranış testleri.

`OrderService` bilerek bir god class'tır; bu testler onu bölmeye çalışan
önerilerin davranışı bozup bozmadığını yakalayacak ağdır.
"""

import pytest
from domain.entities import Customer, OrderLine
from domain.policies import DiscountPolicy
from infra.email_client import EmailClient
from infra.order_repository import OrderRepository
from services.order_service import OrderService
from services.pricing_service import PricingService


@pytest.fixture
def repository():
    return OrderRepository()


@pytest.fixture
def service(repository):
    return OrderService(repository, EmailClient())


@pytest.fixture
def customer():
    return Customer(7, "Ada", "ada@example.com", tier="premium")


@pytest.fixture
def lines():
    return [OrderLine("A", 2, 10.0), OrderLine("B", 3, 5.0)]


class TestOrderLifecycle:
    def test_place_returns_an_identifier(self, service, customer, lines):
        assert service.place(customer, lines) == 1

    def test_place_rejects_non_customer(self, service, lines):
        with pytest.raises(TypeError):
            service.place("Ada", lines)

    def test_place_rejects_empty_lines(self, service, customer):
        with pytest.raises(ValueError):
            service.place(customer, [])

    def test_place_rejects_bad_line_type(self, service, customer):
        with pytest.raises(TypeError):
            service.place(customer, ["not-a-line"])

    def test_fetch_returns_the_order(self, service, customer, lines):
        identifier = service.place(customer, lines)
        assert service.fetch(identifier).customer is customer

    def test_fetch_unknown_raises(self, service):
        with pytest.raises(KeyError):
            service.fetch(99)

    def test_cancel_is_idempotent(self, service, customer, lines):
        identifier = service.place(customer, lines)
        assert service.cancel(identifier) is True
        assert service.cancel(identifier) is False

    def test_cancel_unknown_returns_false(self, service):
        assert service.cancel(99) is False

    def test_close_sets_status(self, service, customer, lines):
        identifier = service.place(customer, lines)
        assert service.close(identifier) == "closed"

    def test_close_cancelled_raises(self, service, customer, lines):
        identifier = service.place(customer, lines)
        service.cancel(identifier)
        with pytest.raises(ValueError):
            service.close(identifier)

    def test_order_count(self, service, customer, lines):
        service.place(customer, lines)
        service.place(customer, lines)
        assert service.order_count() == 2

    def test_orders_for_filters_by_customer(self, service, customer, lines):
        other = Customer(8, "Bob", "bob@example.com")
        service.place(customer, lines)
        service.place(other, lines)
        assert len(service.orders_for(7)) == 1

    def test_open_orders_excludes_cancelled(self, service, customer, lines):
        first = service.place(customer, lines)
        service.place(customer, lines)
        service.cancel(first)
        assert len(service.open_orders()) == 1

    def test_line_count_ignores_empty_lines(self, service, customer):
        identifier = service.place(customer, [OrderLine("A", 2, 1.0), OrderLine("B", 0, 1.0)])
        assert service.line_count(identifier) == 1


class TestPricing:
    def test_discount_defaults_to_zero(self, service):
        assert service.discount_for("premium") == 0.0

    def test_set_and_read_discount(self, service):
        service.set_discount("premium", 0.1)
        assert service.discount_for("premium") == 0.1

    @pytest.mark.parametrize("rate", [-0.1, 1.5])
    def test_invalid_discount_raises(self, service, rate):
        with pytest.raises(ValueError):
            service.set_discount("premium", rate)

    @pytest.mark.parametrize(
        ("quantity", "expected"), [(1, 0.0), (20, 0.1), (100, 0.2)]
    )
    def test_bulk_discount_tiers(self, service, quantity, expected):
        assert service.bulk_discount(quantity) == expected

    def test_apply_tax(self, service):
        assert service.apply_tax(100.0) == 118.0

    def test_set_tax_rate(self, service):
        service.set_tax_rate(0.0)
        assert service.apply_tax(100.0) == 100.0

    def test_negative_tax_rate_raises(self, service):
        with pytest.raises(ValueError):
            service.set_tax_rate(-0.01)

    def test_total_applies_discount_then_tax(self, service):
        service.set_discount("premium", 0.1)
        assert service.total_for(100.0, "premium") == 106.2

    def test_policy_rate(self, service, repository):
        assert service.policy_rate(DiscountPolicy(repository), "premium") == 0.1

    def test_policy_rate_rejects_wrong_type(self, service):
        with pytest.raises(TypeError):
            service.policy_rate("policy", "premium")


class TestAudit:
    def test_log_starts_empty(self, service):
        assert service.audit_size() == 0
        assert service.last_entry() is None

    def test_log_appends(self, service):
        service.log("placed")
        assert service.history() == ["[info] placed"]

    def test_log_custom_level(self, service):
        assert service.log("boom", "error") == "[error] boom"

    def test_clear_returns_count(self, service):
        service.log("a")
        service.log("b")
        assert service.clear_audit() == 2
        assert service.audit_size() == 0


class TestNotifications:
    def test_notify_uses_customer_email(self, service, customer):
        assert service.notify(customer, "Welcome")["to"] == "ada@example.com"

    def test_sent_count_increments(self, service, customer):
        service.notify(customer, "a")
        service.notify(customer, "b")
        assert service.sent_count() == 2

    def test_reset_returns_previous(self, service, customer):
        service.notify(customer, "a")
        assert service.reset_sent() == 1
        assert service.sent_count() == 0


class TestPricingService:
    def test_net_applies_discount(self, repository):
        pricing = PricingService(DiscountPolicy(repository))
        assert pricing.net(100.0, "premium") == 90.0

    def test_gross_adds_tax(self, repository):
        pricing = PricingService(DiscountPolicy(repository))
        assert pricing.gross(100.0, "premium") == 106.2


class TestAggregates:
    """Sonradan eklenen toplulaştırma metotlarının davranışı."""

    def test_revenue_excludes_cancelled(self, service, customer, lines):
        service.place(customer, lines)
        cancelled = service.place(customer, lines)
        service.cancel(cancelled)
        assert service.revenue() == 35.0

    def test_revenue_is_zero_when_empty(self, service):
        assert service.revenue() == 0.0

    def test_tier_summary_counts_by_tier(self, service, customer, lines):
        other = Customer(8, "Bob", "bob@example.com")
        service.place(customer, lines)
        service.place(customer, lines)
        service.place(other, lines)
        assert service.tier_summary() == {"premium": 2, "standard": 1}

    def test_place_rejects_negative_quantity(self, service, customer):
        with pytest.raises(ValueError):
            service.place(customer, [OrderLine("A", -1, 1.0)])

    def test_place_rejects_negative_price(self, service, customer):
        with pytest.raises(ValueError):
            service.place(customer, [OrderLine("A", 1, -1.0)])

    def test_is_priced_requires_a_configured_discount(self, service):
        assert service.is_priced("premium") is False
        service.set_discount("premium", 0.1)
        assert service.is_priced("premium") is True
