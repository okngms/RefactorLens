# Case: god:OrderManager

- **Model:** `openai/gpt-oss-20b`
- **Repetition:** 1

> Apply **one** suggestion, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The class has a high number of methods (NOM=25) and a very high cyclomatic complexity (WMC=49), indicating that it is doing too much. The cohesion metric LCOM4=4 is critical, meaning the methods are largely unrelated to the attributes they use. The class also depends on eight other internal classes (DCC=8), showing a high coupling. These measurements point to a classic God‑object that should be decomposed into smaller, more focused components.

## 1. Split OrderManager into dedicated services

- **Evidence:** LCOM4, DCC, NOM, WMC
- **Predicted effect:** LCOM4 down, DCC down, NOM down, WMC down

Create four new classes:

```python
class OrderService:
    def __init__(self, repo: OrderRepository, pricing: PricingEngine, notifier: NotificationService, logger: AuditLogger):
        self.repo = repo
        self.pricing = pricing
        self.notifier = notifier
        self.logger = logger

    # move place_order, get_order, cancel_order, order_count, orders_for, line_count, mark_paid, unpaid_orders here

class PricingEngine:
    def __init__(self, tax_rate: float, discount_rules: dict):
        self.tax_rate = tax_rate
        self.discount_rules = discount_rules

    # move set_discount, discount_for, bulk_discount, set_tax_rate, apply_tax, total_with_tax, shipping_for

class AuditLogger:
    def __init__(self):
        self._log = []

    # move log_event, history, last_event, log_size, clear_log

class NotificationService:
    def __init__(self, smtp_host: str):
        self.smtp_host = smtp_host
        self._sent = []

    # move configure_smtp, notify, sent_count, outbox, reset_outbox
```

OrderRepository can be a simple in‑memory store for orders. Each new class now only references the classes it actually needs, dramatically lowering LCOM4 and DCC for OrderManager and spreading responsibilities across the system.

## Risks

Splitting the class will increase the number of modules and may introduce subtle bugs if dependencies are not wired correctly. Careful integration testing is required to ensure that order placement, pricing, logging, and notification still work together as before.
