# Case: src.services.order_service:OrderService

- **Condition:** arch (arch-context True, metric-rules False)
- **Model:** `openai/gpt-oss-20b`
- **Repetition:** 1

> Apply **suggestion 1**, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The OrderService class is a classic god class: it has a high number of methods (NOM=26) and a high cyclomatic complexity (WMC=56), and its methods are poorly cohesive (LCOM4=5). The class also references several other project classes (DCC=4), indicating a high coupling surface. These metrics together suggest that the class is doing too much and is difficult to maintain or extend.

## 1. Split OrderService into focused services

- **Status:** linked
- **Evidence:** LCOM4, NOM, WMC, DCC
- **Predicted effect:** LCOM4 down (0.90), NOM down (0.90), WMC down (0.80), DCC up (0.40)
- **Addresses:** god_class
- **Destination layer:** application

Create four new classes in the application layer:

```python
class OrderLifecycleService:
    def __init__(self, repository):
        self._repository = repository
    # move place, fetch, cancel, close, order_count, orders_for, open_orders, line_count

class PricingService:
    def __init__(self, tax_rate=0.18, discounts=None):
        self._tax_rate = tax_rate
        self._discounts = discounts or {}
    # move set_discount, discount_for, bulk_discount, set_tax_rate, apply_tax, total_for, policy_rate, is_priced

class AuditService:
    def __init__(self):
        self._audit = []
    # move log, history, last_entry, audit_size, clear_audit

class NotificationService:
    def __init__(self, notifier):
        self._notifier = notifier
        self._sent = 0
    # move notify, sent_count, reset_sent
```

OrderService becomes a thin façade that delegates to these services or is removed entirely. Each new service has fewer responsibilities, lower NOM/WMC, and a more cohesive method‑attribute graph, reducing LCOM4. The overall DCC may rise slightly because each service references the repository or notifier, but the coupling is now more explicit and easier to manage.
```

## Risks

Splitting the class will require refactoring all callers to use the new services, which may break existing tests or integration points. The new services will introduce additional public APIs that need documentation and may increase the surface area for bugs if the delegation logic is not carefully implemented. Careful unit testing and gradual migration (e.g., keeping a wrapper OrderService that forwards to the new services) can mitigate these risks.
