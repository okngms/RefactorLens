"""models.py davranış testleri."""

import pytest
from models import Customer, OrderLine, Product


class TestCustomer:
    def test_defaults_to_standard_tier(self):
        customer = Customer(1, "Ada", "ada@example.com")
        assert customer.tier == "standard"
        assert customer.is_premium() is False

    def test_promote_makes_premium(self):
        customer = Customer(1, "Ada", "ada@example.com")
        customer.promote("premium")
        assert customer.is_premium() is True

    def test_rename_changes_label(self):
        customer = Customer(1, "Ada", "ada@example.com")
        customer.rename("Ada L.")
        assert customer.label() == "Ada L. <ada@example.com>"

    def test_notes_are_accumulated_and_immutable_outside(self):
        customer = Customer(1, "Ada", "ada@example.com")
        customer.add_note("called")
        customer.add_note("emailed")
        assert customer.notes() == ("called", "emailed")


class TestProduct:
    def test_price_for_multiplies_quantity(self):
        assert Product("SKU1", "Widget", 10.0, stock=5).price_for(3) == 30.0

    def test_in_stock_boundary(self):
        product = Product("SKU1", "Widget", 10.0, stock=5)
        assert product.in_stock(5) is True
        assert product.in_stock(6) is False

    def test_reserve_reduces_stock(self):
        product = Product("SKU1", "Widget", 10.0, stock=5)
        product.reserve(2)
        assert product.stock == 3

    def test_reserve_beyond_stock_raises(self):
        product = Product("SKU1", "Widget", 10.0, stock=1)
        with pytest.raises(ValueError):
            product.reserve(2)

    def test_restock_increases_stock(self):
        product = Product("SKU1", "Widget", 10.0, stock=1)
        product.restock(4)
        assert product.stock == 5


class TestOrderLine:
    def test_subtotal_delegates_to_product(self):
        line = OrderLine(Product("SKU1", "Widget", 2.5, stock=10), 4)
        assert line.subtotal() == 10.0

    def test_bump_changes_subtotal(self):
        line = OrderLine(Product("SKU1", "Widget", 2.5, stock=10), 4)
        line.bump(2)
        assert line.quantity == 6
        assert line.subtotal() == 15.0

    def test_describe_format(self):
        line = OrderLine(Product("SKU1", "Widget", 2.5, stock=10), 4)
        assert line.describe() == "4 x Widget"
