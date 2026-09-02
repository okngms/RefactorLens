"""Infrastructure katmanı davranış testleri."""

import pytest
from domain.entities import Customer, Order, OrderLine
from infra.email_client import EmailClient
from infra.order_repository import OrderRepository


@pytest.fixture
def order():
    customer = Customer(1, "Ada", "ada@example.com")
    return Order(1, customer, [OrderLine("A", 1, 10.0)])


class TestOrderRepository:
    def test_save_returns_incrementing_ids(self, order):
        repository = OrderRepository()
        assert repository.save(order) == 1
        assert repository.save(order) == 2

    def test_get_returns_saved_order(self, order):
        repository = OrderRepository()
        identifier = repository.save(order)
        assert repository.get(identifier) is order

    def test_get_unknown_returns_none(self):
        assert OrderRepository().get(99) is None

    def test_count_and_all_orders(self, order):
        repository = OrderRepository()
        repository.save(order)
        repository.save(order)
        assert repository.count() == 2
        assert len(repository.all_orders()) == 2


class TestEmailClient:
    def test_send_records_the_message(self):
        client = EmailClient("smtp.local")
        message = client.send("ada@example.com", "Hi")
        assert message["host"] == "smtp.local"
        assert client.outbox() == [message]

    def test_outbox_is_a_copy(self):
        client = EmailClient()
        client.send("a@b.c", "x")
        client.outbox().clear()
        assert len(client.outbox()) == 1
