"""Testi olmayan bir sınıf: `apply`'ın karakterizasyon kapısının fikstürü.

Bilerek tek sınıfta iki iş var (stok hareketi ve raporlama) ve bilerek hiç
test yok: `rlens apply` burada `tests.command` olmadan, kapı seviye 2 ile
çalışmak zorunda (`docs/02` §3, Aşama 2).
"""


class Stock:
    def __init__(self):
        self._items = {}

    def add(self, name, qty, price):
        if qty <= 0:
            raise ValueError("qty must be positive")
        if price < 0:
            raise ValueError("price cannot be negative")
        have, _ = self._items.get(name, (0, price))
        self._items[name] = (have + qty, price)
        return have + qty

    def remove(self, name, qty):
        if name not in self._items:
            raise KeyError(name)
        have, price = self._items[name]
        if qty > have:
            raise ValueError("not enough stock")
        if qty == have:
            del self._items[name]
            return 0
        self._items[name] = (have - qty, price)
        return have - qty

    def quantity(self, name):
        if name in self._items:
            return self._items[name][0]
        return 0

    def total_value(self):
        total = 0
        for qty, price in self._items.values():
            total += qty * price
        return total

    def low_items(self, limit):
        result = []
        for name, (qty, _) in self._items.items():
            if qty < limit:
                result.append(name)
        return sorted(result)

    def report(self):
        lines = []
        for name in sorted(self._items):
            qty, price = self._items[name]
            if qty == 0:
                continue
            lines.append(f"{name}: {qty} x {price:.2f} = {qty * price:.2f}")
        if not lines:
            return "empty"
        lines.append(f"total: {self.total_value():.2f}")
        return "\n".join(lines)
