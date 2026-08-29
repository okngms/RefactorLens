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

> **Status: v0.1.0.** `scan` is complete and tested. The AI advisor (`advise`)
> and the verification loop (`verify`) are the next milestones — see
> [Roadmap](#roadmap).

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

The second question is the interesting one.

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
- **It does not send anything anywhere.** `scan` is entirely local. When
  `advise` arrives, it will send selected code to whichever LLM provider you
  configure, and local execution via Ollama will be supported for sensitive
  codebases.
- **Python only.** No Java or C#.

## Roadmap

| Phase | Contents | Version |
|---|---|---|
| 0 | Package skeleton, config, test foundation | — |
| 1 | Metric engine (`scan`) | — |
| **2** | **PyPI release** | **v0.1.0** |
| 3 | AI advisor (`advise`) | v0.2.0 |
| 4 | Verification loop (`verify`) | v0.3.0 |
| 5 | Experiment and findings | v1.0.0 |

Ideas deliberately out of scope live in [FUTURE.md](FUTURE.md).

## Development

```bash
git clone https://github.com/okngms/refactorlens
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
