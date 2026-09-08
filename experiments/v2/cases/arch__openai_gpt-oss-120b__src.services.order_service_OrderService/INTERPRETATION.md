# Interpretation note — arch / gpt-oss-120b / OrderService

Place beside `SUGGESTION.md` in the case directory.

## The ambiguity

> "The original OrderService becomes a thin façade that composes the four
> services **or is removed entirely**."

Two options, both sanctioned by the text. The Risks section covers both as
well: callers "must be updated to use the new façade or the individual
services".

## Which was applied, and why

The façade.

The tiebreak is not stylistic. `OrderService` is the **measured entity**: the
predictions are about its LCOM4, NOM, WMC and DCC. Removing it entirely would
delete the thing the case exists to measure, leaving a `removed` entity and no
delta to score. A reading that erases the measurement cannot be the right
reading of a protocol whose purpose is to measure.

FINDINGS-1 faced the same fork on `messy_project.OrderManager` and chose
removal, because that suggestion never mentioned a façade. Here the façade is
named first. The rule is the same in both — do what the text says — and the
texts differ.

## What was applied

Four classes in the same module, one per responsibility, each holding only the
attributes its methods use, exactly as the suggestion lists them. Method bodies
were extracted from the original by script rather than retyped.

`OrderService` keeps all 26 public methods as one-line delegations. Nothing was
renamed, no signature changed, no caller updated — the façade preserves the
interface, so none was needed.

## What this reproduces

FINDINGS-1's central case: NOM does not fall when wrappers stay, and the model
predicted it would. Whether LCOM4 also stays put is the open question here —
the original had five components and the façade has four attributes, so unlike
the v1 case the count may actually move.
