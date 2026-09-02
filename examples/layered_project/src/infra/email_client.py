"""Infrastructure katmanı: dış dünya ile iletişim."""

from __future__ import annotations


class EmailClient:
    def __init__(self, host: str = "localhost") -> None:
        self.host = host
        self._sent: list[dict[str, str]] = []

    def send(self, address: str, subject: str) -> dict[str, str]:
        message = {"host": self.host, "to": address, "subject": subject}
        self._sent.append(message)
        return message

    def outbox(self) -> list[dict[str, str]]:
        return list(self._sent)
