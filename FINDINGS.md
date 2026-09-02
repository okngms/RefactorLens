# Findings

Do LLMs predict the structural effect of their own refactoring suggestions?

RefactorLens asks every model to commit to a falsifiable claim — "this change
lowers LCOM4 and leaves DCC unchanged" — and then measures whether it was right.
This is what that measurement produced.

**Short version.** Across 13 verifiable predictions, 6 were correct. But the
misses are not scattered: every prediction about a **unit-local arithmetic**
metric was right (6/6), and every prediction about a **structural or
system-scope** metric was wrong (0/7). The models were also fluent, consistent
and fully compliant with the output contract while being wrong. And in one case
a model predicted every metric correctly by producing a change that deleted the
class's entire public interface.

---

## Setup

| | |
|---|---|
| Models | `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b` (via Groq) |
| Targets | `god:OrderManager` (class), `utils:classify_order`, `utils:deep_transform` (functions) |
| Subject | `examples/messy_project` — a deliberately badly designed fixture with 91 behaviour tests |
| Temperature | 0.2 |
| Tool version | rlens 0.2.0, report schema v1 |

Part A collected 27 advice runs (3 models × 3 targets × 3 repetitions). Part B
applied 6 of them by hand and measured the result (3 models × 2 targets ×
repetition 1).

Raw data: `experiments/runs/` and `experiments/cases/`.

---

## Protocol

Fixed before any data was seen, and not adjusted afterwards.

- **Three repetitions** per (model × target) in part A. One sample cannot
  separate a difference between models from a model's own run-to-run variance.
- **Repetition 1 always**, and **suggestion 1 always**, in part B. Choosing which
  run or which suggestion to apply after seeing them would let "pick the one that
  looks best" into the results.
- **Narrowest possible interpretation.** Nothing the suggestion does not
  explicitly ask for gets improved. Where a suggestion's own text asked for
  something — updating call sites, for instance — that was done; where it did not,
  it was not, even when the omission was obviously an oversight.
- **Behaviour tests after every application.** Failure marks the case `broken`:
  its metric delta is void and it is excluded from the accuracy figure. A
  refactoring that improves every number while breaking the code has not
  demonstrated anything about prediction quality.
- **Method bodies were moved mechanically**, extracted from the original source
  by script rather than retyped, so that "I improved it while applying it" could
  not happen silently.

---

## Part A — what the models said

### Contract compliance was perfect

| Model | Runs | Suggestions | Per run | Unlinked | Repaired | Unparseable |
|---|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | 9 | 12 | 1.33 | 0 | 0 | 0 |
| `openai/gpt-oss-20b` | 9 | 9 | 1.00 | 0 | 0 | 0 |
| `qwen/qwen3.8-27b` | 9 | 17 | 1.89 | 0 | 0 | 0 |

Every suggestion named at least one metric. Every suggestion carried a
prediction. No reply needed a repair round, and none failed to parse. The
structured prompt works: models will comply with a strict output contract when
one is stated.

This matters for interpreting the rest. The failures reported below are **not**
failures to follow instructions.

### Models echoed the schema placeholder in 7 of 27 runs

In a quarter of runs the model returned `"target": "module:Name"` — the literal
example from the prompt — instead of the actual target. RefactorLens overrides
this and records a warning, a fix added in phase 3 after observing it once.

Without that fix, those seven runs would have failed to match any class during
verification, silently. A one-line defect in prompt design cost 26% of the
sample, and only showed up because something was checking.

### Repetitions agreed with each other, mostly

Mean Jaccard similarity between the three repetitions of the same (model,
target) pair ranged from 0.64 to 1.0 for cited metrics. Models are largely
consistent with themselves at temperature 0.2, though not perfectly: on
`utils:deep_transform`, `gpt-oss-120b` cited different evidence across runs
(0.639).

Consistency is not accuracy. A model can cite the same metrics every time and be
wrong about them every time — which is roughly what happened.

### Trade-off acknowledgement separated the models

A suggestion that predicts both `up` and `down` admits it will make something
worse.

| Model | Suggestions | Acknowledging a trade-off | Rate |
|---|---|---|---|
| `openai/gpt-oss-120b` | 12 | 9 | 0.75 |
| `qwen/qwen3.8-27b` | 17 | 6 | 0.35 |
| `openai/gpt-oss-20b` | 8 | 2 | 0.25 |

A three-fold spread. The smallest model was the most likely to promise that
every metric would improve at once. Part B shows where that leads.

---

## Part B — whether they were right

| Model | Target | Status | Hits | Misses | Unverifiable | Accuracy |
|---|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | `god:OrderManager` | ok | 1 | 3 | 0 | 25% |
| `openai/gpt-oss-120b` | `utils:classify_order` | ok | 1 | 0 | 1 | 100% |
| `openai/gpt-oss-20b` | `god:OrderManager` | **broken** | 4 | 0 | 0 | (100%) |
| `openai/gpt-oss-20b` | `utils:classify_order` | ok | 2 | 0 | 0 | 100% |
| `qwen/qwen3.8-27b` | `god:OrderManager` | ok | 1 | 3 | 0 | 25% |
| `qwen/qwen3.8-27b` | `utils:classify_order` | ok | 1 | 1 | 0 | 50% |

**6 of 13 verifiable predictions were correct (46%).** The broken case is
excluded.

### The split is the finding

| Metric | Predicted | Correct | |
|---|---|---|---|
| CC | 3 | 3 | 100% |
| WMC | 2 | 2 | 100% |
| PARAMS | 1 | 1 | 100% |
| **subtotal** | **6** | **6** | **100%** |
| NOM | 2 | 0 | 0% |
| LCOM4 | 2 | 0 | 0% |
| DCC | 2 | 0 | 0% |
| LOC | 1 | 0 | 0% |
| **subtotal** | **7** | **0** | **0%** |

Not a gradient. A clean partition, across three different models.

What distinguishes the two groups is **what the change leaves behind**.

CC, WMC and PARAMS are **subtractive**: take work out of the unit and the value
falls, with nothing stepping into its place. Predicting them requires knowing
only what was removed. The models got all six right.

The other four are **residue-dependent**: the value turns on what remains. A
delegating wrapper stands in for the method that left, a new attribute stands in
for the old ones, a new dependency stands in for the ones that moved out. The
models got all seven wrong.

(These labels are a hypothesis derived from 13 predictions, not a settled
taxonomy — one to three observations per metric. Later reports state per-metric
results first and the grouping second, so the grouping can be refuted.)

Every miss was also a scope error: the models predicted the effect on the
*codebase* while the metric measures the *entity*.

- **`DCC up`** (twice, both wrong). The models saw new classes entering the
  system and concluded coupling would rise. DCC is per class: extracting
  collaborators moved five dependencies out of `OrderManager` and added one back,
  so its coupling fell or stayed flat.
- **`LOC same`** (wrong). The model reasoned that the lines were relocated, not
  deleted, so the total was preserved. LOC is per function: `classify_order` went
  from 25 lines to 6.
- **`NOM down`** (twice, both wrong). The suggestions themselves specified that
  `OrderManager` would keep delegating wrappers — one of them wrote a wrapper out
  as an example — yet both predicted the method count would fall. It did not: 25
  methods stayed 25.
- **`LCOM4 down`** (twice, both wrong). Splitting responsibilities feels like it
  must improve cohesion. But the wrappers left behind touch `self._repo`,
  `self._pricing`, `self._audit`, `self._notifier` — four disjoint attributes,
  so the method–attribute graph still has four components. LCOM4 stayed 4.

The `NOM` misses are the sharpest. The information needed was not missing or
subtle: it was in the model's own sketch, two paragraphs above its own
prediction.

### Target type predicts accuracy

Function targets: 4 of 5 correct. Class targets: 2 of 8.

Consistent with the split above — function metrics are mostly unit-local
arithmetic, class metrics mostly structural.

---

## Cases

### The model that was right about everything and destroyed the code

`openai/gpt-oss-20b` on `god:OrderManager`. Predicted `LCOM4 down, DCC down,
NOM down, WMC down`. All four came true.

**42 of 91 behaviour tests failed.**

The suggestion instructed that all 25 methods be moved into four new classes. It
never said what should remain of `OrderManager` — while claiming, in the same
paragraph, that the change would lower LCOM4 and DCC "for OrderManager". Applied
as written, the class was left with a constructor and nothing else. Every metric
it named improved, because an empty class scores perfectly on all of them.

Had the tool measured only metrics, this would have been the most successful case
in the experiment: 100% prediction accuracy alongside an `improved` verdict. The
behaviour tests are the only thing that caught it.

This is not a constructed example. It is Goodhart's law arriving unprompted from
a real model on the first attempt, and it is the strongest argument in this
report for the rule that no metric delta counts unless the tests still pass.

*(The interpretation choice here materially determined the outcome and is
documented in that case's `INTERPRETATION.md`. Reading the suggestion as
implying a delegating façade — which the text never states, unlike the 120b
suggestion for the same target — would have produced a working program and a
different result.)*

### Correct diagnosis, wrong arithmetic

`openai/gpt-oss-120b` on `god:OrderManager`, and `qwen/qwen3.8-27b` on the same
target, produced almost identical outcomes: 1 of 4.

Both diagnoses were correct and well argued. `OrderManager` genuinely does hold
four disjoint responsibilities; the extraction each proposed is the right change
to make. A human reviewer reading either suggestion would learn something true
about the code.

Both were wrong about what their own change would measure. The design judgement
and the metric judgement came apart completely.

### Where the models were reliable

`openai/gpt-oss-20b` on `utils:classify_order`: 2 of 2. Predicted `CC down` and
`PARAMS down` after bundling seven parameters into a dataclass and extracting
two predicates. Both fell.

Nothing structural was involved. Fewer branches, fewer parameters, and the
metric counts exactly those things.

---

## Limitations

State plainly, because the numbers above are small enough to be misread.

**Thirteen predictions.** Six cases. Any percentage here carries an enormous
confidence interval, and the per-metric cells hold one or two observations each.
The *pattern* — unit-local right, structural wrong — is what carries weight, not
the 46%.

**Part B is n=1.** The three repetitions were collected in part A but only
repetition 1 was applied. Applying all three would have tripled the manual work.
So part B cannot separate a model's tendency from a single sampled reply.

**The applier designed the experiment.** The narrow-interpretation rule and the
mechanical extraction of method bodies constrain this, and the applied diffs are
committed so the claim can be checked. It is not eliminated.

**Interpretation was sometimes a judgment call.** Two cases required deciding
what a suggestion meant, and both decisions are documented in the case
directories with the reasoning and the rejected readings. In one case the choice
changed the outcome substantially.

**One fixture, one language.** `messy_project` was built to exhibit specific
smells. Results on real code, or in a language where these metrics are less
adapted, may differ.

**The metrics are adapted to Python.** CAM needs annotations and often reports
nothing; DCC resolves names rather than types; LCOM4 flags well-written data
classes as uncohesive. These adaptations are documented in the README, and they
shape what "correct prediction" means here.

**Metric improvement is not design improvement.** The tool measures the former.
The 20b case shows how far the two can diverge.

**The evaluation is circular by construction.** Models are given metrics as
evidence and then judged on those same metrics. The prompt withholds the
threshold values specifically to keep models aiming at the design problem rather
than at a number, but the circularity is inherent to the method and cannot be
designed away.

---

## Conclusion

**Answered.** Models comply with a structured output contract reliably — 27 of
27 runs, three models, zero violations. They are also reasonably consistent with
themselves at low temperature.

**Answered.** Predictions about **subtractive** metrics — where the change
removes something and nothing replaces it — were correct 6 times out of 6.
Predictions about **residue-dependent** metrics were wrong 7 times out of 7. The
failure is specific: the models do not account for what their own change leaves
behind, and they reason about the codebase while the metric measures the entity.

**Answered, with one case.** A model can be entirely correct about its own
predictions while destroying the code. Metric verification alone is insufficient;
behaviour verification is not optional.

**Not answered.** Whether models differ from one another. The trade-off
acknowledgement spread (0.75 / 0.35 / 0.25) is suggestive, but part B was n=1
and the three models' accuracy figures on class targets were nearly identical.

**What this suggests for tools like this one.** A model's refactoring advice and
a model's prediction about that advice are separable, and they failed
separately here: the diagnoses were sound while the arithmetic was not. A tool
that grounds prompts in metrics gets useful diagnoses. A tool that also checks
the prediction finds out that the diagnosis was the trustworthy half.

Making models predict, and then checking, cost one prompt field and one command.
It is the cheapest part of this system and it produced everything above.
