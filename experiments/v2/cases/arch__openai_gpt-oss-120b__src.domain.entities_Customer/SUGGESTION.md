# Case: src.domain.entities:Customer

- **Condition:** arch (arch-context True, metric-rules False)
- **Model:** `openai/gpt-oss-120b`
- **Repetition:** 1

> Apply **suggestion 1**, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The class has five simple accessor methods and a tiny boolean check, giving it a low NOM and WMC but a critical LCOM4 of 4, indicating very low cohesion among its methods and attributes. DAM is 1.0 because all attributes are private, and DCC is 0 since it does not reference any other internal classes. The metrics together confirm the intentional data‑class nature of Customer, which the project flags as a known false‑positive for LCOM4.

## 1. Add domain behavior to increase cohesion

- **Status:** linked
- **Evidence:** LCOM4, DCC
- **Predicted effect:** LCOM4 down (0.80), DCC up (0.50)
- **Addresses:** data_class
- **Destination layer:** domain

Add a method that operates on the customer's state, e.g.:
```python
    def upgrade_to_premium(self) -> None:
        """Promote the customer to the premium tier.
        This introduces behaviour that uses existing attributes, linking methods together.
        """
        self._tier = "premium"
```
Optionally, introduce a small value‑object like `Tier` from the same domain package and type‑hint it, which will raise DCC modestly while further tying behaviour to the data.

## Risks

Adding mutating behaviour changes the class from a pure data holder to a mutable entity; callers that relied on immutability may need adjustments. Introducing a reference to another domain class (e.g., a Tier value‑object) raises DCC and creates a coupling that must be managed carefully.
