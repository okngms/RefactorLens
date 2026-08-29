"""services.py davranış testleri."""

from models import Customer, OrderLine, Product
from services import AuditEntry, EmailNotifier, Invoice, Order, ShippingCalculator


def make_order(order_id=1):
    customer = Customer(7, "Ada", "ada@example.com")
    lines = [
        OrderLine(Product("A", "Widget", 10.0, stock=100), 2),
        OrderLine(Product("B", "Gadget", 5.0, stock=100), 3),
    ]
    return Order(order_id, customer, lines)


class TestOrder:
    def test_starts_open(self):
        assert make_order().is_open() is True

    def test_subtotal_sums_lines(self):
        assert make_order().subtotal() == 35.0

    def test_item_count_sums_quantities(self):
        assert make_order().item_count() == 5

    def test_close_changes_status(self):
        order = make_order()
        order.close()
        assert order.status == "closed"
        assert order.is_open() is False

    def test_lines_are_copied_not_aliased(self):
        lines = [OrderLine(Product("A", "Widget", 1.0, stock=1), 1)]
        order = Order(1, Customer(1, "A", "a@b.c"), lines)
        lines.append(OrderLine(Product("B", "X", 1.0, stock=1), 1))
        assert len(order.lines) == 1


def test_invoice_text_format():
    assert Invoice(12, 35.0).as_text() == "INV-12: 35.00"


def test_audit_entry_default_level():
    entry = AuditEntry("saved")
    assert entry.level == "info"
    assert entry.format() == "[info] saved"


def test_audit_entry_custom_level():
    assert AuditEntry("boom", "error").format() == "[error] boom"


def test_email_notifier_returns_queued_payload():
    result = EmailNotifier("smtp.local").send("ada@example.com", "Hi")
    assert result == {
        "host": "smtp.local",
        "to": "ada@example.com",
        "subject": "Hi",
        "status": "queued",
    }


class TestShippingCalculator:
    def test_standard_cost(self):
        assert ShippingCalculator().cost_for(2.0) == 5.99

    def test_express_doubles(self):
        assert ShippingCalculator().cost_for(2.0, express=True) == 11.98

    def test_zero_weight_is_flat_rate(self):
        assert ShippingCalculator().cost_for(0.0) == ShippingCalculator.FLAT_RATE
