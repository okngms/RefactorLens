"""Domain katmanı: saf varlıklar. Hiçbir dış katmana bağımlı değildir."""

from __future__ import annotations


class Customer:
    """Kasıtlı `data_class`: neredeyse tamamen erişimci.

    v1 bulgusunda LCOM4'ün veri sınıflarını cezalandırdığı belgelenmişti
    (`Customer` için 3 çıkıyordu). Bu sınıf, koku etiketinin o yanlış
    pozitifi nötrleyip nötrlemediğini ölçer.
    """

    def __init__(self, customer_id: int, name: str, email: str, tier: str = "standard") -> None:
        self._customer_id = customer_id
        self._name = name
        self._email = email
        self._tier = tier

    def customer_id(self) -> int:
        return self._customer_id

    def name(self) -> str:
        return self._name

    def email(self) -> str:
        return self._email

    def tier(self) -> str:
        return self._tier

    def is_premium(self) -> bool:
        return self._tier == "premium"


class OrderLine:
    def __init__(self, sku: str, quantity: int, unit_price: float) -> None:
        self.sku = sku
        self.quantity = quantity
        self.unit_price = unit_price

    def subtotal(self) -> float:
        return self.quantity * self.unit_price


class Order:
    def __init__(self, order_id: int, customer: Customer, lines: list[OrderLine]) -> None:
        self.order_id = order_id
        self.customer = customer
        self.lines = list(lines)
        self.status = "open"

    def subtotal(self) -> float:
        return sum(line.subtotal() for line in self.lines)

    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines)

    def close(self) -> None:
        self.status = "closed"
