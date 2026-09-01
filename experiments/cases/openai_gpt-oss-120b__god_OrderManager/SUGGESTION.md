# Case: god:OrderManager

- **Model:** `openai/gpt-oss-120b`
- **Repetition:** 1

> Apply **one** suggestion, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The OrderManager class aggregates four unrelated responsibilities (order storage, pricing, audit logging, and notification). This is reflected by a critical LCOM4 of 4, a high NOM (25) and WMC (49), indicating low cohesion and complex methods. The DCC of 8 shows it already depends on many internal types, and extracting responsibilities will likely increase that count while improving cohesion.

## 1. Extract the four components into dedicated classes

- **Evidence:** LCOM4, NOM, WMC, DCC
- **Predicted effect:** LCOM4 down, NOM down, WMC down, DCC up

Create four new classes:

```python
class OrderRepository:
    def __init__(self):
        self._orders = {}
        self._next_id = 1
    # move place_order, get_order, cancel_order, order_count, orders_for, line_count, mark_paid, unpaid_orders here
```

```python
class PricingEngine:
    def __init__(self, tax_rate=0.18, discount_rules=None):
        self._tax_rate = tax_rate
        self._discount_rules = discount_rules or {}
    # move set_discount, discount_for, bulk_discount, set_tax_rate, apply_tax, total_with_tax, shipping_for here
```

```python
class AuditLog:
    def __init__(self):
        self._log = []
    # move log_event, history, last_event, log_size, clear_log here
```

```python
class NotificationService:
    def __init__(self, smtp_host="localhost"):
        self._smtp_host = smtp_host
        self._sent = []
    # move configure_smtp, notify, sent_count, outbox, reset_outbox here
```

Then refactor OrderManager to become a thin façade that composes these services:

```python
class OrderManager:
    def __init__(self):
        self.repo = OrderRepository()
        self.pricing = PricingEngine()
        self.audit = AuditLog()
        self.notifier = NotificationService()
    # each original method delegates to the appropriate component, e.g.
    def place_order(self, customer, lines):
        return self.repo.place_order(customer, lines)
    # similarly for the other methods
```

Update imports and adjust any external code that instantiated OrderManager directly to use the same public API (the façade preserves method signatures).

## Risks

Refactoring may require extensive test updates and careful coordination with any code that directly accesses OrderManager's private attributes. The added indirection could have a minor performance impact, but the gain in cohesion and maintainability usually outweighs it.
