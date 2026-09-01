# Interpretation note — openai/gpt-oss-20b / utils:classify_order

Place this file in the case directory alongside `SUGGESTION.md`.

## The judgment call

The suggestion changes the public signature from seven positional parameters to
a single `Order` dataclass. Applied to the source alone, every existing caller
breaks and the behaviour tests fail.

But the suggestion's Risks section says so explicitly:

> "Changing the public signature ... will break existing callers; **all call
> sites must be updated**. ... **Careful unit-test migration is required** to
> preserve behavior."

The call-site migration is therefore part of what the suggestion asks for, not
an improvement invented while applying it.

## Consistency with the previous case

In `openai/gpt-oss-20b / god:OrderManager`, adding delegating methods was
**rejected**, because the text never mentioned them. Here, updating the call
sites is **accepted**, because the text names it as a required step.

The rule is the same in both: do what the text explicitly asks, and nothing
more. The outcomes differ because the texts differ.

## What was changed, and what was not

- `utils.py` — the code block the suggestion supplies, verbatim. The elided
  comment `# ... similar small predicate functions for each rule ...` was **not**
  expanded: the `classify_order` body the suggestion writes out calls only
  `_is_invalid` and `_vip_large`, and inventing predicates it does not call
  would be adding to the suggestion.
- `tests/test_utils.py` — the call construction only:
  `classify_order(**defaults)` became `classify_order(Order(**defaults))`.

**Every assertion is unchanged.** The same inputs are still required to produce
the same outputs, so the behavioural contract is still being verified. The
measuring instrument was not weakened; it was taught the new signature.

## A gap worth recording

`run_verify.py` builds `applied.diff` from source files only, skipping `tests/`.
The test-side change is therefore **not** captured in that diff. It is recorded
here instead. If more cases require call-site migration, the diff builder should
be extended to cover tests.

## Outcome

Behaviour tests: **91 passed.** The case is valid.
