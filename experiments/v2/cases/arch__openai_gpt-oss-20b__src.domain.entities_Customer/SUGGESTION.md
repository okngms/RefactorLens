# Case: src.domain.entities:Customer

- **Condition:** arch (arch-context True, metric-rules False)
- **Model:** `openai/gpt-oss-20b`
- **Repetition:** 1

> Apply **suggestion 1**, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The Customer class has a high LCOM4 (4) indicating low cohesion, which is typical for a data holder. The class contains only simple getters and a single boolean method, resulting in a very low WMC (5) and no external class references (DCC=0). The DAM of 1.0 shows all attributes are private, and the class is correctly isolated in the domain layer. The data_class smell is expected here, but the high LCOM4 suggests that the attributes are not being used together in any method, which could be improved without changing the overall responsibility of the class.

## 1. Add a composite accessor to connect attributes

- **Status:** linked
- **Evidence:** LCOM4
- **Predicted effect:** LCOM4 down (0.90), WMC up (0.60)
- **Addresses:** data_class
- **Destination layer:** domain

```python
    def all_info(self) -> tuple[int, str, str, str]:
        """Return a tuple of all core attributes to increase cohesion."""
        return (self._customer_id, self._name, self._email, self._tier)
```

## Risks

Adding a composite accessor slightly increases WMC and may expose internal state more broadly, but it does not introduce external dependencies or violate domain-layer isolation. The change is minimal and unlikely to break existing code.
