# Case: utils:classify_order

- **Model:** `qwen/qwen3.8-27b`
- **Repetition:** 1

> Apply **one** suggestion, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The function exhibits a high Cyclomatic Complexity (CC=15) and a high Parameter Count (PARAMS=7), indicating that it handles a large number of distinct decision paths and input variables within a single scope. While the nesting depth is low (NESTING=1), the linear accumulation of conditional branches suggests a lack of structural decomposition, making the logic difficult to maintain and test in isolation for specific order types.

## 1. Decompose classification logic into strategy functions

- **Evidence:** CC, LOC
- **Predicted effect:** CC down, LOC same

Refactor the function by extracting each distinct classification branch (e.g., 'vip-large', 'gift-international', 'freight') into separate private helper functions or a list of predicate-action pairs. The main function would then iterate through these strategies, returning the first match. This reduces the CC of the main entry point to a low value (e.g., < 5) while distributing the complexity across smaller, focused units.

## 2. Encapsulate order attributes into a data object

- **Evidence:** PARAMS
- **Predicted effect:** PARAMS down

Create a simple dataclass or namedtuple (e.g., OrderDetails) to hold total, item_count, tier, is_gift, country, coupon, and weight. Change the function signature to accept this single object. This reduces the parameter count from 7 to 1, improving readability and reducing the cognitive load associated with managing multiple scalar arguments.

## Risks

Refactoring into strategies requires careful ordering of conditions to preserve the original precedence (e.g., 'vip-large' must be checked before 'vip'). Introducing a data object changes the public API, requiring updates to all call sites. If the classification rules are expected to change frequently, a strategy pattern might introduce unnecessary indirection compared to a simple list of lambdas.
