# RefactorLens verification

- **Before:** 2026-09-08T16:35:01+00:00
- **After:** 2026-09-08T16:51:02+00:00

## Metric changes

| Entity | Verdict | Changed metrics |
|---|---|---|
| `src.services.order_service:AuditService` | added | — |
| `src.services.order_service:NotificationService` | added | — |
| `src.services.order_service:OrderLifecycleService` | added | — |
| `src.services.order_service:OrderService` | improved | WMC 56→26, LCOM4 5→4 |
| `src.services.order_service:PricingService` | added | — |

## Prediction check

### 1. Extract four focused service classes

Target: `src.services.order_service:OrderService`

| Metric | Predicted | Actual | Outcome |
|---|---|---|---|
| LCOM4 | down | down | hit |
| NOM | down | same | miss |
| WMC | down | down | hit |
| DCC | up | same | miss |

**Accuracy:** 2/4 (50%)

### Overall

- Hits: 2
- Misses: 2
- Unverifiable: 0 (excluded from the ratio)
- **Accuracy: 50%**

## Architecture and smells

- **Smells gone:** feature_envy_candidate @ src.services.order_service:OrderService.close, god_class @ src.services.order_service:OrderService
- **Smells new:** feature_envy_candidate @ src.services.order_service:OrderLifecycleService.close

## Confidence calibration

- **Brier:** 0.273 (0 perfect, 0.25 coin flip)
- **ECE:** 0.287
- Stated confidence 0.79 vs actual accuracy 0.50 (gap +0.29)
- 0 prediction(s) came without a confidence and are excluded

| Confidence | Predictions | Stated | Actual | Gap |
|---|---|---|---|---|
| 0.4–0.6 | 1 | 0.50 | 0.00 | +0.50 |
| 0.8–1.0 | 3 | 0.88 | 0.67 | +0.22 |

---

_Metrics only mean something if the behaviour tests still pass. A refactoring that improves every number while breaking the code is a regression, not an improvement._
