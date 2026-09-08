# Case: src.api.report_view:ReportView

- **Condition:** arch_rules (arch-context True, metric-rules True)
- **Model:** `openai/gpt-oss-20b`
- **Repetition:** 1

> Apply **suggestion 1**, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The class has a low cohesion score (LCOM4 = 2) and references two infrastructure classes (DCC = 2), violating the presentation layer contract. It also exhibits a feature‑envy candidate smell because it accesses many Customer attributes directly. The metrics indicate that the class mixes formatting logic with data‑access and mailing responsibilities.

## 1. Split responsibilities: separate formatting from data access

- **Status:** linked
- **Evidence:** LCOM4, DCC
- **Predicted effect:** LCOM4 down (0.90), DCC down (0.80)
- **Addresses:** feature_envy_candidate, low_cohesion
- **Destination layer:** application

Create a new `ReportService` in the application layer that holds the `OrderRepository` and `EmailClient` dependencies and implements `order_count()` and `mail_summary()`. Keep `ReportView` in the presentation layer with only formatting methods (`title()` and `describe_customer()`). The view will now depend on the service via an interface or a simple wrapper, eliminating direct imports of infrastructure classes.

```python
# src.application.report_service.py
class ReportService:
    def __init__(self, repository: OrderRepository, mailer: EmailClient):
        self._repository = repository
        self._mailer = mailer
    def order_count(self) -> int:
        return self._repository.count()
    def mail_summary(self, address: str) -> dict[str, str]:
        return self._mailer.send(address, f"{self._repository.count()} orders")

# src.api.report_view.py
class ReportView:
    def __init__(self, service: ReportService, width: int = 40):
        self._service = service
        self._width = width
    def title(self) -> str:
        return "Orders".center(self._width, "-")
    def describe_customer(self, customer) -> str:
        parts = [str(customer.customer_id()), customer.name(), customer.email(), customer.tier()]
        return " | ".join(parts).ljust(self._width)
    def order_count(self) -> int:
        return self._service.order_count()
    def mail_summary(self, address: str) -> dict[str, str]:
        return self._service.mail_summary(address)
```

## Risks

The refactor introduces a new class and changes the public API of ReportView, which may break existing callers and tests. The service must be instantiated with concrete infrastructure objects or their adapters, so dependency injection wiring needs to be updated. If the application layer is not yet fully defined, creating the service may require additional scaffolding.
