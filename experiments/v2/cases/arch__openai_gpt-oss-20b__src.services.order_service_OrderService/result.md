# RefactorLens verification

- **Before:** 2026-09-08T17:37:48+00:00
- **After:** 2026-09-08T17:42:55+00:00

## Metric changes

| Entity | Verdict | Changed metrics |
|---|---|---|
| `src.services.order_service:AuditService` | added | — |
| `src.services.order_service:NotificationService` | added | — |
| `src.services.order_service:OrderLifecycleService` | added | — |
| `src.services.order_service:OrderService` | improved | WMC 56→30 |
| `src.services.order_service:PricingService` | added | — |

## Prediction check

### 1. Split OrderService into focused services

Target: `src.services.order_service:OrderService`

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

## Architecture and smells

- **Smells gone:** feature_envy_candidate @ src.services.order_service:OrderService.close, god_class @ src.services.order_service:OrderService
- **Smells new:** feature_envy_candidate @ src.services.order_service:OrderLifecycleService.close

## Confidence calibration

- **Brier:** 0.455 (0 perfect, 0.25 coin flip)
- **ECE:** 0.600
- Stated confidence 0.75 vs actual accuracy 0.25 (gap +0.50)
- 0 prediction(s) came without a confidence and are excluded

| Confidence | Predictions | Stated | Actual | Gap |
|---|---|---|---|---|
| 0.2–0.4 | 1 | 0.40 | 0.00 | +0.40 |
| 0.6–0.8 | 1 | 0.80 | 1.00 | -0.20 |
| 0.8–1.0 | 2 | 0.90 | 0.00 | +0.90 |

---

_Metrics only mean something if the behaviour tests still pass. A refactoring that improves every number while breaking the code is a regression, not an improvement._
