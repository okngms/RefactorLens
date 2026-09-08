# Interpretation note — arch_rules / gpt-oss-20b / Customer

Place beside `SUGGESTION.md` in the case directory.

## Why the call sites were not updated

The Risks section says:

> "If external code relies on the accessor methods, those calls **will fail**."

That is a warning, not a request. Compare case 2 on the same target, whose
Risks said "Ensure the whole codebase is updated" — an explicit instruction,
and the call sites were updated there.

The protocol rule distinguishes the two: what the text asks for is done, what
it merely predicts is not. Repairing an omission the suggestion did not ask to
repair would be rescuing it.

## What was applied

The dataclass exactly as sketched, including the underscore-prefixed field
names. Nothing else was touched.

```
before: NOM 5, WMC 5, LCOM4 4, DAM 1.00, interface 5
after:  NOM 1, WMC 1, LCOM4 1, DAM 1.00, interface 1
```

Behaviour tests: **1 failed, 45 passed, 25 errors.**

## The mirror of case 7

These two cases come from the same model on the same target, differing only in
the metric-rules block, and they fail in opposite directions.

| | Case 7 (`arch`) | Case 8 (`arch_rules`) |
|---|---|---|
| Change | added one method | removed four methods |
| LCOM4 | 4 → 1 | 4 → 1 |
| Behaviour tests | 71 pass | 26 fail |
| Interface | grew 5 → 6 | shrank 5 → 1 |
| Goodhart | silent | fires |
| Predictions | 2/2 | likely 3/3 |

Both reach LCOM4 = 1. Both predict correctly. One is invisible to every check
the tool has; the other trips two of them at once.

The pair is the clearest statement of what the project measures: prediction
accuracy and design quality are independent. A model can be completely right
about the numbers in both a change that does nothing and a change that breaks
everything.

## On the underscore fields

The sketch names the dataclass fields `_customer_id`, `_name` and so on, so DAM
stays at 1.00 — the attributes are still private by convention. But a dataclass
generates `__init__(self, _customer_id, ...)`, so every construction site would
need the underscore too. This is part of why the tests error rather than merely
fail.

The model warned about the generated `__init__` in its Risks section. It saw
the consequence and proposed the change anyway, which is consistent with the
rest of the experiment: the model is not unaware, it is optimising the metric
it was pointed at.
