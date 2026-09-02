"""Presentation katmanı — KASITLI İHLALLER: LV-SKIP ve feature_envy_candidate.

`LV-SKIP`: application katmanını atlayıp doğrudan infrastructure'a bağımlı.
`feature_envy_candidate`: `describe_customer` kendi sınıfının attribute'larından
çok `Customer`'ın metotlarına dokunuyor.
"""

from __future__ import annotations

from infra.email_client import EmailClient
from infra.order_repository import OrderRepository


class ReportView:
    def __init__(self, repository: OrderRepository, mailer: EmailClient) -> None:
        self._repository = repository
        self._mailer = mailer
        self._width = 40

    def title(self) -> str:
        return "Orders".center(self._width, "-")

    def describe_customer(self, customer) -> str:
        """Feature envy: dört erişim Customer'a, bir tanesi kendi durumuna."""
        parts = [
            str(customer.customer_id()),
            customer.name(),
            customer.email(),
            customer.tier(),
        ]
        return " | ".join(parts).ljust(self._width)

    def order_count(self) -> int:
        return self._repository.count()

    def mail_summary(self, address: str) -> dict[str, str]:
        return self._mailer.send(address, f"{self._repository.count()} orders")
