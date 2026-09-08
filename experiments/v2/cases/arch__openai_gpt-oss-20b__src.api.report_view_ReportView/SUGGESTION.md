# Case: src.api.report_view:ReportView

- **Condition:** arch (arch-context True, metric-rules False)
- **Model:** `openai/gpt-oss-20b`
- **Repetition:** 1

> Apply **suggestion 1**, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The class has a low cohesion score (LCOM4 = 2) and is tightly coupled to two internal classes (DCC = 2). It also exhibits a feature‑envy pattern, accessing a Customer object heavily. The small number of methods (NOM = 4) and modest cyclomatic complexity (WMC = 4) suggest the class is not overly complex, but its responsibilities are mixed: presentation, data access, and mail delivery.

## 1. Move data access and mail logic to a dedicated service

- **Status:** linked
- **Evidence:** LCOM4, DCC
- **Predicted effect:** LCOM4 down (0.90), DCC down (0.80)
- **Addresses:** feature_envy_candidate, god_class
- **Destination layer:** application

Create a new class `ReportService` in the application layer:
```python
class ReportService:
    def __init__(self, repo: OrderRepository, mailer: EmailClient):
        self._repo = repo
        self._mailer = mailer

    def order_count(self) -> int:
        return self._repo.count()

    def mail_summary(self, address: str) -> dict[str, str]:
        return self._mailer.send(address, f"{self._repo.count()} orders")
```
Refactor `ReportView` to depend only on the service for data and mail, keeping only formatting methods (`title`, `describe_customer`).

## 2. Extract customer formatting into a separate formatter

- **Status:** linked
- **Evidence:** LCOM4, DCC
- **Predicted effect:** LCOM4 down (0.80), DCC down (0.70)
- **Addresses:** feature_envy_candidate
- **Destination layer:** application

Create `CustomerFormatter` in the application layer:
```python
class CustomerFormatter:
    def __init__(self, width: int = 40):
        self._width = width

    def format(self, customer) -> str:
        parts = [
            str(customer.customer_id()),
            customer.name(),
            customer.email(),
            customer.tier(),
        ]
        return " | ".join(parts).ljust(self._width)
```
Replace `ReportView.describe_customer` with a call to this formatter, or remove the method entirely and let callers use the formatter directly.

## Risks

These changes alter the public API of `ReportView`; callers that invoke `order_count` or `mail_summary` directly will need to be updated to use `ReportService`. The formatter may need to be injected into the view if the view is instantiated elsewhere. Ensure that the new service and formatter are registered in the dependency injection container (if used) to avoid runtime errors.
