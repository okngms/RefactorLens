# RefactorLens verification

- **Before:** 2026-09-08T17:43:45+00:00
- **After:** 2026-09-08T17:49:58+00:00

## Metric changes

| Entity | Verdict | Changed metrics |
|---|---|---|
| `src.services.order_service:AuditService` | added | — |
| `src.services.order_service:NotificationService` | added | — |
| `src.services.order_service:OrderLifecycleService` | added | — |
| `src.services.order_service:OrderService` | improved | WMC 56→26, LCOM4 5→4 |
| `src.services.order_service:PricingService` | added | — |

## Prediction check

### 1. Extract responsibilities into dedicated services

Target: `src.services.order_service:OrderService`

| Metric | Predicted | Actual | Outcome |
|---|---|---|---|
| NOM | down | same | miss |
| WMC | down | down | hit |
| LCOM4 | down | down | hit |
| DCC | down | same | miss |

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

- **Brier:** 0.338 (0 perfect, 0.25 coin flip)
- **ECE:** 0.325
- Stated confidence 0.82 vs actual accuracy 0.50 (gap +0.33)
- 0 prediction(s) came without a confidence and are excluded

| Confidence | Predictions | Stated | Actual | Gap |
|---|---|---|---|---|
| 0.6–0.8 | 2 | 0.75 | 0.50 | +0.25 |
| 0.8–1.0 | 2 | 0.90 | 0.50 | +0.40 |

---

_Metrics only mean something if the behaviour tests still pass. A refactoring that improves every number while breaking the code is a regression, not an improvement._
