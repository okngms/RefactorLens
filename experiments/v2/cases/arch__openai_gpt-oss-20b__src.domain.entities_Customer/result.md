# RefactorLens verification

- **Before:** 2026-09-08T17:14:33+00:00
- **After:** 2026-09-08T17:19:47+00:00

## Metric changes

| Entity | Verdict | Changed metrics |
|---|---|---|
| `src.domain.entities:Customer` | mixed | NOM 5→6, WMC 5→6, LCOM4 4→1 |

## Prediction check

### 1. Add a composite accessor to connect attributes

Target: `src.domain.entities:Customer`

| Metric | Predicted | Actual | Outcome |
|---|---|---|---|
| LCOM4 | down | down | hit |
| WMC | up | up | hit |

**Accuracy:** 2/2 (100%)

### Overall

- Hits: 2
- Misses: 0
- Unverifiable: 0 (excluded from the ratio)
- **Accuracy: 100%**

## Architecture and smells

- **Smells gone:** data_class @ src.domain.entities:Customer

## Confidence calibration

- **Brier:** 0.085 (0 perfect, 0.25 coin flip)
- **ECE:** 0.250
- Stated confidence 0.75 vs actual accuracy 1.00 (gap -0.25)
- 0 prediction(s) came without a confidence and are excluded

| Confidence | Predictions | Stated | Actual | Gap |
|---|---|---|---|---|
| 0.4–0.6 | 1 | 0.60 | 1.00 | -0.40 |
| 0.8–1.0 | 1 | 0.90 | 1.00 | -0.10 |

---

_Metrics only mean something if the behaviour tests still pass. A refactoring that improves every number while breaking the code is a regression, not an improvement._
