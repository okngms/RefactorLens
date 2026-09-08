# Interpretation note — arch / gpt-oss-20b / ReportView

Place beside `SUGGESTION.md` in the case directory.

## What was applied

Suggestion 1 only. Suggestion 2 (`CustomerFormatter`) was not applied.

> "Refactor `ReportView` to depend only on the service for data and mail,
> **keeping only formatting methods** (`title`, `describe_customer`)."

So `order_count` and `mail_summary` leave rather than become delegating
wrappers — unlike the two 120b cases on this target, which kept them.

Call sites were updated because Risks asks for it: "callers that invoke
`order_count` or `mail_summary` directly will need to be updated to use
`ReportService`." The two tests now exercise the service; their assertions are
unchanged.

## The third repetition of the same mistake

```
before: 2 LV-SKIP on report_view
after:  2 LV-SKIP on report_service
```

Three cases on this target now, two models, two conditions, three different
class names — and the same outcome every time. The forbidden import moves one
layer down instead of disappearing.

The prompt states the rule in every one of them: "application must NOT import
infrastructure". Each suggestion places the new class in `application` and has
it import `infra` with concrete type annotations.

The fixture contains the answer none of them reached. `OrderService` takes its
repository and notifier as **unannotated** constructor parameters, so it never
imports `infra` and carries no violation. Inversion of control is a standard
answer to exactly this problem, and three suggestions across two models did not
produce it.

This is now a finding rather than an observation.

## Metrics

```
before: NOM 4, LCOM4 2, DCC 2
after:  NOM 2, LCOM4 1, DCC 1
```

Both predictions should hit. `ReportView` keeps `title` and
`describe_customer`, both touching `_width`, so the method-attribute graph
collapses to one component. `_service` is held but touched by no method, which
is a residue of "depend only on the service" applied to a class that no longer
needs data or mail.
