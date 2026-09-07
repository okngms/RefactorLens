# RefactorLens verification

- **Before:** 2026-09-07T19:23:43+00:00
- **After:** 2026-09-07T19:26:53+00:00

## Metric changes

| Entity | Verdict | Changed metrics |
|---|---|---|
| `src.domain.entities:Customer` | regressed | NOM 5→6, WMC 5→6 |

## Prediction check

### 1. Add domain behavior to increase cohesion

Target: `src.domain.entities:Customer`

| Metric | Predicted | Actual | Outcome |
|---|---|---|---|
| LCOM4 | down | same | miss |
| DCC | up | same | miss |

**Accuracy:** 0/2 (0%)

### Overall

- Hits: 0
- Misses: 2
- Unverifiable: 0 (excluded from the ratio)
- **Accuracy: 0%**

## Architecture and smells

- **Smells gone:** data_class @ src.domain.entities:Customer

## Confidence calibration

- **Brier:** 0.445 (0 perfect, 0.25 coin flip)
- **ECE:** 0.650
- Stated confidence 0.65 vs actual accuracy 0.00 (gap +0.65)
- 0 prediction(s) came without a confidence and are excluded

| Confidence | Predictions | Stated | Actual | Gap |
|---|---|---|---|---|
| 0.4–0.6 | 1 | 0.50 | 0.00 | +0.50 |
| 0.6–0.8 | 1 | 0.80 | 0.00 | +0.80 |

---

_Metrics only mean something if the behaviour tests still pass. A refactoring that improves every number while breaking the code is a regression, not an improvement._
