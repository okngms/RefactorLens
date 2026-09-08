# Interpretation note — arch / gpt-oss-20b / OrderService

Place beside `SUGGESTION.md` in the case directory.

## Two decisions

### 1. Façade, not removal

> "OrderService becomes a thin façade that delegates to these services **or is
> removed entirely**."

Same fork as case 5, same tiebreak: `OrderService` is the measured entity, and
a reading that deletes it leaves nothing to score. The Risks section also
endorses the façade — "keeping a wrapper OrderService that forwards to the new
services".

### 2. Two methods were not assigned to anything

The suggestion lists 24 of the class's 26 methods. `revenue` and `tier_summary`
appear in no service.

They stay where they are, because the text does not move them. Both read
`self._repository`, so `OrderService` has to keep that reference even though
the suggestion hands the repository to `OrderLifecycleService`. The result is a
repository held in two places.

That is not an error in the application. It is what applying this suggestion
literally produces, and the residue is exactly what the experiment measures.

## Effect

```
before: NOM 26, WMC 56, LCOM4 5, DCC 4
after:  NOM 26, WMC 30, LCOM4 5, DCC 4
```

Only WMC moved.

`LCOM4` staying at 5 traces directly to the omission. Case 5 distributed all 26
methods and the façade collapsed to four attributes, so LCOM4 fell to 4. Here
`revenue` and `tier_summary` still touch `_repository`, so the fifth component
survives.

The model predicted `LCOM4 down` at 0.90 and left in the very methods that
prevent it.
