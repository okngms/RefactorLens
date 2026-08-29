# Sample reports

Real `rlens scan` output, checked in so that the JSON schema can be inspected
without installing anything.

- `scan-messy_project.json` — a scan of `examples/messy_project`

Note the `schema_version` field at the root. `verify` (phase 4) compares two
reports and refuses to diff them when the schema versions differ; without that
check the tool would silently produce wrong deltas after a metric rule changes.
