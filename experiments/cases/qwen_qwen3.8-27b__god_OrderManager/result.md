# RefactorLens verification

- **Before:** 2026-09-01T18:49:30+00:00
- **After:** 2026-09-01T18:59:52+00:00

## Metric changes

| Entity | Verdict | Changed metrics |
|---|---|---|
| `god:OrderManager` | improved | WMC 49→43 |
| `god:PricingEngine` | added | — |

## Prediction check

### 1. Extract Pricing and Tax Logic

Target: `god:OrderManager`

| Metric | Predicted | Actual | Outcome |
|---|---|---|---|
| LCOM4 | down | same | miss |
| NOM | down | same | miss |
| WMC | down | down | hit |
| DCC | up | same | miss |

**Accuracy:** 1/4 (25%)

### Overall

- Hits: 1
- Misses: 3
- Unverifiable: 0 (excluded from the ratio)
- **Accuracy: 25%**

---

_Metrics only mean something if the behaviour tests still pass. A refactoring that improves every number while breaking the code is a regression, not an improvement._
