# Case: src.services.order_service:OrderService

- **Condition:** arch_rules (arch-context True, metric-rules True)
- **Model:** `openai/gpt-oss-20b`
- **Repetition:** 1

> Apply **suggestion 1**, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The metrics show that OrderService has a very high number of methods (NOM=26) and a high cumulative cyclomatic complexity (WMC=56), indicating that it is doing too much. The LCOM4 value of 5 signals low cohesion: the class is composed of several unrelated responsibilities (order lifecycle, pricing, audit, notification). The DCC of 4 shows that the class is tightly coupled to many other project classes. Together these metrics confirm the "god_class" smell.

## 1. Extract responsibilities into dedicated services

- **Status:** linked
- **Evidence:** NOM, WMC, LCOM4, DCC
- **Predicted effect:** NOM down (0.90), WMC down (0.80), LCOM4 down (0.90), DCC down (0.70)
- **Addresses:** god_class
- **Destination layer:** application

Create four new classes in the application layer:

```python
class OrderLifecycleService:
    def __init__(self, repository):
        self._repository = repository
    # place, fetch, cancel, close, order_count, orders_for, open_orders, line_count, revenue, tier_summary

class PricingService:
    def __init__(self):
        self._tax_rate = 0.18
        self._discounts: dict[str, float] = {}
    # set_discount, discount_for, bulk_discount, set_tax_rate, apply_tax, total_for, policy_rate, is_priced

class AuditService:
    def __init__(self):
        self._audit: list[str] = []
    # log, history, last_entry, audit_size, clear_audit

class NotificationService:
    def __init__(self, notifier):
        self._notifier = notifier
        self._sent = 0
    # notify, sent_count, reset_sent
```
Then refactor OrderService to become a thin façade that holds references to these services and delegates:

```python
class OrderService:
    def __init__(self, repository, notifier):
        self._lifecycle = OrderLifecycleService(repository)
        self._pricing = PricingService()
        self._audit = AuditService()
        self._notification = NotificationService(notifier)
    # each public method simply forwards to the appropriate service
```
This keeps all classes within the application layer and removes direct imports of presentation or infrastructure.

## Risks

Splitting the class will require updating all callers to use the new services or the façade, which may break existing tests. The new services introduce more classes, potentially increasing maintenance overhead. Care must be taken to avoid duplicating logic (e.g., repository access) across services. If the application already has a dependency injection framework, wiring the new services may need adjustments.
