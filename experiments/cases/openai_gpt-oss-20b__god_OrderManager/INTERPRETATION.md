# Interpretation note — openai/gpt-oss-20b / god:OrderManager

Place this file in the case directory alongside `SUGGESTION.md`.

## The ambiguity

The suggestion instructs that all 25 methods be **moved** into four new classes.
It never says what remains of `OrderManager`, yet the same paragraph claims the
change will be "dramatically lowering LCOM4 and DCC **for OrderManager**". The
text is internally inconsistent: it empties the class while still speaking of it
as though it survives.

Compare with the `openai/gpt-oss-120b` suggestion for the same target, which
states explicitly that "OrderManager becomes a thin façade that composes these
services and forwards calls" and shows a delegating method as an example. That
sentence is absent here.

## Readings considered

| Reading | What it requires | Verdict |
|---|---|---|
| (a) `OrderManager` keeps only a constructor wiring the components | Exactly what the text says | **applied** |
| (b) `OrderManager` becomes a façade with 25 delegating methods | Adding 25 methods the text never mentions | rejected |
| (c) `OrderManager` is renamed to `OrderService` | A rename the text never mentions | rejected |

The protocol rule is "improve nothing the text does not explicitly ask for".
Adding 25 delegating methods would be a substantial addition, and it would
amount to rescuing a suggestion that did not rescue itself.

## Minimal adaptations that were unavoidable

Moving method bodies verbatim would not even run, because the bodies reference
attributes that now live elsewhere. The smallest wiring consistent with the
constructors the suggestion itself specifies:

- `self._orders` / `self._next_id` → `self.repo._orders` / `self.repo._next_id`
  (`OrderService.__init__` takes a `repo` parameter in the suggestion)
- `self._tax_rate` / `self._discount_rules` → `self.tax_rate` /
  `self.discount_rules` (the suggestion's `PricingEngine.__init__` assigns
  public names)
- `self._smtp_host` → `self.smtp_host` (same reason)

Nothing else was changed. No method was renamed, no signature altered, no type
hint added beyond those the suggestion wrote itself.

## Outcome

Behaviour tests: **42 failed, 49 passed.** The case is `broken` and its metric
delta is void.

This is the finding, not a flaw in the experiment. Applied as written, the
suggestion removes the entire public interface of the class while every metric
it named improves. It is the Goodhart failure the tool was built to expose,
produced by a real model rather than a constructed example.

## Bias disclosure

Reading (a) was chosen before the metrics were measured, on the basis of the
protocol rule alone. The choice materially determines the result: reading (b)
would have produced a working program and a very different accuracy figure.
This must be stated in `FINDINGS.md`.
