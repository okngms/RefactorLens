# RefactorLens verification

- **Before:** 2026-09-08T17:20:54+00:00
- **After:** 2026-09-08T17:23:51+00:00

## Metric changes

| Entity | Verdict | Changed metrics |
|---|---|---|
| `src.domain.entities:Customer` | improved | NOM 5→1, WMC 5→1, LCOM4 4→1 |

## Prediction check

### 1. Replace explicit getters with a dataclass

Target: `src.domain.entities:Customer`

| Metric | Predicted | Actual | Outcome |
|---|---|---|---|
| NOM | down | down | hit |
| WMC | down | down | hit |
| LCOM4 | down | down | hit |

**Accuracy:** 3/3 (100%)

### Overall

- Hits: 3
- Misses: 0
- Unverifiable: 0 (excluded from the ratio)
- **Accuracy: 100%**

## Architecture and smells

- **Smells gone:** data_class @ src.domain.entities:Customer

## Suspicious improvements

> Metrics improved while the public interface shrank. This is a question, not a verdict: deleting dead code shrinks the interface too. The behaviour tests decide.

- `src.domain.entities:Customer` — metrics improved while 4 public member(s) were deleted: customer_id, email, name, tier

## Confidence calibration

- **Brier:** 0.020 (0 perfect, 0.25 coin flip)
- **ECE:** 0.133
- Stated confidence 0.87 vs actual accuracy 1.00 (gap -0.13)
- 0 prediction(s) came without a confidence and are excluded

| Confidence | Predictions | Stated | Actual | Gap |
|---|---|---|---|---|
| 0.6–0.8 | 1 | 0.80 | 1.00 | -0.20 |
| 0.8–1.0 | 2 | 0.90 | 1.00 | -0.10 |

---

_Metrics only mean something if the behaviour tests still pass. A refactoring that improves every number while breaking the code is a regression, not an improvement._
