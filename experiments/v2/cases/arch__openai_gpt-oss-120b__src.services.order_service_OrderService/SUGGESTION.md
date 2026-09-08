# Case: src.services.order_service:OrderService

- **Condition:** arch (arch-context True, metric-rules False)
- **Model:** `openai/gpt-oss-120b`
- **Repetition:** 1

> Apply **suggestion 1**, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The class has a very high number of methods (NOM=26) and total cyclomatic complexity (WMC=56), while its cohesion is poor (LCOM4=5). These numbers indicate a god‑class that mixes four distinct responsibilities (order lifecycle, pricing, audit, notification). The class also references four internal types (DCC=4), which will likely increase if responsibilities are split, but the cohesion gain outweighs that.

## 1. Extract four focused service classes

- **Status:** linked
- **Evidence:** LCOM4, NOM, WMC, DCC
- **Predicted effect:** LCOM4 down (0.85), NOM down (0.90), WMC down (0.90), DCC up (0.50)
- **Addresses:** god_class
- **Destination layer:** application

Create four new classes in the same application layer:

- OrderLifecycleService: holds _repository, _next_order_id and implements place, fetch, cancel, close, order_count, orders_for, open_orders, line_count, revenue, tier_summary.
- PricingService: holds _tax_rate, _discounts and implements set_discount, discount_for, bulk_discount, set_tax_rate, apply_tax, total_for, policy_rate, is_priced.
- AuditService: holds _audit and implements log, history, last_entry, audit_size, clear_audit.
- NotificationService: holds _notifier, _sent and implements notify, sent_count, reset_sent.

Each new class receives only the dependencies it needs (e.g., OrderLifecycleService gets repository, NotificationService gets notifier). The original OrderService becomes a thin façade that composes the four services or is removed entirely.

Update imports so that only domain classes are used, preserving the application layer rule.

## Risks

Splitting the class changes the public API; callers that previously used OrderService must be updated to use the new façade or the individual services, which may be a breaking change. Increased DCC reflects more inter‑service references, so careful dependency injection is needed to avoid circular imports. Tests that mock OrderService will need adjustment.
