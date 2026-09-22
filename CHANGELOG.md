# Changelog

Scan, advice and explain reports carry their own `schema_version`; `verify`
refuses to compare scan reports whose schema versions differ. After upgrading,
regenerate any `before` report with the new version.

## Unreleased

### Added

- Report fields `functions[].dynamic_sites` and
  `classes[].dynamic_attribute_hooks`: where static analysis cannot see the
  target (non-constant `getattr`/`setattr`, `eval`/`exec`, dynamic imports,
  forwarded `**kwargs`, attribute hooks). Descriptive, no threshold (K13).
- Report field `functions[].duck_coupling`: distinct `(parameter,
  attribute)` pairs a function touches on its arguments; `null` without
  parameters. Descriptive, no threshold (K14).

## 2.1.0 — 2026-09-22

The metrics were checked against a 26-project calibration corpus: CC
cross-checked against radon, LCOM4 against the `cohesion` tool, DCC counted by
hand; every metric's coverage and distribution measured; default thresholds
derived from that distribution; and every definition change recorded with its
measured effect in
[v2-tanim-kararlari.md](https://github.com/okngms/RefactorLens/blob/main/docs/v2-tanim-kararlari.md).

### Breaking: scan schema 3

Reports from 2.0.0 (schema 2) and 2.1.0 (schema 3) cannot be compared.

- `loc` counts lines that contain code; blank lines, comment-only lines and
  docstrings no longer count (K1). Deleting documentation can no longer
  "improve" LOC.
- `lcom4` is `null` for a class with no methods, previously `0` (K2).
- `dcc` no longer counts a class's own nested classes (K3); Django's
  `class Meta(Base.Meta)` was adding a false dependency to hundreds of classes.

### Changed defaults

- `thresholds.lcom4` is `{warn: 5, critical: 10}`, previously `{warn: 2,
  critical: 4}`. At 2 it flagged a third of all classes; the new values sit at
  about the 95th and 99th percentile, like the other thresholds (K8). The
  `god_class` smell keeps its own `lcom4: 3` rule. To keep the old behaviour, set
  the old values in `rlens.yaml`.

### Added

- `rlens explain` (experimental): reads the measurements back as observations,
  with no advice. Its output is not scored and is not part of any finding; in
  two runs the model still graded values it was told not to grade.
- Report fields: `functions[].annotation_coverage`,
  `functions[].returns_annotated`, `classes[].annotation_coverage` (share of
  parameters with a type annotation; descriptive, no threshold, K11),
  `functions[].entry_point` (K6), `classes[].stub_methods` (K10). Adding fields
  does not change the schema version.
- Explain reports record the `rlens_version` that produced them.

### Smells

- `too_many_params` is not reported for framework entry points: click/typer
  commands, HTTP route handlers, Django/SQLAlchemy signal handlers, pytest
  fixtures (K6). The parameter count is still measured and shown.
- `god_class` is not reported for interfaces — classes whose method names are
  at least half stub bodies (`pass`, `...`, `return None`,
  `raise NotImplementedError`) (K10). Metrics and evidence fields are unchanged.

### Fixed

These change metric values on some classes without a schema change, because
they correct the implementation rather than the definition. A 2.0.0 report and
a 2.1.0 report of the same code can differ on classes using these idioms.

- Import resolution when the scan root is a nested package (`pandas/core`):
  the import graph was silently empty, so Ca, Ce, instability and cycles were
  blank.
- Cyclomatic complexity no longer counts decorator, default-value and
  annotation expressions; `except*` is a nesting level.
- `@overload` stubs are no longer counted as methods (pandas' `DataFrame` NOM
  dropped by 43), and the public interface no longer lists property
  getter/setter pairs and overload stubs twice.
- The first parameter of a `@staticmethod` is no longer taken for `self`.
- A nested class's `self` is no longer attributed to the outer class.
- DCC resolves string annotations and `import ... as` aliases from project
  modules; `Literal[...]` and `Annotated` metadata are not references.

### Documentation

- README limitations now rest on corpus measurements: DCC precision and recall
  (97.4% / 96.1%, measured by hand), DAM and CAM coverage, the `god_class`
  gate's known false negatives and positives, and code the tool does not see.

## 2.0.0 — 2026-09-10

`arch` (layers and violations), smells, architectural context for `advise`,
calibration (Brier, ECE) in `verify`, the Goodhart check, and the second
experiment ([FINDINGS-2.md](https://github.com/okngms/RefactorLens/blob/main/FINDINGS-2.md)).
Scan schema 2, advice schema 2.

## 1.0.0

The first experiment ([FINDINGS.md](https://github.com/okngms/RefactorLens/blob/main/FINDINGS.md)).

## 0.2.0

`advise` and `verify`.

## 0.1.0

`scan`: the metric engine.
