"""`loop` akışı (`docs/02` §4, Aşama 3).

Her iterasyon: hedef için öneri (ikinciden itibaren önceki denemenin geri
beslemesiyle) → 1. öneri `apply` ile uygulanır → sonuç ölçülür. Faz 5
protokolündeki "öneri 1 her zaman" kuralı burada da geçerli: hangi önerinin
uygulanacağını seçmek ölçümü yönlendirmek olurdu.

**Her iterasyon HEAD'den bağımsızdır.** Değişiklikler üst üste binmez;
ölçülen şey, aynı kod için geri beslemenin tahmin doğruluğunu değiştirip
değiştirmediğidir (H1). Kapıyı geçen her iterasyon kendi branch'ini bırakır.

Durma: tahminlerin hepsi doğrulanabilir ve doğru **ve** kapı geçti
(`all_predictions_held`); ya da `max_iter`; ya da bütçe; ya da testsiz
projede hiç karakterizasyon testi geçmedi (`no_gate`, kapı yoksa devam
edilemez); ya da yanıt ayrıştırılamadı ya da öneri yok (`no_suggestion`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rlens.advise.advisor import request_advice
from rlens.advise.context import build_context, context_budget
from rlens.advise.selector import target_for
from rlens.analysis.scanner import scan_project_with_sources
from rlens.apply.runner import NO_GATE, SUSPICIOUS, run_apply
from rlens.apply.worktree import ApplyError
from rlens.config import Config
from rlens.llm.budget import Budget, BudgetExceeded
from rlens.loop.feedback import build_feedback
from rlens.providers.base import ProviderRequestTooLarge, ProviderTruncated
from rlens.verify.calibration import CalibrationPoint, CalibrationReport, calibrate

LOOP_SCHEMA_VERSION = 1

ALL_HELD = "all_predictions_held"
MAX_ITER = "max_iter"
BUDGET = "budget"
STOP_NO_GATE = "no_gate"
NO_SUGGESTION = "no_suggestion"
PROVIDER_LIMIT = "provider_limit"
OUTPUT_LIMIT = "output_limit"
"""Öneri yanıtı çıktı sınırında kesildi; ölçüm boşluğu, modelin hatası değil."""
"""Bir istek sağlayıcının istek başına sınırını aştı; ölçüm boşluğu, modelin hatası değil."""

STOP_TEXT = {
    ALL_HELD: "every prediction held and the tests passed",
    MAX_ITER: "reached the iteration limit",
    BUDGET: "the call budget ran out",
    STOP_NO_GATE: "no characterization test passed, so nothing could be gated",
    NO_SUGGESTION: "the model returned no usable suggestion",
    PROVIDER_LIMIT: "a request exceeded the provider's per-request limit",
    OUTPUT_LIMIT: "an advice reply was cut off at the output limit",
}


def _calibration_points(predictions: dict | None) -> tuple[list[CalibrationPoint], int]:
    points: list[CalibrationPoint] = []
    without = 0
    for suggestion in (predictions or {}).get("suggestions", []):
        for check in suggestion.get("checks", []):
            if check.get("outcome") not in ("hit", "miss"):
                continue
            if check.get("confidence") is None:
                without += 1
                continue
            points.append(
                CalibrationPoint(
                    confidence=float(check["confidence"]),
                    correct=check["outcome"] == "hit",
                    metric=check.get("metric", ""),
                )
            )
    return points, without


def iteration_calibration(predictions: dict | None) -> CalibrationReport:
    """Bir iterasyonun Brier/ECE'si; `verify` ile aynı kural (yalnızca doğrulanabilir)."""
    points, without = _calibration_points(predictions)
    return calibrate(points, without)


@dataclass
class Iteration:
    number: int
    title: str | None = None
    outcome: str | None = None
    branch: str | None = None
    gate_passed: bool | None = None
    advice_status: str | None = None
    """Uygulanan önerinin durumu (`linked`/`unlinked`/`rejected`); kısıt uyumu ölçüsü."""
    hits: int = 0
    misses: int = 0
    unverifiable: int = 0
    brier: float | None = None
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    feedback: str | None = None
    """Bu iterasyonun öneri istemine eklenen blok (ilk iterasyonda yok)."""
    refactorings: list[str] = field(default_factory=list)
    """Tespit edilen türler (H4: tür bazında doğruluk)."""
    apply: dict | None = None
    predictions: dict | None = field(default=None, repr=False)

    @property
    def accuracy(self) -> float | None:
        verifiable = self.hits + self.misses
        return round(self.hits / verifiable, 4) if verifiable else None

    @property
    def all_held(self) -> bool:
        return bool(self.gate_passed) and self.hits > 0 and self.misses == 0

    def to_dict(self) -> dict:
        return {
            "iteration": self.number,
            "title": self.title,
            "outcome": self.outcome,
            "branch": self.branch,
            "gate_passed": self.gate_passed,
            "advice_status": self.advice_status,
            "hits": self.hits,
            "misses": self.misses,
            "unverifiable": self.unverifiable,
            "accuracy": self.accuracy,
            "brier": self.brier,
            "calls": self.calls,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "feedback": self.feedback,
            "refactorings": list(self.refactorings),
            "apply": self.apply,
        }


@dataclass
class LoopResult:
    target: str
    max_iter: int
    iterations: list[Iteration] = field(default_factory=list)
    stop_reason: str = MAX_ITER

    def to_dict(self) -> dict:
        done = self.iterations
        hits = sum(i.hits for i in done)
        misses = sum(i.misses for i in done)
        gated = [i for i in done if i.gate_passed is not None]
        points: list[CalibrationPoint] = []
        without = 0
        for item in done:
            more, missing = _calibration_points(item.predictions)
            points += more
            without += missing
        overall = calibrate(points, without)
        return {
            "schema_version": LOOP_SCHEMA_VERSION,
            "target": self.target,
            "max_iter": self.max_iter,
            "stop_reason": self.stop_reason,
            "iterations": [item.to_dict() for item in done],
            "overall": {
                "accuracy": round(hits / (hits + misses), 4) if hits + misses else None,
                "gate_pass_rate": (
                    round(sum(1 for i in gated if i.gate_passed) / len(gated), 4) if gated else None
                ),
                "suspicious_rate": (
                    round(sum(1 for i in done if i.outcome == SUSPICIOUS) / len(done), 4)
                    if done
                    else None
                ),
                "brier": overall.brier,
                "ece": overall.ece,
                "without_confidence": overall.without_confidence,
                "calls": sum(i.calls for i in done),
            },
        }


def _context(path: Path, target: str, config: Config):
    result = scan_project_with_sources(Path(path), config)
    advice_target = target_for(result.report, config, target)
    if advice_target is None:
        raise ApplyError(f"{target} is not in the scanned project.")
    return build_context(
        advice_target, result.modules, result.project_classes, context_budget(config)
    )


def preview_loop_prompt(path: Path, target: str, config: Config) -> str:
    """`--dry-run`: ilk iterasyonun öneri istemi (geri beslemesiz)."""
    from rlens.advise.prompts import build_user_prompt

    return build_user_prompt(_context(path, target, config))


def run_loop(
    path: Path,
    target: str,
    config: Config,
    provider,
    *,
    max_iter: int | None = None,
    cache=None,
    budget: Budget | None = None,
    arch_context: bool = True,
    metric_rules: bool = False,
) -> LoopResult:
    """Döngüyü koşar. Kullanıcının çalışma ağacı hiçbir iterasyonda değişmez.

    `arch_context` / `metric_rules`: `advise`'ın A/B eksenleri (`--no-arch-context`,
    `--metric-rules`); LensBench koşulları bunları değiştirir.
    """
    scheme = config.arch.scheme if arch_context and config.arch is not None else None
    limit = max_iter or (config.loop.max_iter if config.loop else 3)
    budget = budget or Budget(config.budget)
    context = _context(path, target, config)
    result = LoopResult(target=target, max_iter=limit)
    feedback: str | None = None

    for number in range(1, limit + 1):
        item = Iteration(number=number, feedback=feedback)
        calls, tokens_in, tokens_out = budget.calls, budget.tokens_in, budget.tokens_out
        try:
            advice, _ = request_advice(
                provider,
                context,
                config,
                cache=cache,
                budget=budget,
                scheme=scheme,
                metric_rules=metric_rules,
                feedback=feedback,
            )
            if not advice.is_structured or not advice.suggestions:
                item.outcome = NO_SUGGESTION
                result.iterations.append(item)
                result.stop_reason = NO_SUGGESTION
                break
            item.advice_status = advice.suggestions[0].status
            document = {"advices": [advice.to_dict()]}
            applied = run_apply(
                path, document, target, 1, config, provider, cache=cache, budget=budget
            )
        except BudgetExceeded:
            result.stop_reason = BUDGET
            break
        except ProviderRequestTooLarge:
            # Yeniden denenmez: denemek yalnızca sığan örneklemleri seçerdi.
            result.stop_reason = PROVIDER_LIMIT
            break
        except ProviderTruncated:
            # Aynı mantık: kesilme bizim sınırımızdır, yeniden denemek kısa
            # yanıtları seçerdi (ön kayıt N3).
            result.stop_reason = OUTPUT_LIMIT
            break
        finally:
            item.calls = budget.calls - calls
            item.tokens_in = budget.tokens_in - tokens_in
            item.tokens_out = budget.tokens_out - tokens_out

        item.title = applied.title
        item.outcome = applied.outcome
        item.branch = applied.branch if applied.gate and applied.gate.passed else None
        item.gate_passed = None if applied.gate is None else applied.gate.passed
        item.predictions = applied.predictions
        item.apply = applied.to_dict()
        item.refactorings = [r["kind"] for r in applied.refactorings or []]
        for suggestion in (applied.predictions or {}).get("suggestions", []):
            for check in suggestion.get("checks", []):
                outcome = check.get("outcome")
                item.hits += outcome == "hit"
                item.misses += outcome == "miss"
                item.unverifiable += outcome not in ("hit", "miss")
        item.brier = iteration_calibration(applied.predictions).brier
        result.iterations.append(item)

        if applied.outcome == NO_GATE:
            result.stop_reason = STOP_NO_GATE
            break
        if item.all_held:
            result.stop_reason = ALL_HELD
            break
        feedback = build_feedback(applied)
    else:
        result.stop_reason = MAX_ITER
    return result
