"""Presentation katmanı — KASITLI İHLAL: LV-LEAK.

`repository()` metodu bir infrastructure tipini public imzasında döndürür.
Bağımlılık yönü doğru (presentation → application) ama alt katmanın tipi
dışarı sızıyor. Bu ihlal yalnızca annotation varsa tespit edilebilir; burada
bilerek vardır.
"""

from __future__ import annotations

from infra.order_repository import OrderRepository
from services.order_service import OrderService


class OrderController:
    def __init__(self, service: OrderService, repository: OrderRepository) -> None:
        self._service = service
        self._repository = repository

    def create(self, customer, lines) -> int:
        return self._service.place(customer, lines)

    def cancel(self, order_id: int) -> bool:
        return self._service.cancel(order_id)

    def repository(self) -> OrderRepository:
        """Sızıntının kendisi: infrastructure tipi public imzada."""
        return self._repository
