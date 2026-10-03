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

> **Status: v2.3.0 released.** Four core commands: `scan` measures,
> `arch` maps layers and violations, `advise` asks an LLM for advice grounded in
> both, and `verify` checks whether the model's own prediction came true. A
> fifth, `explain`, is experimental. v2.1 checked every metric against a
> 26-project calibration corpus; v2.2 added Python-specific descriptive
> measures (dynamic opacity, duck-typing coupling); see the
> [changelog](https://github.com/okngms/RefactorLens/blob/main/CHANGELOG.md).
> Two experiments are done — [FINDINGS.md](https://github.com/okngms/RefactorLens/blob/main/FINDINGS.md) and
> [FINDINGS-2.md](https://github.com/okngms/RefactorLens/blob/main/FINDINGS-2.md).

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
tests caught it. Full report: [FINDINGS.md](https://github.com/okngms/RefactorLens/blob/main/FINDINGS.md).

**v2 asked what changes that.** Giving the model its architectural context works:
without it, 1 of 24 suggestions on a class with a layer violation mentions the
problem; with it, 13 of 25 do. Telling it how the metrics are computed does not:
accuracy moved from 50% to 53% while stated confidence rose from 0.76 to 0.83.

The confidence turns out to be unusable. Between 0.6 and 0.8 the models are
almost perfectly calibrated; above 0.8, where most predictions sit, they are
worse than chance — stated 0.89, actual 0.44.

And four suggestions across two models claimed to restore a layer boundary.
All four closed the violation on the target and opened the same one on the new
class. Full report: [FINDINGS-2.md](https://github.com/okngms/RefactorLens/blob/main/FINDINGS-2.md).

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

The **Smells** column labels patterns that need more than one number. Each
label carries its evidence in the JSON report:

| Label | When |
|---|---|
| `god_class` | NOM ≥ 20, WMC ≥ 50 and LCOM4 ≥ 3 together; not for interfaces (at least half the methods are stubs) |
| `data_class` | NOM ≤ 5, WMC ≤ NOM + 2, DAM ≥ 0.5, and at least 70% of public methods are accessors |
| `feature_envy_candidate` | a method touches one other object at least twice as often as its own class (and at least 3 times) |
| `long_method` | CC and lines of code both over their limits |
| `too_many_params` | PARAMS over its limit, except framework entry points (click/typer commands, route handlers, fixtures) |
| `layer_misfit` | the module breaks a layer rule and the class's DCC is over the limit for its layer |

`--no-arch` skips layer analysis and violations. Every smell except
`layer_misfit` and the public interface (which `verify` uses) are still
computed.

### Mapping the architecture

```bash
rlens arch .                        # layers, violations, module coupling
rlens arch . --fail-on-violation    # exit 1 on a firm violation (useful in CI)
```

`arch` assigns each module to a layer — from `arch.layers` in `rlens.yaml`, or
from an existing `import-linter` layers contract — and checks every import
against the layer rules (see *Configuration*). A declaration always wins; a
module that matches no declared prefix is `unknown` and takes part in no
layer rule.

| Code | Alias | Meaning |
|---|---|---|
| `LV-DIR` | back-call | an import against the direction the scheme allows |
| `LV-SKIP` | skip-call | a layer reaches past its neighbour |
| `LV-CYCLE` | cyclic | modules import each other in a cycle |
| `LV-LEAK` | leak | a public signature exposes a type from a lower layer (visible only where annotated) |

The aliases follow the names used in the architecture-erosion literature
(Sarkar et al.; HUSACCT). `LV-CYCLE` corresponds to Arcan's cyclic-dependency
smell. RefactorLens reports Ca, Ce and instability per module but raises no
unstable-dependency smell from them, and it does not detect hub-like
dependencies.

The `Certainty` column separates `firm` from `tentative` violations; only firm
ones count for `--fail-on-violation`. Today every violation is firm:
`tentative` is reserved for layers that were inferred rather than declared,
and inference is not implemented yet. Without any declared layer, `arch` still
reports import cycles and module coupling, and says where to declare layers.

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
(see `env.example` in the repository):

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

**Suspicious improvements.** When a class's metrics improve while its public
interface shrinks, `verify` flags the change as `suspicious`: part of the
improvement may come from deleting work rather than restructuring it. Every
member that disappeared is first searched for in the rest of the project;
found elsewhere, it counts as `moved` (an Extract Class does exactly this) and
raises no suspicion. Only members that are gone everywhere count as `deleted`.
This is a question, not a verdict: deleting dead code shrinks the interface
too, and it cannot see a broken call site. The behaviour tests decide. With
the default `verify.treat_suspicious_as_regression: true`,
`--fail-on-regression` also fails on a suspicious change.

**Calibration.** A suggestion may state a `confidence` for each prediction.
`verify` then reports a Brier score and the expected calibration error (ECE):
does the model's "80% sure" come true about 80% of the time? A prediction
without a confidence is left out of both and counted separately; it is never
treated as low confidence.

`verify` refuses to compare reports with different scan schema versions: the same
code produces different numbers under different metric rules. After upgrading
RefactorLens, regenerate the `before` report with the new version. Schema 3
changed the meaning of `loc`, of `lcom4` for classes without methods (`null`,
previously `0`) and of `dcc`; see
[v2-tanim-kararlari.md](https://github.com/okngms/RefactorLens/blob/main/docs/v2-tanim-kararlari.md).

### Applying a suggestion on a branch (new, v2.4)

```bash
rlens apply . --advice reports/advice-....json          # suggestion 1 of the only target
rlens apply . --advice ... --target app.orders:Orders --suggestion 2
rlens apply . --advice ... --dry-run                    # print the patch request, send nothing
```

`apply` asks the model for a patch that implements one suggestion, applies it
in a separate git worktree, runs **your** test command there, and measures
the result the way `verify` does. It needs a git repository with a clean
working tree and a test command in `rlens.yaml`:

```yaml
tests:
  command: "pytest -q"     # runs at the repository root of the worktree
  timeout: 300
apply:
  allow_files: []          # files besides the target's own file the patch may touch
  keep_failed: false       # keep a failed worktree for inspection
  max_output_tokens: 16384 # patches are longer than advice replies
```

What it guarantees:

- Your working tree, your branch and your HEAD never change. The patch lands
  on a new branch, `rlens/<run-id>/<target>`, which you review and merge
  yourself. **RefactorLens never merges.**
- The patch may touch only the target's file and `apply.allow_files`; the
  commit contains only the files the patch touched.
- If your tests fail, the worktree and the branch are deleted and the outcome
  is `broken`: no metric delta counts unless the behaviour tests pass.
- The model gets one repair attempt for a reply that cannot be applied, and
  every reply is kept in the report.
- The patch request carries the suggestion's text but not the model's own
  predictions, so the patch cannot be written to make them come true.

Outcomes are `verify`'s (`improved`, `regressed`, `mixed`, `unchanged`,
`suspicious`) plus `broken` (tests failed), `rejected` (no applicable patch)
and `no_gate` (see below). Reports go to `reports/apply-*.json` and `.md`.

The report also names what the patch did: `extract_method`, `move_method`,
`extract_class`, `inline`, `rename`, or `unknown`, each with a confidence,
found by comparing the code before and after with `ast`. When a member moved
but a thin method delegating to it stayed behind, the report says so —
those wrappers are why NOM and LCOM4 often stay put after an Extract Class:

```
extract_class OrderService → PricingService (0.95; delegating wrappers left: apply_tax, ...)
```

**A project without tests.** If `tests.command` is not set and
`chartests.enabled_when_no_tests` is true (the default), `apply` first asks the
model for *characterization tests*: pytest tests that record what the target
class does today. They run on the unchanged code; every test that fails is
dropped, the rest must pass a second run too, and the pass rate is reported.
Those tests then gate the patch. If none of them passes, no patch is requested
(`no_gate`). The tests live only in the worktree and are never committed.

```bash
rlens chartests . --target inventory.stock:Stock   # just the tests, kept if they pass
```

`rlens chartests` writes the surviving tests to `reports/chartests-*.py`;
moving them into your test suite is up to you. Characterization tests pin
down current behaviour, bugs included; they do not claim it is correct.

```yaml
chartests:
  enabled_when_no_tests: true
  per_method_cases: 3
  python: python    # your project's Python, with pytest installed
```

`chartests.python` is your project's interpreter, not RefactorLens's: when
RefactorLens is installed with pipx, your dependencies are not in its
environment.

### Feeding the result back: `loop` (new, v2.4)

```bash
rlens loop . --target app.orders:Orders               # up to loop.max_iter (3) iterations
rlens loop . --target app.orders:Orders --max-iter 5
rlens loop . --target app.orders:Orders --dry-run     # print the first request, send nothing
```

`loop` runs `advise` → `apply` (suggestion 1, always) → measure, then asks
again with a feedback block about the previous attempt: which predictions
held and which missed (directions only — never threshold numbers), whether
the tests passed, whether public members were deleted. Every iteration starts
from HEAD; changes do not build on each other, so the question is whether
feedback changes the predictions for the same code. It stops when every
prediction held and the tests passed, at the iteration limit, or when the call
budget runs out.

The report (`reports/loop-*.json` and `.md`) gives, per iteration and overall:
prediction accuracy, whether the tests passed, the suspicious rate, the Brier
score of the stated confidences, and the number of calls. Each iteration that
passes the tests leaves its own branch.

### Comparing two revisions: `diff` and the ratchet (new, v2.4)

```bash
rlens diff origin/main..HEAD                          # tables
rlens diff origin/main..HEAD --format pr-comment      # markdown for a pull request
rlens diff origin/main..HEAD --fail-on new-violation  # CI gate: new findings only
rlens baseline update                                 # accept today's findings
```

`diff` checks out both revisions in temporary worktrees outside your
repository, scans them with today's config, and reports what `verify`
reports — metric changes, violation and smell changes, suspicious
improvements — plus the refactorings detected in the changed files. It calls
no model.

A *finding* is an architecture violation, a smell, or a value over its
threshold. `--fail-on new-violation` fails only on findings that are not
accepted: by `.rlens-baseline.json` when it exists, otherwise by the base
revision. That is a ratchet: an existing codebase is not blocked by what it
already has, but nothing new gets in. `--fail-on regression` fails when a
metric got worse. A GitHub Action that comments on pull requests lives in
[`action/`](https://github.com/okngms/RefactorLens/tree/main/action).

### Reading the measurements back (experimental)

```bash
rlens explain .                      # measure now, then describe
rlens explain . --report reports/scan-....json
rlens explain . --dry-run            # print the prompt, send nothing
rlens explain . --no-llm             # fixed templates, no model, no key
```

`explain` asks the model to describe what the measurements say about the code
as it stands — which metrics point at the same structure, which classes share a
pattern — with no advice and no refactoring. Its output is **not scored** and
never enters an accuracy figure: a sentence like "this class carries too many
responsibilities" can be fluent and wrong, and nothing checks it. Each
observation is tagged with the metrics it rests on; one that names none is
marked `unlinked`.

It is experimental for a measured reason: in two runs the model still graded
values ("high", "low") it had been told not to grade, and its observations
mostly restated the table.

`--no-llm` needs no provider and no key. It translates the report with fixed
sentence templates: each threshold a value meets, with the metric's
definition; each smell with its evidence; and every metric that could not be
computed, with the reason. The same report always gives the same text, and it
uses no grading words. It writes `explain-template-*.json` and `.md`, and none
of it is ever sent to a model.

### Machine-readable output

```bash
rlens scan . --format json | jq '.modules[].classes[] | select(.lcom4 > 5) | .name'
rlens arch . --format json
rlens verify . --format markdown > verification.md
```

`--format` prints the report itself on stdout instead of the tables: `json`
for `scan`, `arch` and `verify`, and `markdown` for `verify`. It is the same
content as the report file, which is still written unless `--no-report` is
given. Status lines go to stderr so the output can be piped. `advise` and
`explain` write their JSON and markdown to files only.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Config error, unwritable report, or a CI gate triggered (`--fail-on-violation`, `--fail-on-regression`) |
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
  lcom4: {warn: 5, critical: 10}
  dcc: {warn: 7}
  wmc: {warn: 50}
  nom: {warn: 20}
```

The defaults are checked against a 26-project calibration corpus: in a typical
project each warning level flags at most about 7% of functions or classes, and
each critical level about 1%. LCOM4 was `{warn: 2, critical: 4}` before this
change; at 2 it flagged a third of all classes. Measurement:
[thresholds.md](https://github.com/okngms/RefactorLens/blob/main/experiments/hardening/thresholds.md).

Unknown keys are an **error**, not a warning. A typo like `max_nestings` would
otherwise leave you silently running on defaults.

Layers are declared by path prefix, relative to the directory you scan. A
declaration always wins over inference:

```yaml
arch:
  layers:
    presentation: ["src/myapp/cli.py", "src/myapp/views/"]
    application: ["src/myapp/services/"]
    domain: ["src/myapp/domain/"]
    infrastructure: ["src/myapp/db/", "src/myapp/clients/"]
  scheme:                              # the default, shown in full
    layers: [presentation, application, domain, infrastructure]
    allowed:
      presentation: [application, domain]
      application: [domain]
      infrastructure: [domain]
      domain: []
    allow_skip: false
```

The default scheme assumes dependencies point inward, with infrastructure
implementing interfaces the domain owns. In a classic layered project where
services call a database client directly, every such call is a violation;
if that is your design, add `infrastructure` to `application`'s `allowed`
list. RefactorLens's own declaration keeps the default and reports those
calls (see *RefactorLens on itself*).

A threshold can differ per layer. Coupling that is normal for a presentation
module can be a warning sign in the domain:

```yaml
thresholds:
  by_layer:
    domain:
      dcc: {warn: 4}
```

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
| `annotation_coverage` | Share of the class's method parameters that carry a type annotation | Descriptive only: no threshold, no smell; `null` when there are no parameters |

**Attribute set (used by DAM and LCOM4)** is the union of: class-level
assignments and annotations, `self.x = ...` in *any* method (not just
`__init__`), and names listed in `__slots__`. Names that are only ever read are
not attributes.

**DCC resolution is best-effort.** Python has no static type information, so a
name appearing in a class body is counted as a reference if it matches a class
defined anywhere in the project. String annotations (`"Order"`) and import
aliases from project modules (`from models import Order as O`) are resolved;
`Literal[...]` values are not references.

A class's own nested classes are part of the class, not dependencies, and are
not counted. Before scan schema 3 they were: Django's
`class Meta(BaseForm.Meta)` alone added a false dependency to hundreds of netbox
classes.

Measured by hand on 36 classes (152 references) from 12 open-source projects,
under schema 3: **97.4% precision and 96.1% recall**, with 31 of 36 classes
exactly right. The errors cluster in high-coupling classes, but none moved a
class across the `dcc` threshold. What goes wrong:

- **Name collisions count.** A third-party class, local variable or module
  with the same name as a project class is counted — `typing.Tuple` when the
  project defines `Tuple`, werkzeug's `Response` when the project defines its
  own.
- **Type aliases are not followed.** `Scheme = Union[APIKey, OAuth2]` used in
  an annotation contributes nothing.
- **Two project classes with the same name count once.**

Method, per-reference verdicts and the full breakdown:
[metric-accuracy.md](https://github.com/okngms/RefactorLens/blob/main/experiments/hardening/metric-accuracy.md).

**CAM is conditional.** The classic definition uses parameter *types*. Parameter
*names* measure something else entirely and would make the result incomparable
to the literature, so name similarity is never used as a fallback. Most Python
codebases on our calibration corpus are mostly annotated (median 82% of
parameters), but a large minority is not — 7 of 26 projects annotate fewer than
3%. Forcing a number out of those would feed the model
noise dressed up as evidence. If annotation coverage falls below
`metrics.cam_min_annotation_coverage` (default 0.7), CAM reports `null` and the
report records why.

### Known limitation: DAM and CAM on real code

Measured on a 26-project calibration corpus (per-project medians):

- **DAM largely reflects a project's naming convention.** Among classes with at
  least two attributes, a typical project puts 86.5% on a single DAM value, and
  in 17 of 19 projects that value is 0. Differences between projects explain
  between half (each project weighted equally) and three quarters (weighted by
  class count) of DAM's variance. In four of five
  web applications (and in fastapi, pipx, yolov5) DAM does not separate classes
  at all: at least 90% of them have no `_`-prefixed attribute. In six of seven
  libraries it does vary between classes. Read DAM against the project's own
  convention, not as an absolute score.
- **CAM is computed for about a quarter of classes** and carries information
  (two or more methods with parameters) for about one in six; in projects
  without annotations (yt-dlp, awscli, netbox) it is almost always `null`.
  Where it is computed, it does discriminate.

Both are kept rather than dropped: removing a field would invalidate earlier
reports and the experiment data built on them. Measurement:
[coverage.md](https://github.com/okngms/RefactorLens/blob/main/experiments/hardening/coverage.md).

### Known limitation: `god_class` and stateless methods

LCOM4 counts every method that touches no attribute as its own component. On
the 26-project calibration corpus, 44 of the 96 classes that pass the
`god_class` metric gate are mostly made of such methods.

- **Interfaces are exempt.** A class whose method names are at least half
  stubs (`pass`, `...`, `return None`, `raise NotImplementedError`) has no
  behaviour to split and gets no `god_class`; the report's `stub_methods`
  field shows the count. This removed three classes on the corpus, among them
  mypy's `NodeVisitor` (83 stub methods).
- **Still flagged, possibly wrongly:** GraphQL types whose resolvers are
  `@staticmethod` (five saleor classes), and large visitor or message-catalogue
  classes whose methods only delegate to a shared helper.

Two replacement gates from the literature (Hitz–Montazeri LCOM3 and
Lanza–Marinescu TCC) and two stateful-method variants were measured, and a
blind sample of 32 large classes was labelled — by an LLM (Claude Sonnet 5),
not a person, so treat this as a first signal. By those labels most large
classes are one responsibility with many methods (a visitor, a DataFrame-like
API, a framework base class), and only about one in ten classes flagged
`god_class` clearly holds several unrelated responsibilities. No alternative
gate did measurably better, so the gate is unchanged; treat a `god_class`
finding as "large, look closer" rather than "should be split". Measurement:
[density-gate.md](https://github.com/okngms/RefactorLens/blob/main/experiments/hardening/density-gate.md),
[stateless-gate.md](https://github.com/okngms/RefactorLens/blob/main/experiments/hardening/stateless-gate.md).

### Known limitation: LCOM4 and data classes

LCOM4 flags well-written data-holder classes as uncohesive. A class with one
accessor per field — `rename` touching `name`, `promote` touching `tier` — has
methods that share no state, so LCOM4 counts them as separate responsibilities.

This is a property of the metric, not a bug, and it is well documented in the
literature. RefactorLens reports the number as measured rather than
special-casing it away. When reading a report, treat a high LCOM4 on a small
class as a question rather than a verdict; **WMC and DCC separate genuinely
overloaded classes from plain data holders far more reliably.**

### Known limitation: LCOM4 and hub methods

The opposite failure also happens. LCOM4 treats a method call as a connection,
so a large class whose methods all call one shared helper (`self.add(...)`,
`self.fail(...)`, the visitor pattern) forms a single component and scores
LCOM4 = 1 — "perfectly cohesive" — however many unrelated responsibilities it
holds.

Because `god_class` requires `lcom4 >= 3`, such classes escape the smell. On
the hardening reference set, 36 of the 107 classes large enough to qualify
were filtered out by LCOM4, 34 of them only because of call edges; mypy's
217-method `TypeChecker` is one. When a class has very high NOM and WMC but no
`god_class` finding, check it by hand. Measurement:
[metric-accuracy.md §6](https://github.com/okngms/RefactorLens/blob/main/experiments/hardening/metric-accuracy.md).

### Function-level metrics

Cyclomatic complexity counts `if`/`elif`, loops, `except` handlers, ternaries,
each additional `and`/`or` operand, comprehension clauses, and `match` cases.
`else`, `with`, and `try` itself add nothing — they do not branch execution.

Nesting depth treats `elif` chains as flat: a ten-branch `elif` is not ten
levels deep.

Nested function definitions are never entered. A function containing a closure
does not inherit the closure's complexity.

LOC counts lines that contain code, from the `def` line to the last line.
Blank lines, comment-only lines and docstrings are not counted; decorators are
excluded. A tool that reports "improved" should not reward deleting a
function's documentation, and physical line counts do exactly that. Before scan
schema 3 LOC counted physical lines; on the calibration corpus the median
function is 15% shorter under the new rule, and a quarter of `long_method`
findings disappear because docstrings, comments and blank lines were what
carried them past 40 lines.

`too_many_params` is not reported for framework entry points: click/typer
commands, HTTP route handlers (`@app.get("/...")`, `@bp.route("/...")`), Django
and SQLAlchemy signal handlers, and pytest fixtures. Their parameters are the
command-line options or HTTP parameters the framework exposes, or a signature the
framework dictates; "reduce the parameter count" would mean changing that
interface. The parameter count itself is still measured and still coloured in the
terminal, where the row is marked (`cli.scan [cli]`); `advise` simply does not
treat it as a reason to pick the function. Recognition is deliberately narrow — a
Celery task's parameters are the author's own design and still count. On the
calibration corpus this affects 17 of 2,238 functions with five or more
parameters, but a single command can carry 29 of them.

Every function also reports `annotation_coverage` (the share of its parameters,
counted exactly as for the parameter count, that carry a type annotation;
`null` when it has none) and `returns_annotated`. These are descriptive: there
is no threshold and no smell, because "fewer annotations is worse" is not a
claim the tool can support. Types kept in separate `.pyi` stub files are not
read, so a package typed that way (attrs) looks unannotated. Measurement:
[annotation-coverage.md](https://github.com/okngms/RefactorLens/blob/main/experiments/hardening/annotation-coverage.md).

`dynamic_sites` counts the places in a function where static analysis cannot
see the target: `getattr`/`setattr`/`delattr`/`hasattr` with a non-constant
name, `eval`/`exec`, dynamic imports, and forwarding the function's own
`**kwargs` to another call. Classes report `dynamic_attribute_hooks` when they
define `__getattr__`, `__getattribute__` or `__setattr__`. Again descriptive:
forwarding `**kwargs` is usually the right design, so there is no threshold.
Hand-checked on 30 sites, 27 were genuinely opaque; the three that were not
looped over a literal list written in the same function. Measurement:
[dynamic-opacity.md](https://github.com/okngms/RefactorLens/blob/main/experiments/hardening/dynamic-opacity.md).

`duck_coupling` counts the distinct `(parameter, attribute)` pairs a function
touches on its arguments — `order.total`, `customer.notify()` — so it measures
how wide an interface the function expects from its collaborators without
resolving any types. It works for module-level functions, which DCC never
sees. Parameters that are reassigned inside the function are left out. Where
parameters are annotated with a project class, 90% of the attributes a function
touches are members of that class (median of 16 projects). Descriptive, no
threshold. Measurement:
[duck-coupling.md](https://github.com/okngms/RefactorLens/blob/main/experiments/hardening/duck-coupling.md).

## RefactorLens on itself

The repository declares its own layers in
[`rlens.yaml`](https://github.com/okngms/RefactorLens/blob/main/rlens.yaml)
and runs the full loop on its own code. With the default scheme, `arch`
reports 12 violations: 9 are services calling the provider and cache modules
directly (a classic layered design, not a ports-and-adapters one), and 3 are
genuine: target selection imports threshold logic from the terminal
renderer, and the analysis layer calls the `import-linter` reader.

`advise` picked three functions (CC 33, 23 and 21). The model suggested
extracting helpers in each case, all nine verifiable predictions held, and
the behaviour tests passed. But the complexity moved rather than shrank: the
module totals went up (CC 33→36, 23→26, 21→26), and one new helper carries
CC 27 — above the critical threshold — without showing up as a flagged row
in `verify`. The target improved; the problem went next door. One model, one
run, three targets: an example, not a finding. Details:
[self-architecture.md](https://github.com/okngms/RefactorLens/blob/main/docs/self-architecture.md).

## What RefactorLens does not do

- **It does not run your code**, with two deliberate exceptions, both in an
  isolated worktree and with a timeout. Files are parsed with `ast`, never
  executed. `apply` runs the test command you put in `rlens.yaml`. `apply` on a
  project without tests, and `rlens chartests`, run **test code written by the
  model** against your code — use `--dry-run` to see the request first, and do
  not use them on code you would not run a stranger's tests against.
- **It does not merge anything.** `advise` suggests and `verify` checks. `apply`
  writes a patch to a separate branch after your tests pass; reviewing and
  merging it is a human's job, on purpose.
- **`scan` and `verify` send nothing anywhere.** They are entirely local.
  `advise` sends the selected class or function, plus the signatures of the
  project classes it depends on, to whichever provider you configure. Use
  `--dry-run` to see exactly what would go out, or the Ollama provider to keep
  everything on your machine.
- **Python only.** No Java or C#.
- **It does not measure code outside functions and classes.** Every metric
  works on a function or a class defined at the top of a module. Script-style
  code written at module level (a training loop in `train.py`), module-level
  calls (a CLI built with hundreds of `parser.add_argument(...)`), and
  functions or classes defined under `if`/`try` (`if TYPE_CHECKING:`) leave no
  trace in the report. On a 26-project corpus this is under 7% of logic lines
  for 22 projects, 8-13% for pydantic and rich, 18% for httpie and 56% for
  nanoGPT. Constant data tables are not counted as logic. Measurement:
  [corpus.md](https://github.com/okngms/RefactorLens/blob/main/experiments/hardening/corpus.md).

## Roadmap

| Phase | Contents | Version |
|---|---|---|
| 0 | Package skeleton, config, test foundation | — |
| 1 | Metric engine (`scan`) | — |
| 2 | First PyPI release | v0.1.0 |
| 3 | AI advisor (`advise`) | — |
| 4 | Verification loop (`verify`) | v0.2.0 |
| 5 | Experiment and findings | v1.0.0 |
| v2 | `arch`, smells, architectural context, calibration, second experiment | v2.0.0 |
| v2.1 | Metrics checked against a 26-project corpus: scan schema 3, percentile-based defaults, `explain` (experimental) | v2.1.0 |
| v2.2 | Python-specific measures, each pre-registered and checked on the corpus: dynamic opacity, duck-typing coupling | v2.2.0 |
| **v2.3** | **`explain --no-llm`; hardening on real projects: `advise` context budget, `--format`, config errors, mutation and property tests** | **v2.3.0** |

Phases 3 and 4 shipped together in v0.2.0. Both experiments live in
[`experiments/`](https://github.com/okngms/RefactorLens/tree/main/experiments), with the raw data committed alongside them.

Next: layer inference instead of requiring layers to be declared — today they come from your config or from an
existing `import-linter` contract, and are reported `unknown` when neither is
present. **v2.4** closes the loop (`apply` in an isolated git branch that a
human reviews and merges, a feedback round, a benchmark); **v2.5** adds
history. These were planned as v3 and v4 and stay in the 2.x line.

Ideas deliberately out of scope live in [FUTURE.md](https://github.com/okngms/RefactorLens/blob/main/FUTURE.md).
[STRUCTURE.md](https://github.com/okngms/RefactorLens/blob/main/STRUCTURE.md) maps the codebase file by file, and
[AGENTS.md](https://github.com/okngms/RefactorLens/blob/main/AGENTS.md) records the locked decisions and invariants behind it.

## Development

```bash
git clone https://github.com/okngms/RefactorLens
cd refactorlens
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest tests                        # the package's own tests
pytest examples/messy_project/tests # the fixture's behaviour tests
ruff check . && ruff format --check .
```

`examples/messy_project` is a deliberately badly designed sample project used as
the test fixture; every metric is verified against hand-computed gold values on
it. See [SMELLS.md](https://github.com/okngms/RefactorLens/blob/main/examples/messy_project/SMELLS.md) for the inventory of
intentional smells and the reasoning behind each.

Its behaviour test suite exists for a specific reason: from phase 4 onward,
refactoring suggestions get applied by hand. If a refactoring breaks the code,
the metrics improve while the program stops working. The rule is therefore
absolute — **no metric delta counts unless the behaviour tests pass.**

## Licence

MIT
