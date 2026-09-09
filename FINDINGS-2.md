# Findings 2

Does architectural context change what a model advises, and does knowing how a
metric is computed make it better at predicting that metric?

FINDINGS-1 established that models predict the structural effect of their own
refactoring suggestions about half the time. This report adds two interventions,
a confidence score, and a question the first experiment could not ask: when a
suggestion claims to fix an architecture violation, does the violation close?

**Short version.** Architectural context works: without it the models never
mention the layer problem, with it half their suggestions target it. Telling
them how the metrics are computed does not work — accuracy moved three points
while stated confidence rose seven. Confidence itself turns out to be
anti-correlated with correctness above 0.8, where most of it lives. And the
metric classification from FINDINGS-1 was refuted by its own refutation
condition: what determines predictability is not the metric but whether the
change leaves residue behind.

---

## Setup

| | |
|---|---|
| Models | `openai/gpt-oss-120b`, `openai/gpt-oss-20b` (via Groq) |
| Excluded | `qwen/qwen3.8-27b` — see Limitations |
| Fixture | `examples/layered_project`, four declared layers, 71 behaviour tests |
| Targets | `OrderService` (god class), `Customer` (data class), `ReportView` (two layer violations) |
| Temperature | 0.2 |
| Tool | rlens, scan schema v2, arch schema v1 |

**Part 5a** collected 99 advice runs across a 2×2 condition matrix. **Part 5b**
applied 12 of them by hand and measured the result.

The two interventions:

- **arch-context** — the prompt carries the target's layer, the permission
  matrix, any open violations and the smell labels.
- **metric-rules** — the prompt carries a short statement of how each metric is
  computed, aimed directly at the scope error FINDINGS-1 found. Threshold
  numbers are never included, in either condition.

Raw data: `experiments/v2/runs/` and `experiments/v2/cases/`. Protocol:
`docs/v2-5b-protokol.md`.

---

## 5a — what the models said

### Contract compliance held

99 runs, zero suggestions unlinked from a metric, zero repair rounds, zero
unparseable replies, and **every prediction carried a confidence**. The
structured prompt continues to work; nothing below is a failure to follow
instructions.

### Architectural context changed the advice

Counting suggestions whose text names a layer:

| Target | neither | metric-rules | arch-context | both |
|---|---|---|---|---|
| `ReportView` (2 violations) | 1 / 12 | 0 / 12 | **8 / 13** | **5 / 12** |
| `OrderService` (no violation) | 0 / 16 | 0 / 19 | 4 / 11 | 0 / 12 |
| `Customer` (no violation) | 0 / 6 | 0 / 9 | 0 / 6 | 0 / 6 |

Without the block, 1 of 24 suggestions on the violating target mentions the
layer problem. With it, 13 of 25 do. The control behaves too: on the two
targets with no violation, context produces almost no architectural language
rather than inventing it.

### The data_class label withdrew an invitation

`Customer` is a sound domain entity with one accessor per private field. LCOM4
reads 4 — the false positive documented in FINDINGS-1 as a reporting
limitation.

It is not only a reporting limitation. Without the `data_class` label:

> *"Replace trivial getters with **public dataclass fields**"*
> *"Replace getters with **public fields** via a dataclass"*

Eight of fifteen suggestions propose destroying encapsulation, and **each one
predicts `DAM down` while doing it**. The model is not blind to the trade; it
makes it deliberately, because LCOM4 rewards it.

With the label — which states that a high LCOM4 is expected for a data holder —
that proposal disappears. Zero of twelve. `DAM` is never mentioned.

A one-sentence piece of context removed an invitation the metric itself was
issuing.

### Both interventions together were not better than one

`arch_rules` produced **less** layer-aware language than `arch` alone (5 vs 8 on
`ReportView`, 0 vs 4 on `OrderService`). The metric-rules block adds roughly 250
tokens of metric talk and appears to pull the answer toward metric language and
away from layer language.

A single-axis experiment would have concluded that two interventions are better
than one. This is what the 2×2 was for.

---

## 5b — whether they were right

Twelve cases, 31 verifiable predictions, **16 correct (52%)**.

| Metric | Predicted | Correct | |
|---|---|---|---|
| WMC | 6 | 5 | 83% |
| DCC | 9 | 5 | 56% |
| LCOM4 | 11 | 5 | 45% |
| NOM | 5 | 1 | 20% |

### The FINDINGS-1 classification was refuted

FINDINGS-1 reported a clean split: 6/6 on one group of metrics, 0/7 on the
other, and named the groups **subtractive** and **residue-dependent**. The
correction that formalised it wrote its own refutation condition: *if a Class B
metric turns out consistently predictable, the mechanism is wrong.*

`DCC` was 0/2 in v1 and is 56% here. `LCOM4` was 0/2 and is 45%. The condition
is met.

The mechanism was named after the wrong thing. It is not the metric that
decides predictability; it is **whether the change leaves residue in the
target**.

Two cases make this exactly:

| | Case 5 | Case 6 |
|---|---|---|
| Model, target | 120b, `OrderService` | 120b, `OrderService` |
| Suggestion | extract four services, **keep 26 delegating wrappers** | extract one service, **remove the three methods** |
| NOM | predicted down → **same** | predicted down → **down** |
| Accuracy | 2 / 4 | **4 / 4** |

Same model, same class, same refactoring type. The only difference is whether
wrappers stayed. A delegating method still counts toward NOM and still touches
an attribute for LCOM4, so both metrics sit still — and the models almost never
predict that.

`WMC` survives both shapes because it is additive: a wrapper costs 1 instead of
the 3 the original method cost, so the sum falls either way. That is why it
leads the table at 83%.

`NOM` is worst at 20% because façade suggestions always leave residue.

The revised classification is two-dimensional and is in
`docs/SPEC-duzeltme-2.5-v2.md`. There is no single "Class A accuracy" figure any
more — only accuracy for a metric under a change shape.

### H2: knowing the rules did not help

| Condition | Predictions | Correct | Accuracy | Stated confidence |
|---|---|---|---|---|
| arch | 16 | 8 | 50% | 0.76 |
| arch_rules | 15 | 8 | 53% | **0.83** |

Three points of accuracy is noise at this sample size. Seven points of
confidence is the visible effect.

**The intervention raised confidence, not competence.**

One qualification: in cases 5 and 6 the metric-rules block appears to have
changed the *suggestion*, steering the model away from a façade and toward a
change whose effect it could predict. If that generalises, the effect of the
intervention is not better prediction of a given change but the selection of a
more predictable change — which is not obviously an improvement. A model steered
toward what it can measure is not the same as a model giving better advice. One
case pair does not settle it, and case 10 points the other way.

### Confidence is anti-correlated with correctness where it matters

| Confidence | Predictions | Stated | Actual | Gap |
|---|---|---|---|---|
| 0.2–0.4 | 2 | 0.40 | 0.50 | −0.10 |
| 0.4–0.6 | 3 | 0.53 | 0.33 | +0.20 |
| 0.6–0.8 | 8 | 0.78 | 0.75 | **+0.03** |
| 0.8–1.0 | **18** | **0.89** | **0.44** | **+0.44** |

Between 0.6 and 0.8 the models are almost perfectly calibrated. Above 0.8 —
where 18 of 31 predictions sit — they are worse than chance.

| Condition | Brier | ECE | Overconfidence |
|---|---|---|---|
| arch | 0.302 | 0.263 | +0.26 |
| arch_rules | **0.386** | 0.373 | +0.29 |
| all | 0.343 | 0.290 | +0.28 |

A coin flip scores 0.25 on Brier. Under `arch_rules` the stated confidence is
not merely uninformative but **misleading**: ranking suggestions by it selects
the wrong ones.

This has a direct consequence for tools like this one. Using a model's own
confidence to filter, sort or auto-apply its suggestions would, on this data,
cause harm.

### The violation moved instead of closing — four times out of four

`ReportView` carries two `LV-SKIP` edges: the presentation layer imports
infrastructure directly. Four cases targeted it, across two models and two
conditions.

All four closed both edges on `report_view`. All four opened the same two on the
new application service. **Net violations: unchanged, every time.**

Every prompt stated the rule the new class then broke: *application must NOT
import infrastructure*. Each suggestion placed its service in `application` and
annotated its constructor with the concrete infrastructure types.

The fixture contains the answer none of them reached. `OrderService` takes its
repository and notifier as **unannotated** constructor parameters, never imports
`infra`, and carries no violation. Inversion of control is the textbook response
to exactly this problem.

Metric verification alone would have recorded four correct `DCC` predictions and
nothing else. This is the question FINDINGS-1 could not ask.

---

## Three cases where the metric improved and nothing did

### Nothing broke, and nothing caught it

`arch` / 20b / `Customer`. One added method:

```python
def all_info(self) -> tuple[int, str, str, str]:
    return (self._customer_id, self._name, self._email, self._tier)
```

LCOM4 counts connected components in the method-attribute graph, so one method
touching every attribute merges all of them.

```
before: NOM 5, WMC 5, LCOM4 4, interface 5
after:  NOM 6, WMC 6, LCOM4 1, interface 6
```

Critical to perfect. The class is one method worse than it was.

| Check | Result |
|---|---|
| Behaviour tests | 71 pass — nothing was removed |
| Goodhart (interface shrank) | silent — the interface **grew** |
| Violations | unchanged |
| Prediction accuracy | 100% |

By every measure the tool has, this is one of the best cases in the experiment.
**No check the tool has would ever fire on it.**

The model is not deceiving anyone. It was asked to lower LCOM4, it lowered
LCOM4, and it declared the `WMC up` cost while doing so.

A cohesion measure defined over shared attribute access can always be satisfied
by one method that touches everything, and no amount of behaviour testing will
notice. **We have no defence against this and no candidate that does not have
the same hole.** It is recorded here as an open problem.

### Everything broke, and two checks caught it

`arch_rules` / 20b / `Customer`, the same model on the same target, the prompts
differing only in the metric-rules block.

The suggestion converts the class to a dataclass and removes the four accessors.
Predictions: `NOM down`, `WMC down`, `LCOM4 down` — **3 of 3 correct**.

```
before: NOM 5, WMC 5, LCOM4 4, interface 5
after:  NOM 1, WMC 1, LCOM4 1, interface 1
```

Behaviour tests: 1 failed, 45 passed, **25 errors**. Flagged `suspicious`
because four public members vanished and were found nowhere else.

Together these two cases say the thing this project exists to say: **prediction
accuracy and design quality are independent.** A model can be completely right
about the numbers in a change that does nothing and in a change that breaks
everything.

### The suggestion prevented its own prediction

`arch` / 20b / `OrderService`. The suggestion lists 24 of the class's 26
methods. `revenue` and `tier_summary` appear in no service, so they stay and
keep touching `_repository`, so the fifth cohesion component survives.

The model predicted `LCOM4 down` at 0.90 and left in the two methods that
prevent it. Result: 1 of 4 — the exact FINDINGS-1 pattern, reproduced on a
different fixture with a different model.

---

## What this means

**Architectural context is worth its tokens.** It is the one intervention with
a clear effect: the models cannot see a layer violation without it and target it
half the time with it. That effect is on *what gets suggested*, not on how
accurately its effect is predicted.

**A one-line piece of context can withdraw an invitation the metric issues.**
The `data_class` label did not make the models better at anything; it stopped
them proposing a change the metric was rewarding. Metric-grounded prompting
inherits the metric's blind spots, and naming them helps.

**Do not use these confidence scores.** Above 0.8 they are worse than chance,
and that is where most of them are.

**Metric improvement is not evidence of anything on its own.** This report
contains three shapes of it: the number improving while the program dies, while
nothing happens, and while the problem relocates. The behaviour gate catches the
first. The Goodhart check catches part of it. Nothing catches the second.

**The classification from FINDINGS-1 was too coarse and its own refutation
condition caught it.** Writing that condition down was worth more than the
classification it protected.

---

## Limitations

**31 predictions, 12 cases, two models.** Every percentage here carries a wide
interval and several per-metric cells hold fewer than six observations. The
patterns — the residue mechanism, the overconfidence above 0.8, the four
identical violation moves — are more reliable than the numbers.

**5b is n=1.** Three repetitions were collected in 5a; only the first was
applied. So 5b cannot separate a model's tendency from a single sampled reply.

**`rejected` measures less than it sounds like.** The tool-side constraint check
verifies three things: whether the named destination layer exists, whether the
move direction is permitted, and whether the model itself declares a violation.
Import-level compliance is **not** measured in v2 — inferring which imports a
sketch would add is not reliable. It comes in v3 from the `apply` diff. Zero
rejections across 23 claims means the models never named an invalid layer, not
that they respected the rules; four violation moves show they did not.

**The person applying the suggestions designed the experiment.** The
narrow-interpretation rule and the mechanical extraction of method bodies
constrain this. It is not eliminated. Where the reading determined the outcome,
the reasoning and the rejected alternatives are recorded in the case's
`INTERPRETATION.md` — five cases needed one.

**Change shape was classified by hand.** The residue mechanism rests on a
judgement about each diff, not an automatic measurement. v3's refactoring type
detection will make it measurable.

**One fixture, one language.** `layered_project` was constructed to exhibit
specific violations and smells. The metrics are adapted to Python: DCC resolves
names rather than types, CAM often cannot be computed, and LCOM4's treatment of
data holders is the subject of one of these findings.

**One model was dropped.** `qwen/qwen3.8-27b` completed 27 of 36 5a runs. The
failures were a hard per-request output ceiling rather than rate limiting, and
the loss was systematic — all three `plain`/`Customer` repetitions failed — so
it could not enter a condition comparison. Its data is committed with that note.
Two observations from it survive as signals: it returned **zero suggestions**
for `Customer` in every architectural condition, and produced the experiment's
only `rejected` suggestions.

**The evaluation is circular by construction.** Models are given metrics as
evidence and judged on those same metrics. The prompt withholds threshold values
to keep them aiming at the design rather than the number, but the circularity is
inherent to the method.

---

## Conclusion

**Answered.** Architectural context changes what models suggest: 1 of 24
suggestions mentions a layer violation without it, 13 of 25 with it. On targets
with no violation it produces no architectural language, so the effect is
specific rather than stylistic.

**Answered, negatively.** Telling models how a metric is computed does not make
them better at predicting it. Accuracy 50% → 53%; stated confidence 0.76 → 0.83.

**Answered.** Confidence is not usable. Calibrated between 0.6 and 0.8, worse
than chance above it, and that is where most predictions are.

**Answered, and it refuted the earlier answer.** Predictability depends on the
shape of the change rather than the identity of the metric. A delegating wrapper
freezes NOM and LCOM4, and models do not anticipate that.

**Answered, with four cases.** A suggestion can name the correct destination
layer, close the violation it targets, and leave the net count unchanged by
opening the same violation one layer down.

**Open.** A metric defined over structure can be satisfied by adding structure
that does nothing. One case in this set does exactly that and passes every check
the tool has. No candidate defence survives inspection.

**What this suggests for tools like this one.** The advice and the prediction
about the advice fail independently, and both fail independently of whether the
code improves. A tool that grounds prompts in metrics gets more relevant advice.
A tool that checks the prediction learns that the advice was the more
trustworthy half. A tool that also checks the violation learns that the
architectural claim was the least trustworthy of the three.

Each of those checks cost one field in a schema and one command. Together they
are the cheapest part of this system and they produced everything above.
