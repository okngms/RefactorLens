# Interpretation note — arch_rules / gpt-oss-120b / ReportView

Place beside `SUGGESTION.md` in the case directory.

## The ambiguity

Suggestion 1 names exactly three things to move: `order_count`, `mail_summary`
and the title-generation logic. It says nothing about `describe_customer`.

But the sketch it supplies for `ReportView` shows only three delegating
methods, no `describe_customer`, and an `__init__` holding nothing but the
service. Taken literally, the sketch deletes a method the prose never mentions.

`describe_customer` is the subject of **suggestion 2**, which is not applied.

## What was applied

The prose, not the sketch. Three things moved; `describe_customer` stayed, and
`_width` stayed with it because that method needs it. The service keeps its own
`_width` for `title`, as the suggestion's own sketch specifies.

The consequence is a duplicated `_width`. That is a faithful result of applying
suggestion 1 alone, and it is exactly the kind of residue the experiment exists
to measure.

## Why this reading

The protocol rule is "improve nothing the text does not explicitly ask for".
Deleting `describe_customer` is not an improvement the text asks for in
suggestion 1; it belongs to suggestion 2. Following the sketch instead of the
prose would have applied half of suggestion 2 under the name of suggestion 1.

## What the other reading would have produced

Removing `describe_customer` takes `ReportView` to three delegating methods
touching one attribute — LCOM4 would very likely reach 1 and the prediction
`LCOM4 down` would hit. The choice therefore determines the outcome, which is
why it is written down before the measurement.
