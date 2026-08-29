"""Küçük yardımcı sınıflar.

Bunlar tek başlarına sorunlu değildir; varlık sebepleri `god.OrderManager`'ın
bunların hepsine birden dokunarak **yüksek DCC** üretmesidir. Yani DCC kokusu
"çok sınıf var" değil, "tek sınıf hepsine bağlı" durumundan doğar.
"""

from __future__ import annotations

from models import Customer, OrderLine


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

    def is_open(self) -> bool:
        return self.status == "open"


class Invoice:
    def __init__(self, order_id: int, amount: float) -> None:
        self.order_id = order_id
        self.amount = amount

    def as_text(self) -> str:
        return f"INV-{self.order_id}: {self.amount:.2f}"


class AuditEntry:
    def __init__(self, message: str, level: str = "info") -> None:
        self.message = message
        self.level = level

    def format(self) -> str:
        return f"[{self.level}] {self.message}"


class EmailNotifier:
    def __init__(self, host: str) -> None:
        self.host = host

    def send(self, address: str, subject: str) -> dict[str, str]:
        # Gerçek ağ çağrısı yok: davranış testleri deterministik kalmalı.
        return {"host": self.host, "to": address, "subject": subject, "status": "queued"}


class ShippingCalculator:
    FLAT_RATE = 4.99

    def cost_for(self, weight: float, express: bool = False) -> float:
        cost = self.FLAT_RATE + weight * 0.5
        if express:
            cost *= 2
        return round(cost, 2)
