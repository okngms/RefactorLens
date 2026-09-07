# Phase 5b protocol — locked before the first case

> Supersedes the part B design in `docs/v2-duzeltme-asama5.md`. Written after
> reading the 5a data and **before** applying a single suggestion.
>
> Writing it down at this moment is the point. The targets below were chosen
> because 5a showed what each would test; choosing them after seeing which
> ones produced interesting deltas would be selection on the outcome.

---

## What 5b measures that 5a could not

5a read the suggestions. 5b applies them and asks three things no amount of
reading can answer:

1. **Did the prediction hold?** The project's central question, now with
   `confidence` attached so calibration is measurable too.
2. **Did the suggestion close the violation it claimed to address?** New in v2:
   `verify` reports violation deltas, so "extract to an application service"
   can be checked against whether the two `LV-SKIP` edges actually disappeared.
3. **Did anything get worse that no metric shows?** The behaviour gate and the
   Goodhart check answer this — and 5a surfaced a case where **neither of them
   would fire**, which is the most interesting cell in the design.

---

## Design

**Two conditions × two models × three targets = 12 cases.**

| Axis | Values | Held fixed |
|---|---|---|
| Condition | `arch`, `arch_rules` | architectural context always on |
| Model | `openai/gpt-oss-120b`, `openai/gpt-oss-20b` | — |
| Target | `OrderService`, `Customer`, `ReportView` | the 5a targets |

The varying axis is `metric-rules`, which is H2: does telling the model how the
metrics are computed improve its predictions about them? Architectural context
is held **on** because 5a showed it changes what gets suggested, and comparing
predictions across different suggestions would confound the two.

`qwen/qwen3.8-27b` is excluded. Its 5a data is incomplete and the loss was
systematic (all three `plain`/`Customer` repetitions failed to a hard
per-request output ceiling), so it cannot enter a condition comparison.

**Repetition 1 always. Suggestion 1 always.** Unchanged from FINDINGS-1, and
the reason is unchanged: picking the run or the suggestion after seeing them
would let "the one that looks best" into the results.

**Narrowest possible interpretation.** Nothing the suggestion does not
explicitly ask for gets improved. Where the text itself asks for something —
updating call sites, for instance — that is done.

**Behaviour tests after every application.** `pytest examples/layered_project/tests`,
71 tests. Failure marks the case `broken`: its metric delta is void and it is
reported separately.

---

## What each target is expected to test

These are **expectations, not predictions to be scored**. They are recorded so
that a surprising result is visible as a surprise.

### `Customer` — the metric invites the damage

5a: without the `data_class` label, 8 of 15 suggestions propose making the
private fields public, and they predict `DAM down` while doing it. The model is
not blind to the trade; it makes it deliberately because LCOM4 rewards it.

With the label the proposal disappears — 0 of 12. But two suggestions in the
labelled conditions propose something else:

> *"Add a composite accessor to connect attributes"*
> *"Add a hub method that touches all attributes"*

This is not a refactoring. LCOM4 counts connected components in the
method-attribute graph; one method touching every attribute merges them all and
drops LCOM4 to 1. Nothing improves. Nothing is removed, so the behaviour tests
pass and the public interface grows rather than shrinks, so the Goodhart check
stays silent.

**Every defence the tool has would report this as a clean success.** That is why
it is in the design.

### `ReportView` — does the advice close the violation?

5a: with architectural context, 13 of 25 suggestions name a layer and target the
two `LV-SKIP` edges. Without it, 1 of 24 does.

5b asks the follow-up: applying one of those suggestions, do the violations
actually close? A suggestion can name the right layer and still leave the import
in place.

### `OrderService` — does the FINDINGS-1 failure reproduce?

5a: every condition predicts `LCOM4 down, NOM down, WMC down, DCC up` — the
exact pattern that scored 1 of 4 in FINDINGS-1, on a different fixture. If it
reproduces here, the residue-dependent failure is not an artefact of
`messy_project`.

---

## Reporting

Per metric first, class grouping second (`docs/SPEC-duzeltme-2.5.md`). Plus:

- **Violation closure:** claimed vs actually closed, per case.
- **Calibration:** Brier and ECE over the verifiable predictions, per condition.
- **Broken cases:** listed separately, deltas void.
- **Silent successes:** cases where every metric improved, tests passed, the
  interface did not shrink, and yet nothing about the code is better. There is
  no automatic check for this; it is judged by reading the diff and recorded as
  such.

That last category exists because 5a found one and the tool cannot see it.

---

## Power

Twelve cases, roughly 2-4 predictions each, so 25-45 verifiable predictions
split across two conditions. **This cannot detect a small effect.** What it can
do:

- If Class B accuracy stays near zero in both conditions, the simplest
  intervention does not work — a stronger result than a small improvement, and
  a reason for v3's feedback loop.
- If it rises substantially, that is a signal worth testing at scale in
  LensBench, not a conclusion.

FINDINGS-2 must state the interval, not the percentage alone.
