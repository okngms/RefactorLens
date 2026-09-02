"""Çağrı ve token bütçesi.

**Neden var:** Deney disiplini ücretsiz/lokal modelleri varsayılan tutmayı
gerektiriyor, ve ücretsiz katmanlarda günlük token limiti bir kaynak değil bir
duvar. Bütçe olmadan tek bir `advise --top-n 10` günlük kotayı bitirebilir.

**Neden sert durur:** Bütçe aşıldığında kalan hedefler atlanır ve rapor kısmi
olduğunu **yazar**. Sessizce daha az hedef işlemek, kullanıcının eksik bir
raporu tam sanmasına yol açardı.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rlens.config import BudgetConfig


class BudgetExceeded(Exception):
    """Bütçe dolduğunda yükseltilir. Hata değil, planlı duruş."""


@dataclass
class Budget:
    """Tek bir çalıştırmanın çağrı ve token sayacı."""

    config: BudgetConfig
    calls: int = 0
    cache_hits: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    skipped: list[str] = field(default_factory=list)
    """Bütçe dolduğu için işlenmeyen hedefler. Rapora yazılır."""

    @property
    def remaining_calls(self) -> int:
        return max(0, self.config.max_calls_per_run - self.calls)

    @property
    def exhausted(self) -> bool:
        return self.remaining_calls == 0

    def check(self, label: str = "") -> None:
        """Yeni bir çağrı yapılabilir mi?

        Raises:
            BudgetExceeded: Sınıra ulaşıldıysa.
        """
        if self.exhausted:
            if label:
                self.skipped.append(label)
            raise BudgetExceeded(
                f"Call budget exhausted ({self.config.max_calls_per_run} calls). "
                f"Raise `budget.max_calls_per_run` or narrow the run with --top-n."
            )

    def record_call(self, tokens_in: int = 0, tokens_out: int = 0) -> None:
        """Gerçekleşmiş bir çağrıyı sayar."""
        self.calls += 1
        self.tokens_in += max(0, tokens_in)
        self.tokens_out += max(0, tokens_out)

    def record_cache_hit(self) -> None:
        """Önbellekten dönen yanıt çağrı sayılmaz — para harcanmadı."""
        self.cache_hits += 1

    def fits(self, estimated_tokens: int) -> bool:
        """Tahmini boyut çağrı başına token sınırına sığıyor mu?"""
        return estimated_tokens <= self.config.max_tokens_per_call

    def summary(self) -> dict[str, int | bool]:
        return {
            "calls": self.calls,
            "max_calls": self.config.max_calls_per_run,
            "cache_hits": self.cache_hits,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "exhausted": self.exhausted,
            "skipped": len(self.skipped),
        }

    def describe(self) -> str:
        """Terminale basılacak tek satırlık özet."""
        parts = [f"{self.calls}/{self.config.max_calls_per_run} calls"]
        if self.cache_hits:
            parts.append(f"{self.cache_hits} from cache")
        if self.tokens_in or self.tokens_out:
            parts.append(f"{self.tokens_in}+{self.tokens_out} tokens")
        if self.skipped:
            parts.append(f"{len(self.skipped)} skipped (budget)")
        return ", ".join(parts)
