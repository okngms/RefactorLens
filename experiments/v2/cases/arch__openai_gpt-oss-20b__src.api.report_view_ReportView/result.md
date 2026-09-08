# RefactorLens verification

- **Before:** 2026-09-08T17:26:00+00:00
- **After:** 2026-09-08T17:32:52+00:00

## Metric changes

| Entity | Verdict | Changed metrics |
|---|---|---|
| `src.api.report_view:ReportView` | improved | NOM 4→2, WMC 4→2, LCOM4 2→1, DCC 2→1 |
| `src.services.report_service:ReportService` | added | — |

## Prediction check

### 1. Move data access and mail logic to a dedicated service

Target: `src.api.report_view:ReportView`

| Metric | Predicted | Actual | Outcome |
|---|---|---|---|
| LCOM4 | down | down | hit |
| DCC | down | down | hit |

**Accuracy:** 2/2 (100%)

### Overall

- Hits: 2
- Misses: 0
- Unverifiable: 0 (excluded from the ratio)
- **Accuracy: 100%**

## Architecture and smells

- **Violations gone:** LV-SKIP src.api.report_view → src.infra.email_client, LV-SKIP src.api.report_view → src.infra.order_repository
- **Violations new:** LV-SKIP src.services.report_service → src.infra.email_client, LV-SKIP src.services.report_service → src.infra.order_repository

## Confidence calibration

- **Brier:** 0.025 (0 perfect, 0.25 coin flip)
- **ECE:** 0.150
- Stated confidence 0.85 vs actual accuracy 1.00 (gap -0.15)
- 0 prediction(s) came without a confidence and are excluded

| Confidence | Predictions | Stated | Actual | Gap |
|---|---|---|---|---|
| 0.6–0.8 | 1 | 0.80 | 1.00 | -0.20 |
| 0.8–1.0 | 1 | 0.90 | 1.00 | -0.10 |

---

_Metrics only mean something if the behaviour tests still pass. A refactoring that improves every number while breaking the code is a regression, not an improvement._
