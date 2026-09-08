# Prediction accuracy (phase 5b)

- **Cases:** 12 of 12

> Each case applies **suggestion 1** of **repetition 1** under the narrowest possible interpretation. Cases whose behaviour tests fail are marked `broken`: their metric delta is void.

| Condition | Model | Target | Status | Hits | Misses | Unverifiable | Accuracy |
|---|---|---|---|---|---|---|---|
| arch | `openai/gpt-oss-120b` | `ReportView` | ok | 1 | 1 | 0 | 50% |
| arch | `openai/gpt-oss-120b` | `Customer` | ok | 0 | 2 | 0 | 0% |
| arch | `openai/gpt-oss-120b` | `OrderService` | ok | 2 | 2 | 0 | 50% |
| arch | `openai/gpt-oss-20b` | `ReportView` | ok | 2 | 0 | 0 | 100% |
| arch | `openai/gpt-oss-20b` | `Customer` | ok | 2 | 0 | 0 | 100% |
| arch | `openai/gpt-oss-20b` | `OrderService` | ok | 1 | 3 | 0 | 25% |
| arch_rules | `openai/gpt-oss-120b` | `ReportView` | ok | 1 | 1 | 0 | 50% |
| arch_rules | `openai/gpt-oss-120b` | `Customer` | ok | 0 | 3 | 0 | 0% |
| arch_rules | `openai/gpt-oss-120b` | `OrderService` | ok | 4 | 0 | 0 | 100% |
| arch_rules | `openai/gpt-oss-20b` | `ReportView` | ok | 1 | 1 | 0 | 50% |
| arch_rules | `openai/gpt-oss-20b` | `Customer` | broken | 3 | 0 | 0 | 100% |
| arch_rules | `openai/gpt-oss-20b` | `OrderService` | ok | 2 | 2 | 0 | 50% |

## Overall (valid cases only)

- Verifiable predictions: 31
- Correct: 16
- **Accuracy: 52%**

## By condition (H2)

Does telling the model how the metrics are computed improve its predictions about them?

| Condition | Predictions | Correct | Accuracy |
|---|---|---|---|
| arch | 16 | 8 | 50% |
| arch_rules | 15 | 8 | 53% |

## Per metric

Reported per metric first; the subtractive / residue-dependent grouping is a hypothesis, not a taxonomy (`docs/SPEC-duzeltme-2.5.md`).

| Metric | Predicted | Correct | Accuracy |
|---|---|---|---|
| DCC | 9 | 5 | 56% |
| LCOM4 | 11 | 5 | 45% |
| NOM | 5 | 1 | 20% |
| WMC | 6 | 5 | 83% |

## Violation closure

A suggestion can name the right layer and still leave the import in place. This is what v1 could not ask.

**`ReportView` — gpt-oss-120b, arch**
- closed: LV-SKIP src.api.report_view → src.infra.email_client
- closed: LV-SKIP src.api.report_view → src.infra.order_repository
- opened: LV-SKIP src.services.order_report_service → src.infra.email_client
- opened: LV-SKIP src.services.order_report_service → src.infra.order_repository
- **no net change**

**`ReportView` — gpt-oss-20b, arch**
- closed: LV-SKIP src.api.report_view → src.infra.email_client
- closed: LV-SKIP src.api.report_view → src.infra.order_repository
- opened: LV-SKIP src.services.report_service → src.infra.email_client
- opened: LV-SKIP src.services.report_service → src.infra.order_repository
- **no net change**

**`ReportView` — gpt-oss-120b, arch_rules**
- closed: LV-SKIP src.api.report_view → src.infra.email_client
- closed: LV-SKIP src.api.report_view → src.infra.order_repository
- opened: LV-SKIP src.services.report_service → src.infra.email_client
- opened: LV-SKIP src.services.report_service → src.infra.order_repository
- **no net change**

**`ReportView` — gpt-oss-20b, arch_rules**
- closed: LV-SKIP src.api.report_view → src.infra.email_client
- closed: LV-SKIP src.api.report_view → src.infra.order_repository
- opened: LV-SKIP src.services.report_service → src.infra.email_client
- opened: LV-SKIP src.services.report_service → src.infra.order_repository
- **no net change**


## Flagged cases

- **broken:** `openai/gpt-oss-20b` / `Customer` — 1 failed, 45 passed, 25 errors in 0.53s
- **suspicious:** `openai/gpt-oss-20b` / `Customer`

## Calibration

Brier is the mean squared error of the stated confidence: 0 is perfect, **0.25 is what a coin flip scores**, and above that the confidence is worse than useless. ECE averages the gap between stated and actual over confidence buckets.

| Condition | Predictions | Brier | ECE | Stated | Actual | Gap |
|---|---|---|---|---|---|---|
| arch | 16 | 0.302 | 0.263 | 0.76 | 0.50 | +0.26 |
| arch_rules | 15 | 0.386 | 0.373 | 0.83 | 0.53 | +0.29 |
| all | 31 | 0.343 | 0.290 | 0.79 | 0.52 | +0.28 |

Where the confidence sits, and whether it is earned.

| Confidence | Predictions | Stated | Actual | Gap |
|---|---|---|---|---|
| 0.2–0.4 | 2 | 0.40 | 0.50 | -0.10 |
| 0.4–0.6 | 3 | 0.53 | 0.33 | +0.20 |
| 0.6–0.8 | 8 | 0.78 | 0.75 | +0.03 |
| 0.8–1.0 | 18 | 0.89 | 0.44 | +0.44 |
