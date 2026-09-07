# Case: src.domain.entities:Customer

- **Condition:** arch_rules (arch-context True, metric-rules True)
- **Model:** `openai/gpt-oss-120b`
- **Repetition:** 1

> Apply **suggestion 1**, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The class has a very high LCOM4 (4) indicating low cohesion among its methods, but this is expected for a data holder with many simple accessors. All attributes are private (DAM=1.0) and the class does not depend on any other internal types (DCC=0). The method count (NOM=5) and total cyclomatic complexity (WMC=5) are modest, but the accessor methods add noise without functional value.

## 1. Replace explicit getters with read‑only properties

- **Status:** linked
- **Evidence:** LCOM4, NOM, WMC
- **Predicted effect:** LCOM4 down (0.85), NOM down (0.90), WMC down (0.90)
- **Addresses:** data_class
- **Destination layer:** domain

Convert each accessor method to a @property that returns the private attribute, e.g.
```python
    @property
    def customer_id(self) -> int:
        return self._customer_id
```
Remove the now‑redundant method definitions. The class body otherwise stays unchanged.

## Risks

Changing methods to properties is a source‑compatible refactor for callers that use attribute access, but any code that relied on the call syntax (e.g., obj.customer_id()) will break. Ensure the whole codebase is updated or provide a thin wrapper method for backward compatibility during transition.
