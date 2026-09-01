# Sample reports

Real output from the three commands, checked in so the formats can be inspected
without installing anything or holding an API key.

| File | Produced by |
|---|---|
| `scan-messy_project.json` | `rlens scan` |
| `advice-messy_project.{json,md}` | `rlens advise` |
| `verify-messy_project.{json,md}` | `rlens verify --advice --applied` |

Two things worth looking at.

**`schema_version` at the root of every report.** `verify` compares two scans and
refuses to diff them when the versions differ; without that check the tool would
silently produce wrong deltas after a metric rule changed.

**`expected_effect` in the advice file.** It is a structured list of
`{metric, direction}` rather than prose, which is what makes the prediction
scoring in the verify report possible at all.
