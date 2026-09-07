# RefactorLens verification

- **Before:** 2026-09-07T19:47:32+00:00
- **After:** 2026-09-07T20:02:54+00:00

## Metric changes

| Entity | Verdict | Changed metrics |
|---|---|---|
| `src.api.report_view:ReportView` | improved | DCC 2→1 |
| `src.services.order_report_service:OrderReportService` | added | — |

## Prediction check

### 1. Extract infrastructure interactions into an application service

Target: `src.api.report_view:ReportView`

| Metric | Predicted | Actual | Outcome |
|---|---|---|---|
| LCOM4 | down | same | miss |
| DCC | down | down | hit |

**Accuracy:** 1/2 (50%)

### Overall

- Hits: 1
- Misses: 1
- Unverifiable: 0 (excluded from the ratio)
- **Accuracy: 50%**

## Architecture and smells

- **Violations gone:** LV-SKIP src.api.report_view → src.infra.email_client, LV-SKIP src.api.report_view → src.infra.order_repository
- **Violations new:** LV-SKIP src.services.order_report_service → src.infra.email_client, LV-SKIP src.services.order_report_service → src.infra.order_repository

## Confidence calibration

- **Brier:** 0.406 (0 perfect, 0.25 coin flip)
- **ECE:** 0.575
- Stated confidence 0.78 vs actual accuracy 0.50 (gap +0.28)
- 0 prediction(s) came without a confidence and are excluded

| Confidence | Predictions | Stated | Actual | Gap |
|---|---|---|---|---|
| 0.6–0.8 | 1 | 0.70 | 1.00 | -0.30 |
| 0.8–1.0 | 1 | 0.85 | 0.00 | +0.85 |

---

_Metrics only mean something if the behaviour tests still pass. A refactoring that improves every number while breaking the code is a regression, not an improvement._
