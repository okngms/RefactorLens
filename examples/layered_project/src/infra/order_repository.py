"""Infrastructure katmanı: kalıcılık."""

from __future__ import annotations

from domain.entities import Order


class OrderRepository:
    def __init__(self) -> None:
        self._rows: dict[int, Order] = {}
        self._next_id = 1

    def save(self, order: Order) -> int:
        identifier = self._next_id
        self._rows[identifier] = order
        self._next_id += 1
        return identifier

    def get(self, order_id: int) -> Order | None:
        return self._rows.get(order_id)

    def all_orders(self) -> list[Order]:
        return [self._rows[key] for key in sorted(self._rows)]

    def count(self) -> int:
        return len(self._rows)
