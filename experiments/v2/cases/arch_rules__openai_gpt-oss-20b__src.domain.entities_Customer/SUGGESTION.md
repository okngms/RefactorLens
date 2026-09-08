# Case: src.domain.entities:Customer

- **Condition:** arch_rules (arch-context True, metric-rules True)
- **Model:** `openai/gpt-oss-20b`
- **Repetition:** 1

> Apply **suggestion 1**, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The class is a classic data holder with five trivial accessor methods. Its high LCOM4 (4) reflects that each method touches only one private attribute, creating many disconnected components in the method‑attribute graph. NOM and WMC are also high for a class that essentially only stores data. The DCC is zero, indicating no external collaborators, which is expected for a data class. The metrics suggest that the class is overly verbose for its purpose.

## 1. Replace explicit getters with a dataclass

- **Status:** linked
- **Evidence:** NOM, WMC, LCOM4
- **Predicted effect:** NOM down (0.90), WMC down (0.90), LCOM4 down (0.80)
- **Addresses:** data_class, boilerplate
- **Destination layer:** domain

```python
from dataclasses import dataclass

@dataclass
class Customer:
    _customer_id: int
    _name: str
    _email: str
    _tier: str = "standard"

    def is_premium(self) -> bool:
        return self._tier == "premium"
```
This removes the four trivial accessor methods and the custom `__init__`, letting the dataclass generate them. The `is_premium` method remains, preserving business logic.

## Risks

Removing explicit getters exposes the private attributes directly, which may violate encapsulation expectations in tests or other layers. If external code relies on the accessor methods, those calls will fail. Additionally, the dataclass will generate a public `__init__`, so any custom validation logic in the original constructor would be lost unless re‑implemented.
