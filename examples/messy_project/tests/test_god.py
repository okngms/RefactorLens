"""OrderManager davranış testleri.

Bu dosya fikstürün **güvenlik ağıdır**. Aşama 3 ve 5'te bir refactoring önerisi
elle uygulandığında ilk çalıştırılacak şey budur: testler kırmızıysa metrik
deltası ne kadar güzel görünürse görünsün vaka "broken" sayılır ve delta
geçersizdir.

Bu yüzden testler `OrderManager`'ın **dış davranışına** bakar, iç yapısına
değil. Sınıf dörde bölünürse bile — ki önerilerin çoğu bunu söyleyecek —
testlerin çoğunun ayakta kalması beklenir.
"""

import pytest
from god import OrderManager
from models import Customer, OrderLine, Product


@pytest.fixture
def customer():
    return Customer(7, "Ada", "ada@example.com", tier="premium")


@pytest.fixture
def lines():
    return [
        OrderLine(Product("A", "Widget", 10.0, stock=100), 2),
        OrderLine(Product("B", "Gadget", 5.0, stock=100), 3),
    ]


@pytest.fixture
def manager():
    return OrderManager()


# --- Bileşen 1: siparişler ---------------------------------------------------


class TestOrders:
    def test_place_order_assigns_incrementing_ids(self, manager, customer, lines):
        first = manager.place_order(customer, lines)
        second = manager.place_order(customer, lines)
        assert (first.order_id, second.order_id) == (1, 2)
        assert manager.order_count() == 2

    def test_place_order_rejects_non_customer(self, manager, lines):
        with pytest.raises(TypeError):
            manager.place_order("Ada", lines)

    def test_place_order_rejects_empty_lines(self, manager, customer):
        with pytest.raises(ValueError):
            manager.place_order(customer, [])

    def test_place_order_rejects_bad_line_type(self, manager, customer):
        with pytest.raises(TypeError):
            manager.place_order(customer, ["not-a-line"])

    def test_get_order_returns_placed_order(self, manager, customer, lines):
        placed = manager.place_order(customer, lines)
        assert manager.get_order(placed.order_id) is placed

    def test_get_order_unknown_id_raises(self, manager):
        with pytest.raises(KeyError):
            manager.get_order(99)

    def test_cancel_order_is_idempotent(self, manager, customer, lines):
        order = manager.place_order(customer, lines)
        assert manager.cancel_order(order.order_id) is True
        assert manager.cancel_order(order.order_id) is False
        assert order.status == "cancelled"

    def test_cancel_unknown_order_returns_false(self, manager):
        assert manager.cancel_order(99) is False

    def test_orders_for_filters_by_customer(self, manager, customer, lines):
        other = Customer(8, "Bob", "bob@example.com")
        manager.place_order(customer, lines)
        manager.place_order(other, lines)
        assert [o.customer.customer_id for o in manager.orders_for(7)] == [7]

    def test_line_count_ignores_zero_quantity_lines(self, manager, customer):
        product = Product("A", "Widget", 10.0, stock=100)
        order = manager.place_order(customer, [OrderLine(product, 2), OrderLine(product, 0)])
        assert manager.line_count(order.order_id) == 1

    def test_mark_paid_returns_invoice_and_sets_status(self, manager, customer, lines):
        order = manager.place_order(customer, lines)
        invoice = manager.mark_paid(order.order_id)
        assert order.status == "paid"
        assert invoice.as_text() == "INV-1: 35.00"

    def test_mark_paid_on_cancelled_order_raises(self, manager, customer, lines):
        order = manager.place_order(customer, lines)
        manager.cancel_order(order.order_id)
        with pytest.raises(ValueError):
            manager.mark_paid(order.order_id)

    def test_unpaid_orders_excludes_paid_and_cancelled(self, manager, customer, lines):
        open_order = manager.place_order(customer, lines)
        paid = manager.place_order(customer, lines)
        cancelled = manager.place_order(customer, lines)
        manager.mark_paid(paid.order_id)
        manager.cancel_order(cancelled.order_id)
        assert manager.unpaid_orders() == [open_order.order_id]


# --- Bileşen 2: fiyatlandırma ------------------------------------------------


class TestPricing:
    def test_discount_defaults_to_zero(self, manager):
        assert manager.discount_for("premium") == 0.0

    def test_set_and_read_discount(self, manager):
        manager.set_discount("premium", 0.1)
        assert manager.discount_for("premium") == 0.1

    @pytest.mark.parametrize("rate", [-0.1, 1.5])
    def test_invalid_discount_rate_raises(self, manager, rate):
        with pytest.raises(ValueError):
            manager.set_discount("premium", rate)

    @pytest.mark.parametrize(
        ("quantity", "expected"),
        [(1, 0.0), (19, 0.0), (20, 0.1), (99, 0.1), (100, 0.2)],
    )
    def test_bulk_discount_tiers(self, manager, quantity, expected):
        assert manager.bulk_discount(quantity) == expected

    def test_bulk_discount_respects_configured_rules(self, manager):
        manager.set_discount("bulk_large", 0.35)
        assert manager.bulk_discount(150) == 0.35

    def test_apply_tax_uses_default_rate(self, manager):
        assert manager.apply_tax(100.0) == 118.0

    def test_set_tax_rate_changes_result(self, manager):
        manager.set_tax_rate(0.0)
        assert manager.apply_tax(100.0) == 100.0

    def test_negative_tax_rate_raises(self, manager):
        with pytest.raises(ValueError):
            manager.set_tax_rate(-0.01)

    def test_total_with_tax_applies_discount_then_tax(self, manager):
        manager.set_discount("premium", 0.1)
        assert manager.total_with_tax(100.0, "premium") == 106.2

    def test_total_with_tax_without_discount(self, manager):
        assert manager.total_with_tax(100.0, "standard") == 118.0

    def test_shipping_for_includes_tax(self, manager):
        assert manager.shipping_for(2.0) == 7.07

    def test_shipping_for_express_is_higher(self, manager):
        assert manager.shipping_for(2.0, express=True) > manager.shipping_for(2.0)


# --- Bileşen 3: denetim günlüğü ----------------------------------------------


class TestAuditLog:
    def test_log_starts_empty(self, manager):
        assert manager.log_size() == 0
        assert manager.last_event() is None

    def test_log_event_appends_formatted_entry(self, manager):
        manager.log_event("order placed")
        assert manager.history() == ["[info] order placed"]

    def test_log_event_custom_level(self, manager):
        manager.log_event("bad input", "error")
        assert manager.last_event() == "[error] bad input"

    def test_log_event_returns_entry(self, manager):
        entry = manager.log_event("x")
        assert entry.message == "x"

    def test_clear_log_returns_removed_count(self, manager):
        manager.log_event("a")
        manager.log_event("b")
        assert manager.clear_log() == 2
        assert manager.log_size() == 0


# --- Bileşen 4: bildirim -----------------------------------------------------


class TestNotifications:
    def test_notify_uses_default_host(self, manager, customer):
        result = manager.notify(customer, "Welcome")
        assert result["host"] == "localhost"
        assert result["to"] == "ada@example.com"

    def test_configure_smtp_changes_host(self, manager, customer):
        manager.configure_smtp("smtp.example.com")
        assert manager.notify(customer, "Hi")["host"] == "smtp.example.com"

    def test_empty_host_raises(self, manager):
        with pytest.raises(ValueError):
            manager.configure_smtp("")

    def test_outbox_accumulates(self, manager, customer):
        manager.notify(customer, "one")
        manager.notify(customer, "two")
        assert manager.sent_count() == 2
        assert [m["subject"] for m in manager.outbox()] == ["one", "two"]

    def test_outbox_is_a_copy(self, manager, customer):
        manager.notify(customer, "one")
        manager.outbox().clear()
        assert manager.sent_count() == 1

    def test_reset_outbox_returns_count(self, manager, customer):
        manager.notify(customer, "one")
        assert manager.reset_outbox() == 1
        assert manager.sent_count() == 0


# --- Bileşenler arası: bağımsızlık ------------------------------------------


def test_components_do_not_interfere(manager, customer, lines):
    """Dört sorumluluğun birbirinden bağımsız olduğunun davranışsal kanıtı.

    Bu test aynı zamanda "sınıfı böl" önerisinin neden güvenli olduğunu gösterir:
    bileşenler zaten birbirini etkilemiyor.
    """
    manager.place_order(customer, lines)
    manager.set_discount("premium", 0.2)
    manager.log_event("noted")
    manager.notify(customer, "Hello")

    assert manager.order_count() == 1
    assert manager.discount_for("premium") == 0.2
    assert manager.log_size() == 1
    assert manager.sent_count() == 1
