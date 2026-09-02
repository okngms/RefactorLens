# docs/

Planning documents and corrections that are not part of the package.

## Corrections to the v2-v4 planning set

The version roadmap lives outside this repository (`00`-`04`). Two of its
statements were checked against v1's actual data and did not survive. The
corrections are here rather than silently applied, because the originals may
already be in circulation.

| File | Corrects | Why |
|---|---|---|
| `SPEC-duzeltme-2.5.md` | `04` § 2.5 | The metric classification contradicted FINDINGS-1: it listed `NOM` and `LOC` as arithmetic, but both were mispredicted every time. Applying it would report v1's accuracy as 6/9 instead of 6/6. |
| `v2-duzeltme-asama5.md` | `01` § 10, Aşama 5 | The experiment required ≥200 manually applied predictions — roughly 90 cases and 35+ hours. Split into an advice-only part and a reduced applied part; the full design moves to v3 where `apply` automates it. |

Both were caught before implementation. Neither changes any code.

## Rule

A planning document that contradicts measured data is corrected, not worked
around. If a correction is rejected, the reason belongs here too.
