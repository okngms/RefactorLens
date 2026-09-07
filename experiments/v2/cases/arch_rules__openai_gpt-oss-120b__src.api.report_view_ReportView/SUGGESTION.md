# Case: src.api.report_view:ReportView

- **Condition:** arch_rules (arch-context True, metric-rules True)
- **Model:** `openai/gpt-oss-120b`
- **Repetition:** 1

> Apply **suggestion 1**, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

ReportView shows low cohesion (LCOM4 = 2) and holds two distinct internal collaborators (DCC = 2). It also exhibits a feature‑envy pattern toward Customer (four accesses) and violates the presentation layer rule by directly importing infrastructure classes (EmailClient, OrderRepository). These metrics indicate that the class is doing too much and is tightly coupled to lower‑level modules.

## 1. Extract a ReportService to the application layer

- **Status:** linked
- **Evidence:** LCOM4, DCC
- **Predicted effect:** LCOM4 down (0.90), DCC down (0.80)
- **Addresses:** feature_envy_candidate, layer_violation
- **Destination layer:** application

Create a new class `ReportService` in the `application` package that receives `OrderRepository` and `EmailClient` in its constructor. Move `order_count`, `mail_summary`, and the title‑generation logic into methods of this service. `ReportView` then only holds a reference to `ReportService` and delegates to it:
```python
# application/report_service.py
class ReportService:
    def __init__(self, repository: OrderRepository, mailer: EmailClient):
        self._repository = repository
        self._mailer = mailer
        self._width = 40

    def title(self) -> str:
        return "Orders".center(self._width, "-")

    def order_count(self) -> int:
        return self._repository.count()

    def mail_summary(self, address: str) -> dict[str, str]:
        return self._mailer.send(address, f"{self._repository.count()} orders")
```
```python
# src/api/report_view.py
class ReportView:
    def __init__(self, service: ReportService):
        self._service = service

    def title(self) -> str:
        return self._service.title()

    def order_count(self) -> int:
        return self._service.order_count()

    def mail_summary(self, address: str) -> dict[str, str]:
        return self._service.mail_summary(address)
```

## 2. Separate customer formatting into its own view class

- **Status:** linked
- **Evidence:** LCOM4
- **Predicted effect:** LCOM4 down (0.85)
- **Addresses:** feature_envy_candidate
- **Destination layer:** presentation

Introduce `CustomerView` in the presentation layer that receives a `Customer` instance and provides `format()` (the current `describe_customer`). Remove `describe_customer` from `ReportView`. The two classes will each have a single responsibility, reducing the method‑attribute graph to one connected component per class:
```python
class CustomerView:
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
`ReportView` now only handles report‑level concerns (title, order count, mailing).

## Risks

Extracting a service changes the public API of ReportView; callers must be updated to inject the new service, which may affect tests and wiring code. Splitting the customer formatter introduces an extra class that must be imported where needed, potentially increasing import noise. Both changes increase the overall number of classes, so DCC for the new service may rise, but the measured metrics for ReportView improve. Careful integration testing is required to ensure that email sending and repository counting still behave identically.
