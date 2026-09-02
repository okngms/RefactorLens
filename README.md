# RefactorLens

**Metric-grounded code review for Python.** RefactorLens computes
object-oriented design metrics from your codebase and reports them as evidence
— not opinions.

```bash
pipx install refactorlens
rlens scan .
```

```
your-project/src — 12 modules, 14 classes, 68 functions

Class metrics
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━┳━━━━━┳━━━━━━━┳━━━━━┳━━━━━━┳━━━━━━┓
┃ Class                       ┃ NOM ┃ WMC ┃ LCOM4 ┃ DCC ┃  DAM ┃  CAM ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━╇━━━━━╇━━━━━━━╇━━━━━╇━━━━━━╇━━━━━━┩
│ orders:OrderManager         │  25 │  49 │     4 │   8 │ 1.00 │    — │
│ reporting:ReportBuilder     │   6 │   7 │     2 │   0 │ 1.00 │    — │
│ models:Customer             │   6 │   6 │     3 │   0 │ 0.20 │ 1.00 │
└─────────────────────────────┴─────┴─────┴───────┴─────┴──────┴──────┘

— CAM not computed for 2 classes (no annotated parameters)
8 items over threshold.
```

> **Status: v1.0.0.** All three commands work, and the experiment they were
> built for is done — see [FINDINGS.md](FINDINGS.md).

## Why this exists

Most "let an AI review my code" tools hand the model raw source and hope for the
best. RefactorLens is built on a different bet: **give the model measurements,
then check its work.**

Two layers make that concrete.

**Metric-grounded prompting.** Before asking a model for advice, compute the
numbers. A suggestion that says "this class has four disjoint responsibilities
(LCOM4 = 4) and touches eight other classes (DCC = 8)" is checkable. A
suggestion that says "this feels messy" is not.

**The verify loop.** Every suggestion must come with a *measurable prediction* —
"this change lowers LCOM4 and leaves DCC unchanged". After the change is
applied, the metrics are recomputed and two questions get answered at once: did
quality actually improve, and **was the model's own prediction correct?**

The second question is the interesting one, and it has an answer now.

Across 13 verifiable predictions from three models, 6 were correct. The misses
are not scattered. Where the change removes something and nothing replaces it,
the models were right every time (CC, WMC, PARAMS — 6 of 6). Where the value
depends on what the change leaves behind — a delegating wrapper, a new
dependency — they were wrong every time (NOM, LCOM4, DCC, LOC — 0 of 7).

In one case a model predicted all four of its metrics correctly by producing a
change that deleted the class's entire public interface. Only the behaviour
tests caught it. Full report: [FINDINGS.md](FINDINGS.md).

## Install

```bash
pipx install refactorlens     # recommended: isolated environment
pip install refactorlens      # or into your current environment
```

Requires Python 3.11 or newer. RefactorLens is a CLI tool rather than a library,
so `pipx` is the better fit.

## Usage

```bash
rlens scan .                          # scan the current project
rlens scan src/ --no-report           # print tables only, write nothing
rlens scan . --fail-on-violation      # exit 1 if anything is over threshold
rlens --version
```

`scan` prints two tables and writes a JSON report to `reports/`:

- **Class metrics** — every class, worst first
- **Functions over threshold** — only the ones that exceed a limit, because
  printing every function makes the output useless

Values shown as `—` were **not computed**, which is different from zero. The
footnote below the table says why.

### The full loop

The three commands are meant to be used in sequence.

```bash
# 1. Measure, establishing a baseline
rlens scan .

# 2. Ask for advice, grounded in those measurements
rlens advise .

# 3. Apply one suggestion by hand, then run YOUR tests

# 4. Re-measure and score the model's prediction
rlens verify . --applied "orders:OrderManager=1" \
                --advice reports/advice-20260829-153748.json
```

Step 3 is not optional. A refactoring that improves every metric while breaking
the code is a regression, not an improvement — `verify` reminds you of this in
every report, but it cannot check it for you.

### Asking for advice

```bash
rlens advise .                       # the 3 worst targets
rlens advise . --top-n 1             # just the worst one
rlens advise . --dry-run             # print the prompt, send nothing
rlens advise . --provider ollama --model llama3
```

`--dry-run` needs no API key and no network. It prints exactly what would be
sent, which is the honest way to decide whether you want to send it.

Configure the provider in `rlens.yaml` and put the key in `.env`
(see `.env.example`):

```yaml
provider:
  name: groq          # groq (cloud) or ollama (local)
  model: <model-id>   # from your provider's docs
```

Model names are never hard-coded. Providers change their catalogues often, and a
baked-in name breaks quietly when the package ages.

Every suggestion must name at least one metric and state a **measurable
prediction** — for example "LCOM4 down, DCC up". Suggestions that name no metric
are kept but tagged `unlinked` rather than dropped, so you can see how often the
model ignores the rule.

### Verifying

```bash
rlens verify .                                   # deltas only
rlens verify . --advice reports/advice-....json  # plus prediction scoring
rlens verify . --applied "orders:OrderManager=1" --advice ...
rlens verify . --fail-on-regression              # exit 1 if anything got worse
```

Without `--before`, the most recent scan report is used as the baseline.

`--applied` matters more than it looks. If a target got three suggestions and you
applied one, scoring all three punishes the model for advice you never followed.

Output looks like this:

```
god:OrderManager   improved   WMC 49→34, DCC 8→4
god:OrderRepository  added

Metric   Predicted  Actual
LCOM4    down       same     ✗
NOM      down       same     ✗
WMC      down       down     ✓
DCC      up         down     ✗

prediction accuracy: 1/4 (25%)
```

Two answers at once: the code did get measurably better, and the model was wrong
about three of its four predictions.

Predictions that cannot be checked — a metric that was never computable, a class
that no longer exists — are counted separately and **excluded** from the ratio.
Treating "we could not measure it" as "the model was wrong" would bias every
number.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Config error, unwritable report, or `--fail-on-violation` triggered |
| 2 | Invalid command usage |

## Configuration

RefactorLens works with no configuration. To customise, put `rlens.yaml` in your
project root — it is searched for upward from the scanned path.

```yaml
scan:
  include: ["."]                       # scan everything under the given path
  exclude: ["tests/", ".venv/", "migrations/"]
  output_dir: reports/

metrics:
  cam_min_annotation_coverage: 0.7     # below this, CAM reports null

thresholds:
  cyclomatic_complexity: {warn: 10, critical: 20}
  max_params: {warn: 5}
  max_nesting: {warn: 4}
  lcom4: {warn: 2, critical: 4}
  dcc: {warn: 7}
  wmc: {warn: 50}
  nom: {warn: 20}
```

Unknown keys are an **error**, not a warning. A typo like `max_nestings` would
otherwise leave you silently running on defaults.

## Metric definitions and adaptations

The metrics are inspired by the QMOOD family and classic complexity measures.
**Only a subset of QMOOD is implemented; this is not a complete QMOOD tool.**

Python is dynamically typed, so several object-oriented metrics can only be
computed by adaptation. Those adaptations are documented here rather than
hidden.

### Shared rule: which methods count

All six class metrics operate on the same method set: methods defined directly
in the class body, excluding dunder methods. `@property`, `@staticmethod` and
`@classmethod` are included. Nested functions and nested classes are not.

`__init__` is excluded, and this matters most for LCOM4: a constructor touches
every attribute by definition, so counting it would merge every class into a
single component and make the metric useless. Classic LCOM4 excludes
constructors for the same reason.

### Class-level metrics

| Metric | What it counts | Adaptation |
|---|---|---|
| **NOM** | Methods in the class | Dunders excluded |
| **WMC** | Sum of cyclomatic complexity over those methods | Same method set as NOM, for consistency |
| **LCOM4** | Connected components in the method–attribute graph | See limitation below |
| **DAM** | Ratio of private attributes | Reported twice: `dam` counts `_x` and `__x`; `dam_strict` counts only `__x` |
| **DCC** | Distinct project-internal classes referenced | Name-based resolution; see below |
| **CAM** | Mean ratio of each method's parameter types to the class-wide set | Computed only when annotation coverage is sufficient |

**Attribute set (used by DAM and LCOM4)** is the union of: class-level
assignments and annotations, `self.x = ...` in *any* method (not just
`__init__`), and names listed in `__slots__`. Names that are only ever read are
not attributes.

**DCC resolution is best-effort.** Python has no static type information, so a
name appearing in a class body is counted as a reference if it matches a class
defined anywhere in the project. A local variable that shares a name with a
class will be counted. Standard-library and third-party classes are not counted.

**CAM is conditional.** The classic definition uses parameter *types*. Parameter
*names* measure something else entirely and would make the result incomparable
to the literature, so name similarity is never used as a fallback. Most Python
codebases are unannotated; forcing a number out of them would feed the model
noise dressed up as evidence. If annotation coverage falls below
`metrics.cam_min_annotation_coverage` (default 0.7), CAM reports `null` and the
report records why.

### Known limitation: LCOM4 and data classes

LCOM4 flags well-written data-holder classes as uncohesive. A class with one
accessor per field — `rename` touching `name`, `promote` touching `tier` — has
methods that share no state, so LCOM4 counts them as separate responsibilities.

This is a property of the metric, not a bug, and it is well documented in the
literature. RefactorLens reports the number as measured rather than
special-casing it away. When reading a report, treat a high LCOM4 on a small
class as a question rather than a verdict; **WMC and DCC separate genuinely
overloaded classes from plain data holders far more reliably.**

### Function-level metrics

Cyclomatic complexity counts `if`/`elif`, loops, `except` handlers, ternaries,
each additional `and`/`or` operand, comprehension clauses, and `match` cases.
`else`, `with`, and `try` itself add nothing — they do not branch execution.

Nesting depth treats `elif` chains as flat: a ten-branch `elif` is not ten
levels deep.

Nested function definitions are never entered. A function containing a closure
does not inherit the closure's complexity.

## What RefactorLens does not do

- **It does not run your code.** Files are parsed with `ast`, never executed.
- **It does not fix anything.** `scan` measures; future versions will suggest.
- **`scan` and `verify` send nothing anywhere.** They are entirely local.
  `advise` sends the selected class or function, plus the signatures of the
  project classes it depends on, to whichever provider you configure. Use
  `--dry-run` to see exactly what would go out, or the Ollama provider to keep
  everything on your machine.
- **Python only.** No Java or C#.

## Roadmap

| Phase | Contents | Version |
|---|---|---|
| 0 | Package skeleton, config, test foundation | — |
| 1 | Metric engine (`scan`) | — |
| 2 | First PyPI release | v0.1.0 |
| 3 | AI advisor (`advise`) | — |
| 4 | Verification loop (`verify`) | v0.2.0 |
| **5** | **Experiment and findings** | **v1.0.0** |

Phases 3 and 4 shipped together in v0.2.0. The phase 5 experiment lives in
[`experiments/`](experiments/), with the raw data committed alongside it.

Ideas deliberately out of scope live in [FUTURE.md](FUTURE.md).
[STRUCTURE.md](STRUCTURE.md) maps the codebase file by file, and
[AGENTS.md](AGENTS.md) records the locked decisions and invariants behind it.

## Development

```bash
git clone https://github.com/<user>/refactorlens
cd refactorlens
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest tests                        # the package's own tests
pytest examples/messy_project/tests # the fixture's behaviour tests
ruff check . && ruff format --check .
```

`examples/messy_project` is a deliberately badly designed sample project used as
the test fixture; every metric is verified against hand-computed gold values on
it. See [SMELLS.md](examples/messy_project/SMELLS.md) for the inventory of
intentional smells and the reasoning behind each.

Its behaviour test suite exists for a specific reason: from phase 4 onward,
refactoring suggestions get applied by hand. If a refactoring breaks the code,
the metrics improve while the program stops working. The rule is therefore
absolute — **no metric delta counts unless the behaviour tests pass.**

## Licence

MIT
