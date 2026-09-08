# Case: src.services.order_service:OrderService

- **Condition:** arch_rules (arch-context True, metric-rules True)
- **Model:** `openai/gpt-oss-120b`
- **Repetition:** 1

> Apply **suggestion 1**, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The OrderService class aggregates four distinct concerns (order lifecycle, pricing, audit, and notification) resulting in a very high method count (NOM=26) and cyclomatic complexity (WMC=56). The method‑attribute graph is fragmented (LCOM4=5), indicating poor cohesion, while all attributes are private (DAM=1.0). It also references four internal classes (DCC=4). These measurements together confirm the god‑class smell and hint at feature‑envy in the notification methods.

## 1. Extract Notification responsibilities to a dedicated NotificationService

- **Status:** linked
- **Evidence:** LCOM4, DCC, NOM, WMC
- **Predicted effect:** LCOM4 down (0.85), NOM down (0.90), WMC down (0.90), DCC up (0.40)
- **Addresses:** god_class, feature_envy_candidate
- **Destination layer:** application

Create a new class NotificationService in the same application package:
```python
class NotificationService:
    def __init__(self, notifier):
        self._notifier = notifier
        self._sent = 0

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
```
Inject NotificationService into OrderService (or have OrderService call it via composition) and remove the original `notify`, `sent_count`, and `reset_sent` methods. The original class now no longer touches the notifier directly, reducing its cohesion fragmentation.

## 2. Extract Pricing logic into a PricingService

- **Status:** linked
- **Evidence:** LCOM4, NOM, WMC, DCC
- **Predicted effect:** LCOM4 down (0.90), NOM down (0.95), WMC down (0.95), DCC down (0.60)
- **Addresses:** god_class
- **Destination layer:** application

Introduce a PricingService that owns `_tax_rate`, `_discounts` and all related methods:
```python
class PricingService:
    def __init__(self, tax_rate: float = 0.18):
        self._tax_rate = tax_rate
        self._discounts: dict[str, float] = {}

    # discount management
    def set_discount(self, tier, rate): ...
    def discount_for(self, tier): ...
    def bulk_discount(self, quantity): ...
    def set_tax_rate(self, rate): ...
    def apply_tax(self, amount): ...
    def total_for(self, subtotal, tier): ...
    def policy_rate(self, policy, tier): ...
    def is_priced(self, tier): ...
```
OrderService receives a PricingService instance (e.g., via its constructor) and delegates pricing calls. The original tax‑rate and discount attributes are removed from OrderService, shrinking its attribute set and improving cohesion.

## Risks

Splitting the class introduces new public interfaces; existing code that directly accessed OrderService's notification or pricing methods must be updated to use the new services, which may cause runtime errors if not refactored consistently. The added indirection could slightly increase overall call depth and may raise DCC for OrderService (it now references the new services). Careful integration testing is required to ensure that repository interactions and audit logging remain unchanged.
