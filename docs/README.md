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
| `SPEC-duzeltme-2.5-v2.md` | `SPEC-duzeltme-2.5.md` | The first correction wrote its own refutation condition and 5b triggered it. The determinant is not the metric but whether the change leaves residue behind: a delegating wrapper keeps NOM and LCOM4 still, and models almost never predict that. |
| `v2-5b-protokol.md` | `v2-duzeltme-asama5.md` part B | Targets were chosen after reading the 5a data, so the protocol was written before the first application. |
| `v2-duzeltme-asama5.md` | `01` § 10, Aşama 5 | The experiment required ≥200 manually applied predictions — roughly 90 cases and 35+ hours. Split into an advice-only part and a reduced applied part; the full design moves to v3 where `apply` automates it. |

The first two were caught before implementation. The third replaces a
hypothesis that its own data refuted — which is what a refutation condition is
for. Superseded documents stay: how a hypothesis was built and what broke it
matters as much as the corrected version.

## Rule

A planning document that contradicts measured data is corrected, not worked
around. If a correction is rejected, the reason belongs here too.
