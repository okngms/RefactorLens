# Working on RefactorLens

Context for an assistant picking this project up cold. Read this before
changing anything; [STRUCTURE.md](STRUCTURE.md) maps the files, this explains
the reasoning behind them.

---

## If you are reading this as a flat file list

When this repository is pasted into a chat context, directory structure is lost:
every file arrives as a bare name. Two consequences to keep in mind.

**Same-named files collide.** There are two `README.md` (root and
`examples/sample_reports/`) and six `__init__.py`. Only one of each survives.

**Paths must come from [STRUCTURE.md](STRUCTURE.md), not guessed.** `model.py`
and `models.py` are different files in different packages, as are
`report/verify.py` and the `verify/` package. When proposing an edit, always
give the full path relative to the repository root.

---

## What this project is

A CLI tool that measures object-oriented design metrics in Python code, feeds
those measurements to an LLM as **evidence** for refactoring advice, and then
checks whether the model's own prediction about its advice came true.

The last part is the point. Plenty of tools show code to an AI. This one asks
the AI to commit to a falsifiable claim — "this change lowers LCOM4 and leaves
DCC unchanged" — and then measures whether it was right.

The research question, in one line: **how accurately do LLMs predict the
structural effect of their own refactoring suggestions?**

---

## Where the project stands

| Phase | Contents | Status |
|---|---|---|
| 0 | Package skeleton, config, test fixture | done |
| 1 | Metric engine (`scan`) | done |
| 2 | First PyPI release | done, v0.1.0 |
| 3 | AI advisor (`advise`) | done |
| 4 | Verification loop (`verify`) | done, released as v0.2.0 |
| 5 | Experiment and `FINDINGS.md` | done, released as v1.0.0 |

488 package tests, 91 fixture behaviour tests, ruff clean. Published on PyPI as
`refactorlens`. All three commands work end to end against a real provider.

---

## Locked decisions — do not reopen

These were argued through and settled. Reopening them wastes time and usually
reintroduces a bug that was already fixed once.

**Python only.** No Java, no C#.

**No auto-fix.** The tool suggests; a human applies. Automatic application would
make the behaviour-test rule unenforceable, and that rule is load-bearing.

**No `history` command.** `reports/` is gitignored, so history lives on one
machine and dies with it. `verify` covers the useful case.

**Only `ast`, no third-party parser.** Known cost: name and type resolution stay
best-effort. Accepted for zero dependencies and full control.

**Model names are never hard-coded.** Provider catalogues change; a baked-in name
breaks quietly when the package ages. Config supplies it, and the error message
when it is missing explains why.

**Two core providers: Groq and Ollama.** Cloud with a free tier, and local for
code that must not leave the machine. Gemini and Anthropic adapters are optional
future work — about thirty lines each against `providers/base.py`.

---

## Invariants — breaking these breaks the project's thesis

Each of these exists for a specific reason and each has tests guarding it. If a
change makes one of them fail, the change is wrong, not the test.

### Raw threshold numbers never reach the model

The prompt shows measured values and a `[WARN]` / `[CRITICAL]` flag, never the
threshold itself. A model that knows the limit can learn to satisfy the number
instead of fixing the design — the Goodhart trap this tool is meant to expose.

Guarded by `tests/test_prompts.py::TestNoRawThresholds` and a CLI-level test.

### `expected_effect` is structured, not prose

A list of `{metric, direction}` where direction is `up` / `down` / `same` and
metric is one of the tool's own names. Phase 4 compares it against the measured
delta **by machine**. Free text would make the entire verify loop impossible.

Invalid entries are dropped and reported as warnings, never silently accepted.

### Schema violations are tagged, not dropped

A suggestion linked to no metric gets the `unlinked` tag and stays in the report.
A reply that cannot be parsed at all gets `unstructured` and its raw text is
kept. Dropping them would make phase 5 unable to measure how often models ignore
the contract.

### Unverifiable predictions are excluded from the accuracy ratio

If the model predicts "CAM down" and CAM was never computable, that is our
measurement gap, not the model's error. Counting it as a miss would bias every
number in phase 5 against the model. They are counted separately and shown.

### Uncomputable metrics report `null`, never zero

Most Python code is unannotated, so CAM often cannot be computed. Forcing a
number would feed the model noise dressed as evidence — which would undermine the
project's own thesis from the inside. `null` propagates through the report, the
terminal (`—`), and the delta logic (not comparable).

### Every report carries `schema_version`

Metric rules change between versions. `verify` refuses to draw conclusions from
two reports whose schema versions differ, because the deltas would be
arithmetically valid and semantically meaningless. Scan reports and advice
reports version independently.

### No metric delta counts unless the behaviour tests pass

This is not theoretical. Extracting the audit-log component from `OrderManager`
produces exactly this:

```
NOM 25→20, WMC 49→42, LCOM4 4→3   →   verdict: improved
6 failed, 85 passed                →   the code is broken
```

Three metrics improved, the tool said "improved", and the program stopped
working. `examples/messy_project/tests/` is the only thing that catches it.

---

## Conventions

**Language.** Everything the user sees is English: terminal output, error
messages, `--help`, README. Docstrings and inline comments are Turkish — they
serve the developer, not the user. Do not mix the two.

**Gold values before implementation.** For every metric, the expected value on
`examples/messy_project` was computed by hand first, then the test written, then
the code. Reversing the order makes the test certify the code's bugs.

**Commit style.** Conventional prefix, imperative subject, and a body that
explains *why* when the reason is not obvious from the diff. Example:

```
fix: never trust the target name reported by the model

The model echoed the schema placeholder "module:Name" verbatim. That
string matches no class, and verify --advice matches advice to classes
by this name, so it would have broken phase 4 silently.
```

**Fixture changes come with test changes.** Every number in
`examples/messy_project/SMELLS.md` is asserted somewhere. Changing the fixture
without updating the gold values makes tests fail for reasons nobody can trace.

**Exit codes.** 0 success, 1 user or environment error, 2 reserved for
click/typer usage errors, 3 not implemented. Do not collide with 2.

---

## Traps already hit — do not step on them again

**rich eats square brackets.** `console.print()` treats `[...]` as markup, so
`self._orders[key]` printed as `self._orders`. Any model-produced or code-derived
text must go through `rich.markup.escape()` or `markup=False`. This failure is
silent: the user reads wrong code without noticing.

**`ast.walk` flattens the tree.** It descends into nested function and class
definitions, so "skip nested definitions" cannot be implemented by `continue`
inside a `walk` loop. `func_metrics._walk_own_scope` exists for this.

**The model echoes schema placeholders.** It returned `"target": "module:Name"`
verbatim — the literal example from the prompt. The requested target is
authoritative; the model's is only recorded as a warning.

**LCOM4 flags well-written data classes.** `Customer` has one accessor per field,
they share no state, so LCOM4 counts three components. This is a documented
property of the metric, not a bug. The fixture was deliberately *not* reshaped to
make the number look better — that would be the exact trap the tool warns about.
WMC and DCC separate real god classes from data holders far more reliably.

**Default `scan.include` is `["."]`, not `["src/"]`.** The old default silently
matched nothing when scanning a path already inside `src/`. The path argument is
the user's choice of scope; config should not narrow it again by default.

**Singular and plural.** "1 modules", "1 suggestions" — caught twice. There are
tests now.

---

## What phase 5 is

A small but controlled experiment, then `FINDINGS.md`.

The protocol is fixed in advance and must not be adjusted after seeing results:

- **n = 3 repetitions** per (model × target) pair, temperature fixed at 0.2 and
  reported. A single sample cannot answer "do models differ" — run-to-run
  variance may exceed the difference between models.
- **Narrowest possible interpretation** when applying a suggestion. Nothing the
  text does not explicitly say gets improved. This stops the person applying it
  from unconsciously rescuing a weak suggestion.
- **Behaviour tests after every application.** Failure means the case is tagged
  `broken`, its metric delta is void, and it is reported as a separate finding
  rather than hidden.

Research questions, in priority order:

1. Do the model's predictions hold? (`expected_effect` accuracy)
2. Are suggestions genuinely grounded in the metrics, or is
   `rationale_metric_link` filled in as a formality?
3. Do applied suggestions improve metrics, or fix one while breaking another?
4. Is there a difference between models that exceeds n=3 variance?

Limitations that must be stated plainly in `FINDINGS.md`: the person applying
the suggestions also designed the experiment; the sample is small; the metrics
are adapted to Python; and "metric improvement" is not the same thing as "design
improvement".

### The experiment is done

See [FINDINGS.md](FINDINGS.md). Headline: 6 of 13 verifiable predictions correct,
split cleanly — 6/6 on unit-local arithmetic metrics (CC, WMC, PARAMS), 0/7 on
structural ones (LCOM4, DCC, NOM, LOC). One case predicted every metric correctly
while breaking 42 behaviour tests.

Two rules were added to the protocol while running it, both fixed before results
were seen: **repetition 1 always**, and **suggestion 1 always**.

### The data point that started it

From a real Groq run against `openai/gpt-oss-120b`, suggestion applied under the
narrow-interpretation rule:

| Metric | Predicted | Actual | |
|---|---|---|---|
| LCOM4 | down | same | miss |
| NOM | down | same | miss |
| WMC | down | down | hit |
| DCC | up | down | miss |

One of four. The model's diagnosis was correct — the class genuinely should be
split — but it did not know what its own suggestion would do to the numbers.
Leaving thin delegating wrappers behind keeps NOM identical and keeps LCOM4 at
four, and moving the collaborators out *lowers* the target's coupling rather
than raising it.

That single case is not a finding. It is the shape of what phase 5 will measure.

---

## How to work on this

Phases are closed in order and each splits into parts. A part is one coherent
idea that leaves the test suite green — that is also the unit of a commit.

Before every commit:

```bash
pytest tests                        # 488
pytest examples/messy_project/tests # 91
ruff check . && ruff format --check .
```

When adding files, give their full paths relative to the repository root. Two
directories are easy to confuse: the root `tests/` tests the package, while
`examples/messy_project/tests/` tests the fixture.

New ideas go to [FUTURE.md](FUTURE.md), not into the current phase.
