"""Domain katmanı davranış testleri."""

import pytest
from domain.entities import Customer, Order, OrderLine
from domain.policies import DiscountPolicy
from infra.order_repository import OrderRepository


@pytest.fixture
def customer():
    return Customer(1, "Ada", "ada@example.com", tier="premium")


@pytest.fixture
def lines():
    return [OrderLine("A", 2, 10.0), OrderLine("B", 3, 5.0)]


class TestCustomer:
    def test_accessors(self, customer):
        assert customer.customer_id() == 1
        assert customer.name() == "Ada"
        assert customer.email() == "ada@example.com"
        assert customer.tier() == "premium"

    def test_is_premium(self, customer):
        assert customer.is_premium() is True

    def test_standard_customer_is_not_premium(self):
        assert Customer(2, "Bob", "bob@example.com").is_premium() is False


class TestOrder:
    def test_subtotal(self, customer, lines):
        assert Order(1, customer, lines).subtotal() == 35.0

    def test_item_count(self, customer, lines):
        assert Order(1, customer, lines).item_count() == 5

    def test_starts_open_and_closes(self, customer, lines):
        order = Order(1, customer, lines)
        assert order.status == "open"
        order.close()
        assert order.status == "closed"

    def test_lines_are_copied(self, customer):
        lines = [OrderLine("A", 1, 1.0)]
        order = Order(1, customer, lines)
        lines.append(OrderLine("B", 1, 1.0))
        assert len(order.lines) == 1


def test_order_line_subtotal():
    assert OrderLine("A", 4, 2.5).subtotal() == 10.0


class TestDiscountPolicy:
    def test_known_tier(self):
        assert DiscountPolicy(OrderRepository()).rate_for("premium") == 0.1

    def test_unknown_tier_is_zero(self):
        assert DiscountPolicy(OrderRepository()).rate_for("gold") == 0.0

    def test_loyalty_bonus_requires_three_orders(self, customer, lines):
        repository = OrderRepository()
        policy = DiscountPolicy(repository)
        assert policy.loyalty_bonus(1) == 0.0
        for index in range(3):
            repository.save(Order(index, customer, lines))
        assert policy.loyalty_bonus(1) == 0.05
