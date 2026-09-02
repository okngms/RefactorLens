"""Domain katmanı — KASITLI İHLAL: LV-DIR.

Domain, infrastructure'a bağımlı olmamalıdır. Bu modül bilerek tersini yapar:
bir domain kuralı doğrudan repository'ye erişir. Katman kuralının en klasik
ihlali budur ve fikstürün onu yakalayıp yakalamadığımızı ölçmesi gerekir.
"""

from __future__ import annotations

from infra.order_repository import OrderRepository


class DiscountPolicy:
    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository
        self._rates = {"premium": 0.1, "standard": 0.0}

    def rate_for(self, tier: str) -> float:
        return self._rates.get(tier, 0.0)

    def loyalty_bonus(self, customer_id: int) -> float:
        """Repository'ye doğrudan erişim — ihlalin somut hali."""
        orders = [
            order
            for order in self._repository.all_orders()
            if order.customer.customer_id() == customer_id
        ]
        return 0.05 if len(orders) >= 3 else 0.0
