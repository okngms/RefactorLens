# Experiments

Phase 5. Not part of the package — these scripts never ship to users, they
import `rlens` as a library and produce research data.

## Why this exists

The tool asks every model for a **measurable prediction** about its own advice.
Phase 5 asks whether those predictions are any good, and it splits into two
parts with very different costs.

**Part A — collect and analyse advice.** No code is modified. It answers:

- Are suggestions genuinely tied to metrics, or is `rationale_metric_link`
  filled in as a formality?
- How often do models break the JSON contract?
- Ask the same model the same question three times: does it say the same thing?
- Do models differ by more than their own run-to-run variance?

**Part B — apply and verify.** Suggestions are applied by hand and the
predictions are scored. This is where the headline question gets answered, and
it is expensive: every case needs a fresh fixture copy, a careful manual edit,
a behaviour-test run and a `verify` call.

## Protocol

Fixed in advance. **Do not adjust it after seeing results.**

| Setting | Value | Why |
|---|---|---|
| Repetitions | 3 per (model × target) | One sample cannot separate a model difference from run-to-run variance |
| Temperature | 0.2, reported | Comparisons are meaningless without it |
| Targets | Whatever the selector picks, identical across models | The difference must come from the model, not the prompt |
| Application rule | Narrowest possible interpretation | Stops the person applying it from unconsciously rescuing a weak suggestion |
| After every application | `pytest examples/messy_project/tests` | Failure tags the case `broken`; its delta is void and reported separately |

## Running part A

```bash
# See what would happen. Sends nothing, needs no API key.
python experiments/run_advice.py --models openai/gpt-oss-120b --plan

# Collect. Resumable: rerun the same command to continue where it stopped.
python experiments/run_advice.py \
    --models openai/gpt-oss-120b,openai/gpt-oss-20b,qwen/qwen3.8-27b \
    --delay 8

# Analyse whatever is on disk.
python experiments/analyse_advice.py --out experiments/analysis-advice.md
```

Three models × three targets × three repetitions is 27 calls. Free tiers cap
tokens per minute, and each prompt is roughly 2,000 tokens, so `--delay` matters
more than it looks. If a run stops halfway — rate limit, closed laptop, expired
daily quota — rerun the same command. Combinations already on disk are skipped.

Model ids come from your provider's documentation. Nothing is hard-coded.

## Running part B

Three steps, because the middle one is yours.

```bash
# 1. Copy the fixture, measure a baseline, print the suggestion
python experiments/run_verify.py prepare \
    --model openai/gpt-oss-120b --target god:OrderManager

# 2. Read cases/<slug>/SUGGESTION.md and edit cases/<slug>/project/
#    Apply ONE suggestion, narrowest interpretation, change nothing else.

# 3. Run the behaviour tests, re-measure, score the prediction
python experiments/run_verify.py measure \
    --model openai/gpt-oss-120b --target god:OrderManager --applied 1

# When every case is done
python experiments/run_verify.py summarise --out experiments/analysis-verify.md
```

Repetition 1 is always used, fixed in advance so that "pick the one that looks
best" cannot creep in.

Each case directory keeps `baseline.json`, `advice.json`, `applied.diff`,
`result.json` and `result.md`. The project copy itself is gitignored — bulky and
redundant — but the diff is committed, because "I applied the narrowest
interpretation" is a claim and the diff is its evidence.

A case whose behaviour tests fail is marked `broken`. It still appears in the
table with its own numbers, but it is excluded from the overall accuracy: a
refactoring that improves the metrics while breaking the code has not
demonstrated anything about prediction quality.

## Layout

```
experiments/
├── README.md               This file
├── run_advice.py           Part A collection: runs/<model>/<target>/repN.json
├── analyse_advice.py       Part A analysis: compliance, consistency, profile
├── run_verify.py           Part B: prepare → (you edit) → measure → summarise
├── runs/                   Raw advice — committed, it is the data
└── cases/                  Part B cases; project copies gitignored, diffs kept
```

`runs/` is checked in deliberately. `FINDINGS.md` will make claims about model
behaviour; those claims are only worth anything if the raw replies behind them
can be inspected.

## Results

Both parts are done. The report is [FINDINGS.md](../FINDINGS.md); the numbers
behind it are in `analysis-advice.md`, `analysis-verify.md`, `runs/` and
`cases/`.

Two protocol rules were added while running part B, each fixed before the
corresponding results were seen:

- **Repetition 1 always.** Three repetitions were collected in part A; only the
  first was applied, so that "pick the run that looks best" could not creep in.
- **Suggestion 1 always.** Several replies contained more than one suggestion.

Where a suggestion was ambiguous enough that the choice of reading changed the
outcome, an `INTERPRETATION.md` in the case directory records the readings
considered, the one applied, and why.

## What part A cannot tell you

Nothing about whether a prediction was **correct**. A model can be perfectly
consistent, always cite metrics, always predict a direction, and still be wrong
every time. Consistency is not accuracy.

That is part B's job, and one data point already exists — a real suggestion from
`openai/gpt-oss-120b`, applied under the narrow-interpretation rule:

| Metric | Predicted | Actual | |
|---|---|---|---|
| LCOM4 | down | same | miss |
| NOM | down | same | miss |
| WMC | down | down | hit |
| DCC | up | down | miss |

One of four. The diagnosis was right — the class genuinely should be split — but
the model did not know what its own suggestion would do to the numbers.

One case is an anecdote. Phase 5 turns it into a measurement.
