# Interpretation note — arch_rules / gpt-oss-120b / OrderService

Place beside `SUGGESTION.md` in the case directory.

## How this differs from case 5

Case 5 (`arch`) proposed a **façade**: extract four services, keep all 26
methods on `OrderService` as delegations. This one says the opposite:

> "... and **remove** the original `notify`, `sent_count`, and `reset_sent`
> methods."

No wrappers. The methods leave.

The `metric-rules` block was in this prompt and states plainly that "a method
that delegates to another object still counts" toward NOM. Whether the model
avoided the façade because it read that is not something one case can settle,
but the two suggestions came from the same model on the same target under
conditions differing only in that block.

## The one ambiguity

> "Inject NotificationService into OrderService (or have OrderService call it
> via composition)"

Injecting a service whose methods have all been removed leaves an unused
reference. Two readings: hold it anyway, or drop notification from
`OrderService` entirely.

**Held**, as written. `OrderService.__init__` still takes a notifier and now
constructs `NotificationService(notifier)`.

This reading **favours the model**: naming the class in the constructor makes it
count toward DCC, so the `DCC up` prediction can hit. Dropping the reference
would have kept DCC at 4 and turned that prediction into a miss. Where the text
supports either reading, the one that gives the model its best case is the
honest choice — the alternative is grading against a reading the model did not
propose.

## Call sites

The three tests for notification now use `NotificationService` directly. Risks
asks for this: "existing code that directly accessed OrderService's
notification or pricing methods must be updated to use the new services."
Assertions are unchanged; only the object under test moved.

## What this also tests

`OrderService` loses three public members and `NotificationService` gains the
same three. The Goodhart check should report them as **moved**, not deleted —
the fix made before phase 5a, so that the tool stops punishing Extract Class.
