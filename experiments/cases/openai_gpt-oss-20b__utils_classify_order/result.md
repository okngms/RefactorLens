# RefactorLens verification

- **Before:** 2026-09-01T18:42:44+00:00
- **After:** 2026-09-01T18:48:39+00:00

## Metric changes

| Entity | Verdict | Changed metrics |
|---|---|---|
| `utils:Order` | added | — |
| `utils:_is_invalid` | added | — |
| `utils:_vip_large` | added | — |
| `utils:classify_order` | improved | CC 15→13, LOC 25→23, PARAMS 7→1 |

## Prediction check

### 1. Encapsulate parameters and split logic into helper functions

Target: `utils:classify_order`

| Metric | Predicted | Actual | Outcome |
|---|---|---|---|
| CC | down | down | hit |
| PARAMS | down | down | hit |

**Accuracy:** 2/2 (100%)

### Overall

- Hits: 2
- Misses: 0
- Unverifiable: 0 (excluded from the ratio)
- **Accuracy: 100%**

---

_Metrics only mean something if the behaviour tests still pass. A refactoring that improves every number while breaking the code is a regression, not an improvement._
