# Repository structure

A map of the codebase: what lives where, what each file is responsible for, and
how a command flows through them.

For *why* the code is shaped this way — the locked decisions, the invariants that
must not break, and the traps already hit — see [AGENTS.md](AGENTS.md).

~8,900 lines of source, ~8,500 lines of tests (1052 of them), plus the
fixture's own 91 behaviour tests.

---

## Top level

```
refactorlens/
├── pyproject.toml          Packaging, dependencies, ruff and pytest config
├── README.md               The public documentation (this is what PyPI shows)
├── STRUCTURE.md            You are here
├── AGENTS.md               Why the code is shaped this way; locked decisions
├── CLAUDE.md               Claude Code entry point: imports AGENTS.md, adds the session workflow
├── FUTURE.md               Ideas deliberately kept out of scope
├── LICENSE                 MIT
├── .env.example            Which API keys are needed; copy to .env
├── .gitignore
├── src/rlens/              The package pip installs
├── examples/               Test fixture and sample output
├── experiments/            Research scripts and data; import rlens, never ship to users
└── tests/                  The package's own tests
```

Two things are easy to confuse:

**Two `README.md` files.** The one at the root documents the tool. The one in
`examples/sample_reports/` explains what those sample files are.

**Two `tests/` directories.** The root one tests RefactorLens. The one inside
`examples/messy_project/` tests the *fixture* — see below for why that matters.

---

## `src/rlens/` — the package

```
src/rlens/
├── __init__.py             __version__ — the single source of the version number
├── cli.py                  The four commands: scan, arch, advise, verify
├── config.py               rlens.yaml loading, merging and validation
│
├── analysis/               Measurement. No network, no LLM.
│   ├── model.py            Report dataclasses + the three schema versions
│   ├── parser.py           File discovery and ast parsing
│   ├── entry_points.py     Framework entry points (click/typer, routes, signals, fixtures)
│   ├── func_metrics.py     CC, LOC, parameter count, nesting depth
│   ├── class_metrics.py    NOM, WMC, DAM, LCOM4, DCC, CAM
│   ├── imports.py          Import extraction; module → module edges
│   ├── graph.py            Ca, Ce, instability, cycles
│   ├── architecture.py     Layer assignment and violations → ArchReport
│   ├── interface.py        Public interface of a class (Goodhart check input)
│   ├── smells.py           god_class, data_class, feature_envy, long_method, …
│   └── scanner.py          Orchestration: sources → ProjectReport
│
├── advise/                 Deciding what to ask and understanding the answer
│   ├── selector.py         Rank targets by threshold violations
│   ├── context.py          Which code goes in the prompt; context budget
│   ├── prompts.py          System instruction, evidence block, output schema
│   └── advisor.py          Call, parse, validate, one repair attempt
│
├── explain/                Reading the measurements back, no advice (experimental)
│   ├── prompts.py          System instruction and measurement block for the model
│   ├── explainer.py        Call, parse, tag unlinked and graded findings
│   └── template.py         --no-llm: fixed sentence templates, never sent to a model
│
├── llm/                    Cost control around the provider call
│   ├── budget.py           Per-run call and token budget; partial reports
│   └── cache.py            Prompt-hash keyed response cache
│
├── providers/              Talking to LLMs
│   ├── base.py             Contract, error types, retry with backoff, .env
│   ├── groq.py             Cloud provider
│   ├── ollama.py           Local provider
│   └── __init__.py         Name → adapter lookup
│
├── integrations/           Reading other tools' configuration
│   └── importlinter.py     Layer contracts from an existing import-linter setup
│
├── verify/                 Measuring what actually happened
│   ├── diff.py             Metric deltas between two scan reports
│   ├── prediction.py       Predictions vs measured delta; hit rate
│   ├── calibration.py      Brier score and ECE over stated confidence
│   └── goodhart.py         Metrics improved while the interface shrank
│
└── report/                 Everything the user sees or reads later
    ├── terminal.py         scan tables
    ├── architecture.py     arch output, terminal and markdown
    ├── advice.py           advise output, terminal and markdown
    ├── verify.py           verify output, terminal and markdown
    ├── explain.py          explain output (model and template), terminal and markdown
    └── files.py            Writing and reading JSON/markdown reports
```

### Why the boundaries are where they are

**`cli.py` contains no logic.** It reads arguments, loads config, calls into the
packages above and prints the result. Everything it calls is testable without a
terminal.

**`analysis/` never touches the network.** `scan` and `verify` are entirely
local; only `advise` sends anything anywhere. Keeping measurement in its own
package makes that guarantee structural rather than a promise.

**`report/` is separate from the logic that produces the data.** The same
`ProjectDelta` renders to a terminal table and to markdown without either
formatter leaking into `verify/`.

---

## `examples/messy_project/` — the test fixture

```
examples/messy_project/
├── SMELLS.md               Inventory of the deliberate smells, with measured values
├── rlens.yaml              The fixture's own config
├── models.py               Clean, fully annotated classes (CAM is computable here)
├── services.py             Small helper classes
├── god.py                  The god class — the main subject
├── reporting.py            Partially annotated class (CAM falls below threshold)
├── utils.py                Function-level smells
└── tests/                  BEHAVIOUR tests — 91 of them
    ├── conftest.py         Makes the fixture importable as a flat project
    ├── test_god.py
    ├── test_models.py
    ├── test_reporting.py
    ├── test_services.py
    └── test_utils.py
```

This is not a demo. It is a measuring instrument, and it does four jobs:

1. **Gold values for the metric tests.** Every number in `SMELLS.md` was computed
   by hand first, then asserted in `tests/test_class_metrics.py` and
   `tests/test_func_metrics.py`.
2. **The README demo.**
3. **The subject of the phase 5 experiment.**
4. **The ground on which "did the refactoring break the code" is decided.**

### Why `messy_project/tests/` is mandatory

From phase 4 onward, refactoring suggestions get applied by hand. If a
refactoring breaks the code, the metrics improve while the program stops working
— and the verify report means nothing.

This is not hypothetical. Extracting the audit-log component out of
`OrderManager` produces:

```
NOM 25→20, WMC 49→42, LCOM4 4→3   →   verdict: improved
6 failed, 85 passed                →   the code is broken
```

Three metrics improved and the tool said "improved". The behaviour tests are the
only thing that catches it. Hence the project rule:

> **No metric delta counts unless the behaviour tests pass.**

---

## `tests/` — the package's own tests

```
tests/
├── test_config.py          Config loading, merging, validation
├── test_parser.py          Discovery, include/exclude, broken files
├── test_func_metrics.py    Function metrics + gold values
├── test_class_metrics.py   Class metrics + gold values
├── test_scanner.py         The two-pass scan flow
├── test_report.py          scan output and JSON files
├── test_selector.py        Target ranking
├── test_context.py         Prompt context and budget
├── test_prompts.py         Prompt construction
├── test_providers.py       Adapters, retry, .env (fake HTTP)
├── test_advisor.py         Response parsing and schema validation
├── test_advice_report.py   advise output
├── test_diff.py            Metric deltas
├── test_prediction.py      Prediction scoring
├── test_verify_report.py   verify output
├── test_metric_edges.py    Real-world idioms: decorators, @overload, except*, string annotations
├── test_hardening_compare.py  The radon cross-check classifier (radon optional)
├── test_hardening_dcc.py   DCC manual-count sampling, hints, verdict enforcement
├── test_hardening_cohesion_cam.py  CAM coverage split, Spearman, deviation categories
├── test_hardening_corpus.py  Corpus file, accuracy-set subset, config trap, logic-line rule
├── test_hardening_distribution.py  Percentiles, >= rule, per-project weighting, eligibility
├── test_hardening_coverage.py  Null / definitional / informative split, spread, trivial-value rules
├── test_hardening_thresholds.py  Candidate shares, pinned fixture thresholds, LCOM4 reaches no smell
├── test_hardening_density_gate.py  LCOM3-HM, direct TCC, stub bodies, stateless kinds
├── test_hardening_stateless_gate.py  Stateful graphs, R1-R4 rules, refutation conditions
├── test_hardening_god_class_sample.py  Stratified pick, blindness, verdict checks, weighting
├── test_stub_interfaces.py  K10: stub bodies, stub names, no god_class on interfaces
├── test_annotation_coverage.py  K11: slots, null rule, CAM agreement, fixture gold values
├── test_hardening_annotations.py  Pre-registered refutations, py.typed detection
├── test_exposure.py        EXP candidate: index, external access, eta squared
├── test_hardening_pysmell_labels.py  Threshold search, reading rule, PySmell detector rules
├── test_dynamic_opacity.py  K13: opaque site kinds, hooks, refutation rules, fixture gold values
├── test_duck_coupling.py   K14: pairs, rebinding forms, members, fixture gold values
├── test_hardening_unreported.py  Conditional units, duplicate identities, logic sets
├── test_module_cohesion.py  Module globals, components, exact expectation
├── test_entry_points.py    Entry point recognition; no too_many_params, no advice on params
└── test_cli.py             All four commands end to end
```

### `experiments/hardening/` — metric accuracy on real code

```
experiments/hardening/
├── projects.txt            12 reference projects, frozen by commit hash (block 1 accuracy)
├── corpus.txt              26 calibration projects in four types; superset of projects.txt
├── corpus.py               Corpus fetch and inventory: counts, measured logic share
├── corpus.md               What the corpus is and how much of it RefactorLens sees
├── distribution.py         Per-project percentiles and where default thresholds fall
├── metric-distribution.md  The distribution table and what it says about thresholds
├── coverage.py             Per metric: computable, fixed by definition, informative, spread
├── coverage.md             The coverage table; why CAM and DAM are kept (K7)
├── thresholds.py           Threshold candidates: LCOM4 shares, user-visible effect, kw-only params
├── thresholds.md           The threshold rule and why LCOM4 became 5/10 (K8)
├── density_gate.py         god_class gate candidates: LCOM3-HM, TCC, stateless methods
├── density-gate.md         Nine items for both candidates and why they were rejected (K9)
├── stateless_gate.py       Pre-registered stateless-method rules R1-R4 and their refutations
├── stateless-gate.md       Pre-registration, PySmell label check, results; R1 became K10
├── god_class_sample.py     Blind stratified god_class sample and weighted summary
├── god-class-labeling.md   Labelling guide, written before any label
├── god-class-sample.json   What the labeller sees: identity and location only
├── god-class-verdicts.json Labels from yanitlar.md (32 classes)
├── yanitlar.md             Raw blind labels (LLM labeller, one chat per class)
├── god-class-labels.md     Result of the blind labels; R4 not adopted (K17)
├── annotations.py          Annotation coverage on the corpus; py.typed cross-check
├── annotation-coverage.md  Pre-registration and result (K11)
├── exposure_measure.py     DAM variance split; usage-based exposure candidate (EXP)
├── exposure.md             Pre-registration and result; EXP rejected (K12)
├── exposure-sample.json    30 exposed attributes drawn for the precision check
├── exposure-verdicts.json  Per-access verdicts with file, line and reason
├── pysmell_labels.py       Can PySmell's manual labels be rebuilt from its own metrics
├── pysmell-labels.md       Pre-registration and result: labels are thresholds, not an oracle
├── dynamic_opacity.py      Dynamic opacity on the corpus; precision sample
├── dynamic-opacity.md      Pre-registration and result (K13)
├── dynamic-sample.json     30 opaque sites drawn for the precision check
├── dynamic-verdicts.json   Per-site verdicts with file, line and reason
├── duck_coupling.py        Duck coupling on the corpus; typed member check, precision sample
├── duck-coupling.md        Pre-registration and result (K14)
├── duck-sample.json        30 parameter-attribute pairs drawn for the precision check
├── duck-verdicts.json      Per-pair verdicts with file, line and reason
├── unreported.py           Code no unit covers: conditional definitions, module-level code
├── module_cohesion.py      Module cohesion candidates and the importer-usage signal
├── module-cohesion.md      Pre-registration and result; both variants rejected (K16)
├── friction.md             Rough edges found using the tool on itself, each with a decision
├── robustness.py           scan, arch and advise --dry-run on the corpus via the CLI; exits, skips, prompt sizes, time
├── robustness.md           Result: no crashes, timing, the context-budget fix
├── self/                   RefactorLens on itself: scan, arch, advise and verify reports
├── entry_points.py         How many entry points the corpus has; effect on too_many_params
├── entry-points.md         Why the rule is narrow, and what it changed
├── compare_radon.py        CC vs radon per function; classifies every difference
├── dcc_sample.py           DCC manual count: stratified sample, worksheet, summary
├── cam_coverage.py         How often CAM is computable, and informative
├── compare_cohesion.py     LCOM4 vs the cohesion tool: Spearman, deviations, god_class gate
├── dcc-verdicts.json       Human verdicts per reference, with file and line
├── metric-accuracy.md      The difference table: definition gaps, fixes, open decisions
├── results/cc-radon.json   Raw comparison output
├── results/dcc-*.{json,csv}  DCC sample, per-reference rows, summary
├── results/cam-coverage.json, cohesion-spearman.json
├── results/corpus-inventory.json  Reproducible counts; corpus-timing.json is not
├── results/metric-distribution.json, metric-distribution-tables.md
├── results/entry-points.json
├── results/coverage.json, coverage-tables.md
├── results/threshold-candidates.json, threshold-candidates-tables.md
├── results/density-gate.json, density-gate-tables.md
├── results/stateless-gate.json, stateless-gate-tables.md
├── results/god-class-strata.json  Strata of the sample
├── results/god-class-summary.json  Weighted precision and recall per gate
├── results/annotation-coverage.json, annotation-coverage-tables.md
├── results/exposure.json, exposure-tables.md
├── results/pysmell-labels.json, pysmell-labels-tables.md
├── results/dynamic-opacity.json, dynamic-opacity-tables.md
├── results/duck-coupling.json, duck-coupling-tables.md
├── results/unreported.json, unreported-tables.md
├── results/module-cohesion.json, module-cohesion-tables.md
├── results/robustness.json, robustness-tables.md, robustness-timing.json
├── results/robustness-before-context-fix.json  Record of the run before the budget fix
└── .cache/                 Checked-out reference projects (gitignored, not in sdist)
```

488 tests. None of them touch the network: providers are faked and backoff
delays are injected, so the suite runs offline in under two seconds.

Run both suites:

```bash
pytest tests                        # 488
pytest examples/messy_project/tests # 91
```

---

## How a command flows

### `rlens scan <path>`

```
cli.scan
  └─ config.load_config              rlens.yaml, searched upward
  └─ analysis.scanner.scan_project
       ├─ analysis.parser            find .py files, parse them
       ├─ class_metrics.collect_class_names   ← pass 1
       ├─ class_metrics.measure_class          ← pass 2
       └─ func_metrics.measure_function
  └─ report.terminal.render_report   tables
  └─ report.files.write_report       reports/scan-<timestamp>.json
```

The two passes exist because DCC counts *project-internal* classes. Deciding
whether a name belongs to the project requires knowing every class name first;
a single pass would systematically undercount.

### `rlens advise <path>`

```
cli.advise
  └─ scanner.scan_project_with_sources   report + parsed sources
  └─ advise.selector.select_targets      worst N by violation score
  └─ advise.context.build_context        target body + dependency signatures
  └─ advise.prompts.build_user_prompt    evidence block + JSON schema
  └─ providers.get_provider              groq | ollama
  └─ advise.advisor.request_advice       call, parse, validate, repair once
  └─ report.advice                       terminal + markdown
  └─ report.files.write_advice           reports/advice-<timestamp>.{json,md}
```

`--dry-run` stops after `build_user_prompt`. No key, no network.

### `rlens verify <path>`

```
cli.verify
  └─ report.files.latest_report      baseline, unless --before given
  └─ report.files.read_report        validates schema_version
  └─ scanner.scan_project            measure again, now
  └─ verify.diff.diff_reports        per-metric deltas + verdicts
  └─ verify.prediction.check_predictions   only with --advice
  └─ report.verify                   terminal + markdown
```

---

## Report formats

Three kinds of report land in `reports/`, all timestamped so runs never
overwrite each other:

| File | Written by | Read by |
|---|---|---|
| `scan-*.json` | `scan` | `verify` as the baseline |
| `advice-*.json` | `advise` | `verify --advice` |
| `advice-*.md` | `advise` | you |
| `verify-*.json` | `verify` | phase 5 aggregation |
| `verify-*.md` | `verify` | you |

Every report carries `schema_version` at its root. Metric rules change between
versions; without that field `verify` would silently diff two reports whose
numbers mean different things. Scan reports and advice reports version
independently, because the advice format can change without affecting metrics.

Sample output of all three lives in `examples/sample_reports/` so the formats can
be inspected without installing anything.

---

## Where things are deliberately *not*

- **No `history` command.** `reports/` is gitignored, so history lives on one
  machine and disappears with it. `verify` covers the useful case.
- **No auto-fix.** The tool suggests; a human applies. Automatic application
  would make the behaviour-test rule unenforceable.
- **No hard-coded model names.** Provider catalogues change; a baked-in name
  breaks quietly when the package ages.
- **No Gemini or Anthropic adapters yet.** The contract in `providers/base.py` is
  about thirty lines to implement.

See [FUTURE.md](FUTURE.md) for the parking lot.
