# Case: utils:classify_order

- **Model:** `openai/gpt-oss-20b`
- **Repetition:** 1

> Apply **one** suggestion, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The function `classify_order` has a cyclomatic complexity of 15 and accepts seven parameters, both exceeding typical thresholds. This indicates a highly branching, hard‑to‑maintain routine that is prone to bugs and difficult to test. The linear sequence of guard clauses and nested conditions also makes future extensions cumbersome.

## 1. Encapsulate parameters and split logic into helper functions

- **Evidence:** CC, PARAMS
- **Predicted effect:** CC down, PARAMS down

```python
from dataclasses import dataclass

@dataclass
class Order:
    total: float
    item_count: int
    tier: str
    is_gift: bool
    country: str
    coupon: bool
    weight: float


def _is_invalid(order: Order) -> bool:
    return order.total <= 0 or order.item_count <= 0


def _vip_large(order: Order) -> bool:
    return order.tier == "premium" and order.total > 1000

# ... similar small predicate functions for each rule ...

def classify_order(order: Order) -> str:
    if _is_invalid(order):
        return "invalid"
    if _vip_large(order):
        return "vip-large"
    if order.tier == "premium":
        return "vip"
    if order.is_gift and order.country != "TR":
        return "gift-international"
    if order.is_gift:
        return "gift-domestic"
    if order.coupon and order.total > 500:
        return "discounted-large"
    if order.coupon:
        return "discounted"
    if order.weight > 30:
        return "freight"
    if order.total > 1000:
        return "large"
    if order.item_count > 20:
        return "bulk"
    return "standard"
```

## Risks

Changing the public signature from seven positional arguments to a single Order object will break existing callers; all call sites must be updated. The helper functions add a small runtime overhead and increase the number of functions in the module, which could affect metrics like DCC if a class is introduced. Careful unit‑test migration is required to preserve behavior.
