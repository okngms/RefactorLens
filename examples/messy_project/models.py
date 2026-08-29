"""Temiz taraf: tam annotate edilmiş, kohezyonlu (LCOM4 = 1) sınıflar.

Bu modül bilerek "iyi"dir. İki işi var:
1. CAM'in **hesaplanabildiği** vakayı sağlamak (annotation kapsamı %100).
2. Metriklerin yalnızca kötü kodu değil, iyi kodu da doğru ölçtüğünü kanıtlamak.
   Her sınıfı "sorunlu" işaretleyen bir araç hiçbir şey söylemiyordur.
"""

from __future__ import annotations


class Customer:
    """Kohezyonlu: tüm metotlar aynı attribute kümesine dokunur → LCOM4 = 1."""

    def __init__(self, customer_id: int, name: str, email: str, tier: str = "standard") -> None:
        self.customer_id = customer_id
        self.name = name
        self.email = email
        self.tier = tier
        self._notes: list[str] = []

    def rename(self, name: str) -> None:
        self.name = name

    def promote(self, tier: str) -> None:
        self.tier = tier

    def is_premium(self) -> bool:
        return self.tier == "premium"

    def add_note(self, note: str) -> None:
        self._notes.append(note)

    def notes(self) -> tuple[str, ...]:
        return tuple(self._notes)

    def label(self) -> str:
        return f"{self.name} <{self.email}>"


class Product:
    def __init__(self, sku: str, title: str, unit_price: float, stock: int = 0) -> None:
        self.sku = sku
        self.title = title
        self.unit_price = unit_price
        self.stock = stock

    def in_stock(self, quantity: int) -> bool:
        return self.stock >= quantity

    def reserve(self, quantity: int) -> None:
        if not self.in_stock(quantity):
            raise ValueError(f"{self.sku}: yetersiz stok ({self.stock} < {quantity})")
        self.stock -= quantity

    def restock(self, quantity: int) -> None:
        self.stock += quantity

    def price_for(self, quantity: int) -> float:
        return self.unit_price * quantity


class OrderLine:
    """DCC = 1 (yalnızca Product'a bağımlı) — düşük coupling referans vakası."""

    def __init__(self, product: Product, quantity: int) -> None:
        self.product = product
        self.quantity = quantity

    def subtotal(self) -> float:
        return self.product.price_for(self.quantity)

    def bump(self, extra: int) -> None:
        self.quantity += extra

    def describe(self) -> str:
        return f"{self.quantity} x {self.product.title}"
