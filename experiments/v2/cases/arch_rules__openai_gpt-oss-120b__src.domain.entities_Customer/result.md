# RefactorLens verification

- **Before:** 2026-09-07T19:30:15+00:00
- **After:** 2026-09-07T19:43:38+00:00

## Metric changes

No metric changed.

## Prediction check

### 1. Replace explicit getters with read‑only properties

Target: `src.domain.entities:Customer`

| Metric | Predicted | Actual | Outcome |
|---|---|---|---|
| LCOM4 | down | same | miss |
| NOM | down | same | miss |
| WMC | down | same | miss |

**Accuracy:** 0/3 (0%)

### Overall

- Hits: 0
- Misses: 3
- Unverifiable: 0 (excluded from the ratio)
- **Accuracy: 0%**

## Confidence calibration

- **Brier:** 0.781 (0 perfect, 0.25 coin flip)
- **ECE:** 0.883
- Stated confidence 0.88 vs actual accuracy 0.00 (gap +0.88)
- 0 prediction(s) came without a confidence and are excluded

| Confidence | Predictions | Stated | Actual | Gap |
|---|---|---|---|---|
| 0.8–1.0 | 3 | 0.88 | 0.00 | +0.88 |

---

_Metrics only mean something if the behaviour tests still pass. A refactoring that improves every number while breaking the code is a regression, not an improvement._
