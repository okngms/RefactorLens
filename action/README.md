# RefactorLens diff — GitHub Action

Compares a pull request with its base and comments with the result: metric
changes, new and resolved findings, detected refactorings (including
delegating wrappers left behind), and suspicious improvements. It can fail
the build on new findings only, so an existing codebase is not blocked by
the findings it already has. It calls no model and needs no API key.

```yaml
name: refactorlens
on: pull_request

permissions:
  contents: read
  pull-requests: write   # to post the comment

jobs:
  diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0       # the base commit must be available
      - uses: okngms/RefactorLens/action@v2.4.0
        with:
          fail-on: new-violation
```

| Input | Default | Meaning |
|---|---|---|
| `path` | `.` | Directory to scan on both sides |
| `base` | the PR's base commit | Revision to compare against |
| `fail-on` | `none` | `none`, `regression` (a metric got worse) or `new-violation` |
| `comment` | `true` | Post the result as a PR comment (edits the previous one) |
| `version` | latest | refactorlens version to install |
| `python-version` | `3.12` | Python used to run RefactorLens |

**Ratchet.** With `fail-on: new-violation`, a finding fails the build only if
it is not accepted: by `.rlens-baseline.json` in `path` when that file exists,
otherwise by the base revision. Create or refresh the baseline with
`rlens baseline update` and commit it.

The comment also goes to the job summary. See
[example-comment.md](example-comment.md) for real output.

## Versioning

Pin a release tag (`@v2.4.0`) rather than a branch. The action lives in the
`action/` directory of the RefactorLens repository; GitHub Marketplace lists
only actions whose `action.yml` is at a repository root, so the Marketplace
listing needs either that or a separate repository.
