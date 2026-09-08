# RefactorLens verification

- **Before:** 2026-09-08T17:04:09+00:00
- **After:** 2026-09-08T17:12:39+00:00

## Metric changes

| Entity | Verdict | Changed metrics |
|---|---|---|
| `src.services.order_service:NotificationService` | added | — |
| `src.services.order_service:OrderService` | mixed | NOM 26→23, WMC 56→53, LCOM4 5→4, DCC 4→5 |

## Prediction check

### 1. Extract Notification responsibilities to a dedicated NotificationService

Target: `src.services.order_service:OrderService`

| Metric | Predicted | Actual | Outcome |
|---|---|---|---|
| LCOM4 | down | down | hit |
| NOM | down | down | hit |
| WMC | down | down | hit |
| DCC | up | up | hit |

**Accuracy:** 4/4 (100%)

### Overall

- Hits: 4
- Misses: 0
- Unverifiable: 0 (excluded from the ratio)
- **Accuracy: 100%**

## Confidence calibration

- **Brier:** 0.101 (0 perfect, 0.25 coin flip)
- **ECE:** 0.237
- Stated confidence 0.76 vs actual accuracy 1.00 (gap -0.24)
- 0 prediction(s) came without a confidence and are excluded

| Confidence | Predictions | Stated | Actual | Gap |
|---|---|---|---|---|
| 0.2–0.4 | 1 | 0.40 | 1.00 | -0.60 |
| 0.8–1.0 | 3 | 0.88 | 1.00 | -0.12 |

---

_Metrics only mean something if the behaviour tests still pass. A refactoring that improves every number while breaking the code is a regression, not an improvement._
