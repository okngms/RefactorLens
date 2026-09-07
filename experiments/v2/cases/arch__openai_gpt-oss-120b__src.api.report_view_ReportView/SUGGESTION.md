# Case: src.api.report_view:ReportView

- **Condition:** arch (arch-context True, metric-rules False)
- **Model:** `openai/gpt-oss-120b`
- **Repetition:** 1

> Apply **suggestion 1**, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The class has a low method count (NOM=4) but its cohesion is weak (LCOM4=2) because two of its methods reach into the OrderRepository and EmailClient, while only one method accesses its own state. It also references two distinct internal classes (DCC=2), violating the presentation layer's rule against infrastructure imports and triggering feature‑envy and LV‑SKIP warnings.

## 1. Extract infrastructure interactions into an application service

- **Status:** linked
- **Evidence:** LCOM4, DCC
- **Predicted effect:** LCOM4 down (0.85), DCC down (0.70)
- **Addresses:** feature_envy_candidate, layer_violation
- **Destination layer:** application

Create a new class in the application layer, e.g. OrderReportService, that receives OrderRepository and EmailClient in its constructor and implements `order_count` and `mail_summary`. In ReportView keep only presentation logic (title, describe_customer) and delegate to the service:
```python
class OrderReportService:
    def __init__(self, repository: OrderRepository, mailer: EmailClient):
        self._repository = repository
        self._mailer = mailer
    def order_count(self) -> int:
        return self._repository.count()
    def mail_summary(self, address: str) -> dict[str, str]:
        return self._mailer.send(address, f"{self._repository.count()} orders")

class ReportView:
    def __init__(self, service: OrderReportService):
        self._service = service
        self._width = 40
    # title and describe_customer stay unchanged
    def order_count(self) -> int:
        return self._service.order_count()
    def mail_summary(self, address: str) -> dict[str, str]:
        return self._service.mail_summary(address)
```

## Risks

Moving the repository and mailer behind an application service changes the public API of ReportView; callers must be updated to provide the new service instance. If other presentation components rely on direct access to OrderRepository or EmailClient, they will also need refactoring. The added indirection may slightly increase runtime overhead, but it restores layer boundaries and improves cohesion.
