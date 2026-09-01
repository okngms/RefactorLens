# Case: utils:classify_order

- **Model:** `openai/gpt-oss-120b`
- **Repetition:** 1

> Apply **one** suggestion, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The function shows a cyclomatic complexity of 15 and accepts 7 parameters, both exceeding typical thresholds. The high CC indicates many independent decision branches, making the logic hard to understand and test. The large parameter list suggests low cohesion and a potential violation of the Single Responsibility Principle, increasing the chance of bugs when callers must supply many arguments.

## 1. Extract each rule into its own helper function

- **Evidence:** CC, LCOM4
- **Predicted effect:** CC down, LCOM4 down

Create small functions like `def is_invalid_total(total): return total <= 0`, `def is_gift_international(is_gift, country): return is_gift and country != "TR"`, etc. Then rewrite `classify_order` to call these helpers sequentially and return the matching label. This flattens the decision tree and groups related checks, reducing cyclomatic complexity while improving cohesion.

## 2. Bundle input arguments into a dataclass

- **Evidence:** PARAMS, DCC
- **Predicted effect:** PARAMS down, DCC up

Define `@dataclass class OrderInfo: total: float; item_count: int; tier: str; is_gift: bool; country: str; coupon: bool; weight: float`. Change the signature to `def classify_order(info: OrderInfo):` and adjust the helper calls to use `info.total`, `info.item_count`, etc. This reduces the visible parameter count at the cost of introducing a new class, raising DCC.

## Risks

Splitting logic into many helpers may slightly increase the overall line count and introduce import overhead; ensure all helpers are kept private to the module to avoid API churn. Introducing a dataclass changes the public interface, so callers must be updated and existing tests revised, which could cause breakage if not coordinated.
