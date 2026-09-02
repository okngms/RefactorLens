"""Application katmanı: küçük ve kohezyonlu — karşılaştırma referansı."""

from __future__ import annotations

from domain.policies import DiscountPolicy


class PricingService:
    def __init__(self, policy: DiscountPolicy) -> None:
        self._policy = policy
        self._tax_rate = 0.18

    def net(self, amount: float, tier: str) -> float:
        return round(amount * (1 - self._policy.rate_for(tier)), 2)

    def gross(self, amount: float, tier: str) -> float:
        return round(self.net(amount, tier) * (1 + self._tax_rate), 2)
