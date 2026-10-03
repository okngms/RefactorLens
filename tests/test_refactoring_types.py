"""Refactoring türü tespiti (v2.4 Aşama 4, `docs/02` §5).

Her tür için elle yazılmış bir önce/sonra çifti ve beklenen sınıflandırma.
Altın değer önce yazıldı: hangi değişikliğin hangi tür olduğu koddan değil,
refactoring kataloğunun tanımından (Fowler) geliyor.

Ek: taşınan metodun yerinde delege eden bir sarmalayıcı kaldıysa
`delegates: True` — FINDINGS'teki "kalıntı" gözleminin tespit edilebilir hali.
"""

from __future__ import annotations

from rlens.analysis.refactoring_types import (
    EXTRACT_CLASS,
    EXTRACT_METHOD,
    INLINE,
    MOVE_METHOD,
    RENAME,
    UNKNOWN,
    detect,
)


def kinds(before: str, after: str) -> list[tuple[str, str, str]]:
    return [(d.kind, d.source, d.target) for d in detect({"m.py": before}, {"m.py": after})]


ORDERS = """class Orders:
    def total(self, lines):
        subtotal = 0
        for line in lines:
            subtotal += line.price * line.qty
        tax = subtotal * 0.18
        return subtotal + tax

    def label(self):
        return "orders"
"""


class TestEachKind:
    def test_extract_method(self):
        after = """class Orders:
    def total(self, lines):
        subtotal = self._subtotal(lines)
        tax = subtotal * 0.18
        return subtotal + tax

    def _subtotal(self, lines):
        subtotal = 0
        for line in lines:
            subtotal += line.price * line.qty
        return subtotal

    def label(self):
        return "orders"
"""
        assert kinds(ORDERS, after) == [(EXTRACT_METHOD, "Orders.total", "Orders._subtotal")]

    def test_inline(self):
        before = """class Orders:
    def total(self, lines):
        return self._sum(lines) * 2

    def _sum(self, lines):
        result = 0
        for line in lines:
            result += line
        return result
"""
        after = """class Orders:
    def total(self, lines):
        result = 0
        for line in lines:
            result += line
        return result * 2
"""
        assert kinds(before, after) == [(INLINE, "Orders._sum", "Orders.total")]

    def test_rename(self):
        after = ORDERS.replace("def label(self):", "def name(self):")
        assert kinds(ORDERS, after) == [(RENAME, "Orders.label", "Orders.name")]

    def test_move_method_between_existing_classes(self):
        before = (
            ORDERS
            + """

class Printer:
    def header(self):
        return "header"
"""
        )
        after = """class Orders:
    def total(self, lines):
        subtotal = 0
        for line in lines:
            subtotal += line.price * line.qty
        tax = subtotal * 0.18
        return subtotal + tax


class Printer:
    def header(self):
        return "header"

    def label(self):
        return "orders"
"""
        assert kinds(before, after) == [(MOVE_METHOD, "Orders.label", "Printer.label")]

    def test_extract_class(self):
        before = """class Shop:
    def __init__(self):
        self._audit = []
        self._stock = {}

    def record(self, event):
        self._audit.append(event)

    def trail(self):
        return list(self._audit)

    def add(self, name):
        self._stock[name] = self._stock.get(name, 0) + 1
"""
        after = """class AuditLog:
    def __init__(self):
        self._audit = []

    def record(self, event):
        self._audit.append(event)

    def trail(self):
        return list(self._audit)


class Shop:
    def __init__(self):
        self._stock = {}

    def add(self, name):
        self._stock[name] = self._stock.get(name, 0) + 1
"""
        (detection,) = detect({"m.py": before}, {"m.py": after})
        assert (detection.kind, detection.source, detection.target) == (
            EXTRACT_CLASS,
            "Shop",
            "AuditLog",
        )
        assert detection.details["members"] == ["record", "trail"]
        assert detection.details["delegates"] is False


class TestResidue:
    def test_extract_class_that_leaves_delegating_wrappers(self):
        """Üyeler yeni sınıfa gitti ama eski sınıfta ince sarmalayıcılar kaldı:
        NOM ve LCOM4'ü yerinde tutan tam olarak budur (FINDINGS)."""
        before = """class Shop:
    def record(self, event):
        self._audit.append(event)

    def trail(self):
        return list(self._audit)
"""
        after = """class AuditLog:
    def record(self, event):
        self._audit.append(event)

    def trail(self):
        return list(self._audit)


class Shop:
    def record(self, event):
        return self._log.record(event)

    def trail(self):
        return self._log.trail()
"""
        (detection,) = detect({"m.py": before}, {"m.py": after})
        assert detection.kind == EXTRACT_CLASS
        assert detection.details["delegates"] is True
        assert detection.details["delegating_wrappers"] == ["record", "trail"]

    def test_a_rewritten_member_behind_a_wrapper_still_moved(self):
        """Gerçek koşudan: `discount_for` yeni sınıfta yeniden yazıldı (gövde farklı),
        eski sınıfta ona delege eden sarmalayıcı kaldı. Taşınmış sayılır."""
        before = """class Shop:
    def __init__(self):
        self._discounts = {}

    def discount_for(self, tier):
        if tier in self._discounts:
            return self._discounts[tier]
        return 0.0

    def set_discount(self, tier, rate):
        self._discounts[tier] = rate
"""
        after = """class Pricing:
    def __init__(self):
        self._discounts = {}

    def discount_for(self, tier):
        return self._discounts.get(tier, 0.0)

    def set_discount(self, tier, rate):
        self._discounts[tier] = rate


class Shop:
    def __init__(self):
        self._pricing = Pricing()

    def discount_for(self, tier):
        return self._pricing.discount_for(tier)

    def set_discount(self, tier, rate):
        return self._pricing.set_discount(tier, rate)
"""
        (detection,) = detect({"m.py": before}, {"m.py": after})
        assert detection.kind == EXTRACT_CLASS
        assert detection.details["members"] == ["discount_for", "set_discount"]
        assert detection.details["rewritten"] == ["discount_for"]
        assert detection.details["delegating_wrappers"] == ["discount_for", "set_discount"]


class TestEdges:
    def test_no_change_detects_nothing(self):
        assert detect({"m.py": ORDERS}, {"m.py": ORDERS}) == []

    def test_reformatting_is_not_a_refactoring(self):
        assert detect({"m.py": ORDERS}, {"m.py": ORDERS.replace("    ", "    ", 1) + "\n\n"}) == []

    def test_an_edit_matching_no_rule_is_unknown(self):
        after = ORDERS.replace("subtotal * 0.18", "subtotal * 0.2")
        assert kinds(ORDERS, after) == [(UNKNOWN, "Orders.total", "Orders.total")]

    def test_every_detection_has_a_confidence(self):
        after = ORDERS.replace("def label(self):", "def name(self):")
        (detection,) = detect({"m.py": ORDERS}, {"m.py": after})
        assert 0 < detection.confidence <= 1
        assert detection.to_dict()["confidence"] == detection.confidence

    def test_a_new_file_and_a_syntax_error(self):
        assert detect({}, {"n.py": "def f():\n    return 1\n"}) == []
        assert detect({"m.py": ORDERS}, {"m.py": "def broken(:\n"}) == []
