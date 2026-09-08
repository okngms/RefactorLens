# Interpretation note — arch / gpt-oss-20b / Customer

Place beside `SUGGESTION.md` in the case directory.

## No ambiguity

The suggestion supplies the method verbatim. One method was added to
`Customer`, nothing else was touched, no call site needed updating.

The note exists not because the application was unclear but because of what
the application demonstrates.

## What it does

`all_info` touches all four private attributes. LCOM4 counts connected
components in the method-attribute graph, so a single method touching every
attribute merges all of them:

```
before: NOM 5, WMC 5, LCOM4 4, DAM 1.00, interface 5
after:  NOM 6, WMC 6, LCOM4 1, DAM 1.00, interface 6
```

LCOM4 goes from "critical" to perfect. Nothing about the class is better. It
has one more method than it needs and returns its entire state as a tuple.

## Every defence stays silent

| Check | Result | Why it does not fire |
|---|---|---|
| Behaviour tests | 71 pass | Nothing was removed or changed |
| Goodhart (interface shrank) | silent | The interface **grew**, 5 → 6 |
| Architecture violations | unchanged | Nothing crossed a layer |
| Prediction accuracy | likely 2/2 | The model was right about both metrics |

`verify` will report this as an improvement with a perfect prediction score. By
every measure the tool has, this is the best case in the experiment.

## Why this is the sharpest case in the set

FINDINGS-1 recorded a model improving four metrics while deleting a class's
entire public interface. The behaviour tests caught it — 42 failed — and the
finding was that metric verification alone is insufficient.

This is the same shape with the failure mode inverted. Nothing breaks, so
nothing catches it. The model states the trade-off it is making (`WMC up`,
0.60) and is correct about both predictions. It is not deceiving anyone; it was
asked to lower LCOM4 and it lowered LCOM4.

The metric invited this. A cohesion measure defined over shared attribute
access can always be satisfied by adding one method that touches everything,
and no amount of behaviour testing will notice.

## What would catch it

Nothing currently in the tool. Candidates, none implemented:

- A method that only reads state and adds no behaviour is not a cohesion
  improvement; some notion of "does this method do anything" would be needed.
- Comparing LCOM4 against a second cohesion measure that a hub method does not
  satisfy — but every graph-based measure has the same hole.
- Human review, which is what the tool exists to inform rather than replace.

This belongs in FINDINGS-2 as an open problem, not a solved one.
