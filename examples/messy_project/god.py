"""Fikstürün kalbi: dört sorumluluğu tek sınıfta toplayan god class.

Kasıtlı kokular (kesin değerler Faz 1'de elle doğrulanır, bkz. SMELLS.md):

* **LCOM4 = 4.** Metot–attribute grafiği dört ayrık bileşene ayrılır:
  siparişler (`_orders`, `_next_id`), fiyatlandırma (`_tax_rate`,
  `_discount_rules`), denetim günlüğü (`_log`), bildirim (`_smtp_host`,
  `_sent`). Bileşenler birbirini **hiç çağırmaz** — sınıfın dört ayrı sınıf
  olması gerektiğinin ölçülebilir kanıtı budur.
* **Yüksek DCC.** Sekiz proje-içi sınıfa dokunur.
* **Yüksek NOM/WMC.** 25 metot.
* **CAM = null.** Dosyada tek bir parametre annotation'ı yoktur. Bu bilinçli:
  gerçek Python projelerinin çoğu böyledir ve aracın bu durumda sayı
  uydurmadığını kanıtlamamız gerekir.

Kod ÇALIŞIR ve `tests/` altındaki davranış testleriyle korunur. Bir öneri
uygulandığında testler kırmızıya dönerse, metrikler ne kadar iyileşirse
iyileşsin o vaka "broken" sayılır.
"""

from models import Customer, OrderLine, Product
from services import AuditEntry, EmailNotifier, Invoice, Order, ShippingCalculator


class OrderManager:
    def __init__(self):
        # Bileşen 1 — siparişler
        self._orders = {}
        self._next_id = 1
        # Bileşen 2 — fiyatlandırma
        self._tax_rate = 0.18
        self._discount_rules = {}
        # Bileşen 3 — denetim günlüğü
        self._log = []
        # Bileşen 4 — bildirim
        self._smtp_host = "localhost"
        self._sent = []

    # -- Bileşen 1: siparişler ------------------------------------------------

    def place_order(self, customer, lines):
        if not isinstance(customer, Customer):
            raise TypeError("customer bir Customer olmali")
        if not lines:
            raise ValueError("bos siparis olusturulamaz")
        for line in lines:
            if not isinstance(line, OrderLine):
                raise TypeError("lines yalnizca OrderLine icermeli")
            if not isinstance(line.product, Product):
                raise TypeError("OrderLine.product bir Product olmali")
        order = Order(self._next_id, customer, lines)
        self._orders[self._next_id] = order
        self._next_id += 1
        return order

    def get_order(self, order_id):
        if order_id not in self._orders:
            raise KeyError(order_id)
        return self._orders[order_id]

    def cancel_order(self, order_id):
        order = self._orders.get(order_id)
        if order is None:
            return False
        if order.status == "cancelled":
            return False
        order.status = "cancelled"
        return True

    def order_count(self):
        return len(self._orders)

    def orders_for(self, customer_id):
        found = []
        for order in self._orders.values():
            if order.customer.customer_id == customer_id:
                found.append(order)
        return found

    def line_count(self, order_id):
        order = self.get_order(order_id)
        total = 0
        for line in order.lines:
            if line.quantity > 0:
                total += 1
        return total

    def mark_paid(self, order_id):
        order = self.get_order(order_id)
        if order.status == "cancelled":
            raise ValueError("iptal edilmis siparis odenemez")
        order.status = "paid"
        return Invoice(order_id, order.subtotal())

    def unpaid_orders(self):
        result = []
        for order_id in sorted(self._orders):
            order = self._orders[order_id]
            if order.status not in ("paid", "cancelled"):
                result.append(order_id)
        return result

    # -- Bileşen 2: fiyatlandırma ---------------------------------------------

    def set_discount(self, tier, rate):
        if rate < 0 or rate > 1:
            raise ValueError("indirim orani 0-1 arasinda olmali")
        self._discount_rules[tier] = rate

    def discount_for(self, tier):
        if tier in self._discount_rules:
            return self._discount_rules[tier]
        return 0.0

    def bulk_discount(self, quantity):
        if quantity >= 100:
            return self._discount_rules.get("bulk_large", 0.2)
        if quantity >= 20:
            return self._discount_rules.get("bulk_small", 0.1)
        return 0.0

    def set_tax_rate(self, rate):
        if rate < 0:
            raise ValueError("vergi orani negatif olamaz")
        self._tax_rate = rate

    def apply_tax(self, amount):
        return round(amount * (1 + self._tax_rate), 2)

    def total_with_tax(self, subtotal, tier):
        discount = self.discount_for(tier)
        discounted = subtotal * (1 - discount)
        return self.apply_tax(discounted)

    def shipping_for(self, weight, express=False):
        calculator = ShippingCalculator()
        base = calculator.cost_for(weight, express)
        return round(base * (1 + self._tax_rate), 2)

    # -- Bileşen 3: denetim günlüğü -------------------------------------------

    def log_event(self, message, level="info"):
        entry = AuditEntry(message, level)
        self._log.append(entry)
        return entry

    def history(self):
        return [entry.format() for entry in self._log]

    def last_event(self):
        if not self._log:
            return None
        return self._log[-1].format()

    def log_size(self):
        return len(self._log)

    def clear_log(self):
        removed = len(self._log)
        self._log = []
        return removed

    # -- Bileşen 4: bildirim --------------------------------------------------

    def configure_smtp(self, host):
        if not host:
            raise ValueError("host bos olamaz")
        self._smtp_host = host

    def notify(self, customer, subject):
        notifier = EmailNotifier(self._smtp_host)
        result = notifier.send(customer.email, subject)
        self._sent.append(result)
        return result

    def sent_count(self):
        return len(self._sent)

    def outbox(self):
        return list(self._sent)

    def reset_outbox(self):
        count = len(self._sent)
        self._sent = []
        return count
