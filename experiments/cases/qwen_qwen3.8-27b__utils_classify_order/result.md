# RefactorLens verification

- **Before:** 2026-09-01T19:00:39+00:00
- **After:** 2026-09-01T19:03:49+00:00

## Metric changes

| Entity | Verdict | Changed metrics |
|---|---|---|
| `utils:classify_order` | mixed | CC 15→3, LOC 25→6, NESTING 1→2 |

## Prediction check

### 1. Decompose classification logic into strategy functions

Target: `utils:classify_order`

| Metric | Predicted | Actual | Outcome |
|---|---|---|---|
| CC | down | down | hit |
| LOC | same | down | miss |

**Accuracy:** 1/2 (50%)

### Overall

- Hits: 1
- Misses: 1
- Unverifiable: 0 (excluded from the ratio)
- **Accuracy: 50%**

---

_Metrics only mean something if the behaviour tests still pass. A refactoring that improves every number while breaking the code is a regression, not an improvement._
