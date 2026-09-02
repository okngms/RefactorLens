"""Application katmanı — KASITLI KOKU: god_class.

Dört sorumluluğu tek sınıfta toplar (sipariş, fiyatlandırma, denetim, bildirim).
Kural: NOM ≥ 20 ∧ WMC ≥ 50 ∧ LCOM4 ≥ 3.

`messy_project.god.OrderManager`'dan farkı: burada sınıf bir katmana aittir ve
bağımlılıkları katman kurallarına **uygundur** — yalnızca domain'i import eder.
Depo ve bildirici dışarıdan enjekte edilir; application katmanı somut
infrastructure tiplerine bağlanmaz.

Yani metrikler aynı derecede kötüyken mimari ihlal yoktur. v2'nin ayırt etmesi
gereken tam olarak bu: kötü metrik ≠ mimari ihlal.
"""

from __future__ import annotations

from domain.entities import Customer, Order, OrderLine
from domain.policies import DiscountPolicy


class OrderService:
    def __init__(self, repository, notifier) -> None:
        # Bileşen 1 — sipariş yaşam döngüsü
        self._repository = repository
        self._next_order_id = 1
        # Bileşen 2 — fiyatlandırma
        self._tax_rate = 0.18
        self._discounts: dict[str, float] = {}
        # Bileşen 3 — denetim
        self._audit: list[str] = []
        # Bileşen 4 — bildirim
        self._notifier = notifier
        self._sent = 0

    # -- Bileşen 1: sipariş yaşam döngüsü -------------------------------------

    def place(self, customer, lines):
        if not isinstance(customer, Customer):
            raise TypeError("customer must be a Customer")
        if not lines:
            raise ValueError("an order needs at least one line")
        for line in lines:
            if not isinstance(line, OrderLine):
                raise TypeError("lines must contain OrderLine objects")
            if line.quantity < 0:
                raise ValueError("a line quantity cannot be negative")
            if line.unit_price < 0:
                raise ValueError("a unit price cannot be negative")
        order = Order(self._next_order_id, customer, lines)
        self._next_order_id += 1
        return self._repository.save(order)

    def fetch(self, order_id):
        order = self._repository.get(order_id)
        if order is None:
            raise KeyError(order_id)
        return order

    def cancel(self, order_id):
        order = self._repository.get(order_id)
        if order is None:
            return False
        if order.status == "cancelled":
            return False
        order.status = "cancelled"
        return True

    def close(self, order_id):
        order = self.fetch(order_id)
        if order.status == "cancelled":
            raise ValueError("a cancelled order cannot be closed")
        order.close()
        return order.status

    def order_count(self):
        return self._repository.count()

    def orders_for(self, customer_id):
        found = []
        for order in self._repository.all_orders():
            if order.customer.customer_id() == customer_id:
                found.append(order)
        return found

    def open_orders(self):
        return [o for o in self._repository.all_orders() if o.status == "open"]

    def line_count(self, order_id):
        order = self.fetch(order_id)
        total = 0
        for line in order.lines:
            if line.quantity > 0:
                total += 1
        return total

    def revenue(self):
        total = 0.0
        for order in self._repository.all_orders():
            if order.status != "cancelled":
                total += order.subtotal()
        return round(total, 2)

    def tier_summary(self):
        counts = {}
        for order in self._repository.all_orders():
            tier = order.customer.tier()
            if tier in counts:
                counts[tier] += 1
            else:
                counts[tier] = 1
        return counts

    # -- Bileşen 2: fiyatlandırma ---------------------------------------------

    def set_discount(self, tier, rate):
        if rate < 0 or rate > 1:
            raise ValueError("a discount rate must be between 0 and 1")
        self._discounts[tier] = rate

    def discount_for(self, tier):
        if tier in self._discounts:
            return self._discounts[tier]
        return 0.0

    def bulk_discount(self, quantity):
        if quantity >= 100:
            return self._discounts.get("bulk_large", 0.2)
        if quantity >= 20:
            return self._discounts.get("bulk_small", 0.1)
        return 0.0

    def set_tax_rate(self, rate):
        if rate < 0:
            raise ValueError("a tax rate cannot be negative")
        self._tax_rate = rate

    def apply_tax(self, amount):
        return round(amount * (1 + self._tax_rate), 2)

    def total_for(self, subtotal, tier):
        discounted = subtotal * (1 - self.discount_for(tier))
        return self.apply_tax(discounted)

    def policy_rate(self, policy, tier):
        if not isinstance(policy, DiscountPolicy):
            raise TypeError("policy must be a DiscountPolicy")
        return policy.rate_for(tier)

    def is_priced(self, tier):
        return tier in self._discounts and self._discounts[tier] > 0 and self._tax_rate > 0

    # -- Bileşen 3: denetim ---------------------------------------------------

    def log(self, message, level="info"):
        entry = f"[{level}] {message}"
        self._audit.append(entry)
        return entry

    def history(self):
        return list(self._audit)

    def last_entry(self):
        if not self._audit:
            return None
        return self._audit[-1]

    def audit_size(self):
        return len(self._audit)

    def clear_audit(self):
        removed = len(self._audit)
        self._audit = []
        return removed

    # -- Bileşen 4: bildirim --------------------------------------------------

    def notify(self, customer, subject):
        result = self._notifier.send(customer.email(), subject)
        self._sent += 1
        return result

    def sent_count(self):
        return self._sent

    def reset_sent(self):
        previous = self._sent
        self._sent = 0
        return previous
