# Repository structure

A map of the codebase: what lives where, what each file is responsible for, and
how a command flows through them.

For *why* the code is shaped this way — the locked decisions, the invariants that
must not break, and the traps already hit — see [AGENTS.md](AGENTS.md).

69 files. ~4,600 lines of source, ~3,800 lines of tests.

---

## Top level

```
refactorlens/
├── pyproject.toml          Packaging, dependencies, ruff and pytest config
├── README.md               The public documentation (this is what PyPI shows)
├── STRUCTURE.md            You are here
├── AGENTS.md               Why the code is shaped this way; locked decisions
├── FUTURE.md               Ideas deliberately kept out of scope
├── LICENSE                 MIT
├── .env.example            Which API keys are needed; copy to .env
├── .gitignore
├── src/rlens/              The package pip installs
├── examples/               Test fixture and sample output
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
├── cli.py                  The three commands: scan, advise, verify
├── config.py               rlens.yaml loading, merging and validation
│
├── analysis/               Measurement. No network, no LLM.
│   ├── model.py            Report dataclasses + SCHEMA_VERSION
│   ├── parser.py           File discovery and ast parsing
│   ├── func_metrics.py     CC, LOC, parameter count, nesting depth
│   ├── class_metrics.py    NOM, WMC, DAM, LCOM4, DCC, CAM
│   └── scanner.py          Orchestration: sources → ProjectReport
│
├── advise/                 Deciding what to ask and understanding the answer
│   ├── selector.py         Rank targets by threshold violations
│   ├── context.py          Which code goes in the prompt; context budget
│   ├── prompts.py          System instruction, evidence block, output schema
│   └── advisor.py          Call, parse, validate, one repair attempt
│
├── providers/              Talking to LLMs
│   ├── base.py             Contract, error types, retry with backoff, .env
│   ├── groq.py             Cloud provider
│   ├── ollama.py           Local provider
│   └── __init__.py         Name → adapter lookup
│
├── verify/                 Measuring what actually happened
│   ├── diff.py             Metric deltas between two scan reports
│   └── prediction.py       expected_effect vs measured delta; hit rate
│
└── report/                 Everything the user sees or reads later
    ├── terminal.py         scan tables
    ├── advice.py           advise output, terminal and markdown
    ├── verify.py           verify output, terminal and markdown
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
└── test_cli.py             All three commands end to end
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
