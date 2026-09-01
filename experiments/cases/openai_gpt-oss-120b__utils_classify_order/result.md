# RefactorLens verification

- **Before:** 2026-09-01T18:28:49+00:00
- **After:** 2026-09-01T18:31:30+00:00

## Metric changes

| Entity | Verdict | Changed metrics |
|---|---|---|
| `utils:_is_bulk` | added | — |
| `utils:_is_discounted` | added | — |
| `utils:_is_discounted_large` | added | — |
| `utils:_is_freight` | added | — |
| `utils:_is_gift_domestic` | added | — |
| `utils:_is_gift_international` | added | — |
| `utils:_is_invalid_item_count` | added | — |
| `utils:_is_invalid_total` | added | — |
| `utils:_is_large` | added | — |
| `utils:_is_vip` | added | — |
| `utils:_is_vip_large` | added | — |
| `utils:classify_order` | improved | CC 15→12 |

## Prediction check

### 1. Extract each rule into its own helper function

Target: `utils:classify_order`

| Metric | Predicted | Actual | Outcome |
|---|---|---|---|
| CC | down | down | hit |
| LCOM4 | down | — | unverifiable (LCOM4 is not measured for a function target) |

**Accuracy:** 1/1 (100%)

### Overall

- Hits: 1
- Misses: 0
- Unverifiable: 1 (excluded from the ratio)
- **Accuracy: 100%**

---

_Metrics only mean something if the behaviour tests still pass. A refactoring that improves every number while breaking the code is a regression, not an improvement._
