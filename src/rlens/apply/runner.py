"""`apply` akışı: öneriden branch'e (`docs/02` §2-3, Aşama 1-2).

1. Repo ve temiz ağaç denetimi. Kapı yoksa çağrı yapılmadan durulur: ya
   `tests.command` (seviye 1) ya da testsiz projede karakterizasyon testleri
   (seviye 2, `chartests.enabled_when_no_tests`).
2. İzole worktree; "önce" taraması worktree'de (HEAD ile aynı). Seviye 2'de
   testler **patch'ten önce** üretilir ve değişmemiş kodda doğrulanır; hiçbiri
   geçmezse patch istenmez (`no_gate`).
3. Patch istenir, ayrıştırılır, dokunduğu dosyalar denetlenir, uygulanır.
   Herhangi bir adım reddederse model tek bir onarım şansı alır.
4. Davranış kapısı. Geçmezse worktree ve branch silinir (`keep_failed` hariç):
   kapıyı geçmeyen bir değişikliğin metrik deltası sayılmaz (invariant).
5. Commit, "sonra" taraması, `verify` mantığıyla sonuç; worktree dizini
   kaldırılır, branch kalır. Araç asla merge etmez.

Beklenmeyen bir hata olursa worktree ve branch yine silinir: yarım kalmış bir
uygulama kullanıcının deposunda iz bırakmamalı.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from rlens.advise.advisor import _generate
from rlens.analysis.scanner import scan_project
from rlens.apply.gate import GateResult, run_gate
from rlens.apply.patch import apply_patch, touched_paths, validate_paths
from rlens.apply.prompts import (
    SYSTEM_INSTRUCTION,
    PatchFormatError,
    build_patch_prompt,
    build_repair_prompt,
    parse_patch,
)
from rlens.apply.worktree import (
    ApplyError,
    Worktree,
    commit_paths,
    create_worktree,
    discard,
    ensure_clean,
    release,
    repository_root,
)
from rlens.chartests.generator import (
    SYSTEM_INSTRUCTION as CHARTESTS_INSTRUCTION,
)
from rlens.chartests.generator import (
    ChartestsFormatError,
    ChartestsResult,
    build_chartests_prompt,
    parse_tests,
    run_chartests,
    validate,
)
from rlens.config import Config
from rlens.providers.base import ProviderError, ProviderTruncated
from rlens.verify import goodhart as goodhart_module
from rlens.verify.diff import UNCHANGED, diff_reports
from rlens.verify.prediction import check_predictions

#: `apply` raporunun biçim sürümü; scan ve advice şemalarından bağımsız.
APPLY_SCHEMA_VERSION = 1

#: `verify`'ın sonuçlarına (improved, regressed, mixed, unchanged) ek olanlar.
SUSPICIOUS = "suspicious"
BROKEN = "broken"
"""Kapı geçmedi; delta hesaplanmaz."""
REJECTED = "rejected"
"""Patch iki denemede de kabul edilmedi; hiçbir şey uygulanmadı."""
NO_GATE = "no_gate"
"""Testsiz projede hiçbir karakterizasyon testi mevcut kodda geçmedi; patch istenmedi."""

MAX_ATTEMPTS = 2


@dataclass
class ApplyResult:
    target: str
    suggestion_index: int
    title: str
    run_id: str
    outcome: str = REJECTED
    branch: str | None = None
    commit: str | None = None
    attempts: int = 0
    patch: str | None = None
    rejections: list[str] = field(default_factory=list)
    replies: list[str] = field(default_factory=list)
    """Her denemenin ham yanıtı; reddedilen yanıt da saklanır (AGENTS: unstructured)."""
    gate: GateResult | None = None
    entity: dict | None = None
    predictions: dict | None = None
    goodhart: dict | None = None
    chartests: dict | None = None
    """Seviye 2: üretilen, tutulan, atılan testler ve geçme oranı."""

    def to_dict(self) -> dict:
        return {
            "schema_version": APPLY_SCHEMA_VERSION,
            "target": self.target,
            "suggestion_index": self.suggestion_index,
            "title": self.title,
            "run_id": self.run_id,
            "outcome": self.outcome,
            "branch": self.branch,
            "commit": self.commit,
            "attempts": self.attempts,
            "patch": self.patch,
            "rejections": list(self.rejections),
            "replies": list(self.replies),
            "gate": None if self.gate is None else self.gate.to_dict(),
            "entity": self.entity,
            "predictions": self.predictions,
            "goodhart": self.goodhart,
            "chartests": self.chartests,
        }


def _suggestion(advice: dict, target: str, index: int) -> dict:
    for entry in advice.get("advices", []):
        if entry.get("target") == target:
            suggestions = entry.get("suggestions", [])
            if not 1 <= index <= len(suggestions):
                noun = "suggestion" if len(suggestions) == 1 else "suggestions"
                raise ApplyError(
                    f"{target} has {len(suggestions)} {noun}; there is no suggestion {index}."
                )
            return suggestions[index - 1]
    raise ApplyError(f"The advice file has no advice for {target}.")


def _target_file(report: dict, target: str, scan_prefix: Path) -> str:
    """Hedefin dosyası, depo köküne göre (patch yolları bu biçimde)."""
    module = target.split(":", 1)[0]
    for entry in report.get("modules", []):
        if entry["module"] == module:
            return (scan_prefix / entry["path"]).as_posix()
    raise ApplyError(f"{target} is not in the scanned project; was the code changed since?")


def _own_output(config: Config, scan_prefix: Path) -> tuple[str, ...]:
    """Aracın kendi çıktı dizinleri (raporlar, önbellek), depo köküne göre.

    İkisi de taranan yola göre çözülür (bkz. `cli._build_cache`); mutlak yollar
    depo dışındadır ve temizlik denetimini ilgilendirmez.
    """
    directories = [config.scan.output_dir]
    if config.cache is not None:
        directories.append(config.cache.directory)
    return tuple(
        (scan_prefix / directory).as_posix()
        for directory in directories
        if directory and not Path(directory).is_absolute()
    )


def _read(base: Path, relative: str) -> str | None:
    path = base / relative
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _gate_mode(config: Config) -> tuple[bool, bool]:
    """(seviye 1, seviye 2). İkisi de yoksa `apply` çalışmaz."""
    level1 = config.tests is not None and bool(config.tests.command)
    chartests = config.chartests
    level2 = not level1 and chartests is not None and chartests.enabled_when_no_tests
    if not (level1 or level2):
        raise ApplyError(
            "Set `tests.command` in rlens.yaml (for example 'pytest -q'), or enable "
            "`chartests.enabled_when_no_tests` for a project without tests. `apply` "
            "never lands a change that has not passed a behaviour gate."
        )
    return level1, level2


def _timeout(config: Config) -> int:
    return config.tests.timeout if config.tests is not None else 300


def chartests_request(target: str, target_file: str, base: Path, config: Config) -> str:
    """Karakterizasyon testi istemi; `base` dosyaların okunduğu kök."""
    source = _read(base, target_file) or ""
    cases = config.chartests.per_method_cases if config.chartests else 3
    return build_chartests_prompt(target, target_file, source, cases)


def generate_chartests(
    target: str,
    target_file: str,
    work: Worktree,
    scan_root: Path,
    config: Config,
    provider,
    cache,
    budget,
) -> ChartestsResult:
    """Testleri ister ve değişmemiş kodda doğrular (seviye 2'nin ön koşulu)."""
    prompt = chartests_request(target, target_file, work.path, config)
    try:
        reply, _, _ = _generate(
            provider, CHARTESTS_INSTRUCTION, prompt, _patch_config(config), cache, budget, target
        )
    except ProviderTruncated as exc:
        return ChartestsResult(
            reason="The reply was cut off at the model's output limit; raise "
            "`apply.max_output_tokens`.",
            reply=exc.partial,
        )
    try:
        code = parse_tests(reply)
    except ChartestsFormatError as exc:
        return ChartestsResult(reason=str(exc), reply=reply)
    result = validate(code, scan_root, python=config.chartests.python, timeout=_timeout(config))
    result.reply = reply
    return result


def preview_prompt(path: Path, advice: dict, target: str, index: int, config: Config) -> str:
    """`--dry-run`: modele gidecek istem, çalışma ağacından; çağrı ve worktree yok."""
    suggestion = _suggestion(advice, target, index)
    root = repository_root(path)
    scan_prefix = Path(path).resolve().relative_to(root)
    report = scan_project(Path(path), config).to_dict()
    target_file = _target_file(report, target, scan_prefix)
    allowed = {target_file, *(config.apply.allow_files if config.apply else ())}
    files = {name: _read(root, name) for name in sorted(allowed)}
    return build_patch_prompt(target, suggestion, files)


def run_apply(
    path: Path,
    advice: dict,
    target: str,
    index: int,
    config: Config,
    provider,
    *,
    cache=None,
    budget=None,
    run_id: str | None = None,
) -> ApplyResult:
    """Bir öneriyi izole bir branch'te uygular ve sonucu ölçer."""
    level1, level2 = _gate_mode(config)
    suggestion = _suggestion(advice, target, index)
    root = repository_root(path)
    scan_prefix = Path(path).resolve().relative_to(root)
    ensure_clean(root, ignore=_own_output(config, scan_prefix))

    run_id = run_id or f"{datetime.now(UTC):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"
    result = ApplyResult(
        target=target,
        suggestion_index=index,
        title=str(suggestion.get("title") or "(untitled)"),
        run_id=run_id,
    )
    work = create_worktree(root, run_id, target)
    try:
        scan_root = work.path / scan_prefix
        before = scan_project(scan_root, config).to_dict()
        target_file = _target_file(before, target, scan_prefix)
        allowed = {target_file, *(config.apply.allow_files if config.apply else ())}
        files = {name: _read(work.path, name) for name in sorted(allowed)}
        original = build_patch_prompt(target, suggestion, files)

        if level2:
            chartests = generate_chartests(
                target, target_file, work, scan_root, config, provider, cache, budget
            )
            result.chartests = chartests.to_dict()
            if not chartests.kept:
                result.outcome = NO_GATE
                discard(work)
                return result

        if not _patch_until_applied(
            result, work, original, allowed, config, provider, cache, budget
        ):
            discard(work)
            return result

        if level1:
            result.gate = run_gate(config.tests.command, work.path, timeout=_timeout(config))
        else:
            result.gate = run_chartests(
                scan_root, python=config.chartests.python, timeout=_timeout(config)
            )
        if not result.gate.passed:
            result.outcome = BROKEN
            if config.apply and config.apply.keep_failed:
                result.branch = work.branch
            else:
                discard(work)
            return result

        result.commit = commit_paths(
            work,
            touched_paths(result.patch),
            f"rlens apply: {target} suggestion {index}\n\n{result.title}\n",
        )
        after = scan_project(scan_root, config).to_dict()
        _measure(result, advice, before, after)
        result.branch = work.branch
        release(work)
        return result
    except BaseException:
        discard(work)
        raise


def _patch_config(config: Config) -> Config:
    """Patch çağrıları için config: çıktı sınırı `apply.max_output_tokens`.

    Kullanıcı `provider.max_output_tokens`'ı daha yüksek verdiyse o kalır.
    """
    limit = config.apply.max_output_tokens if config.apply else None
    current = config.provider.max_output_tokens
    if limit is None or (current is not None and current >= limit):
        return config
    return replace(config, provider=replace(config.provider, max_output_tokens=limit))


def _patch_until_applied(result, work, original, allowed, config, provider, cache, budget) -> bool:
    """Patch'i ister ve uygular; en fazla `MAX_ATTEMPTS` deneme. Başarıda True.

    Kesilen yanıt onarılmaz: aynı sınırla ikinci deneme de kesilir.
    """
    user = original
    config = _patch_config(config)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result.attempts = attempt
        try:
            reply, _, _ = _generate(
                provider, SYSTEM_INSTRUCTION, user, config, cache, budget, result.target
            )
        except ProviderTruncated as exc:
            result.replies.append(exc.partial)
            result.rejections.append(
                f"The reply was cut off at the model's output limit "
                f"({config.provider.max_output_tokens} tokens). Raise "
                "`apply.max_output_tokens` in rlens.yaml, or ask for a smaller change."
            )
            result.outcome = REJECTED
            return False
        except ProviderError as exc:
            # İlk çağrı başarısızsa öğrenilen bir şey yok; hata yukarı gider.
            # Onarım çağrısı başarısızsa ilk denemenin kaydı kaybolmamalı.
            if attempt == 1:
                raise
            result.rejections.append(f"The repair request failed: {exc}")
            result.outcome = REJECTED
            return False
        result.replies.append(reply)
        patch = None
        try:
            patch = parse_patch(reply)
            validate_paths(touched_paths(patch), allowed)
            apply_patch(work, patch)
        except (PatchFormatError, ApplyError) as exc:
            result.rejections.append(str(exc))
            user = build_repair_prompt(original, patch, str(exc))
            continue
        result.patch = patch
        return True
    result.outcome = REJECTED
    return False


def _measure(result: ApplyResult, advice: dict, before: dict, after: dict) -> None:
    """`verify` ile aynı ölçüm: delta, Goodhart, bu önerinin tahminleri."""
    delta = diff_reports(before, after)
    suspicions = goodhart_module.detect(before, after, delta.entities)
    entity = delta.by_name(result.target)
    result.entity = None if entity is None else entity.to_dict()
    outcome = UNCHANGED if entity is None else entity.summarise()
    if any(check.qualified_name == result.target for check in suspicions.suspicious):
        outcome = SUSPICIOUS
    result.outcome = outcome
    result.goodhart = suspicions.to_dict()
    applied = {result.target: [result.suggestion_index]}
    result.predictions = check_predictions(advice, delta, applied).to_dict()


def run_chartests_only(
    path: Path,
    target: str,
    config: Config,
    provider,
    *,
    cache=None,
    budget=None,
) -> ChartestsResult:
    """`rlens chartests`: testleri üretir ve HEAD'de doğrular; hiçbir şey commit'lenmez.

    Doğrulama izole bir worktree'de yapılır: testler kullanıcının ağacında
    koşsaydı `__pycache__` ve test artıkları bırakırdı. Sonuç rapora yazılır;
    test dosyasını projeye eklemek kullanıcının kararıdır.
    """
    root = repository_root(path)
    scan_prefix = Path(path).resolve().relative_to(root)
    ensure_clean(root, ignore=_own_output(config, scan_prefix))
    run_id = f"{datetime.now(UTC):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"
    work = create_worktree(root, run_id, target)
    try:
        scan_root = work.path / scan_prefix
        report = scan_project(scan_root, config).to_dict()
        target_file = _target_file(report, target, scan_prefix)
        return generate_chartests(
            target, target_file, work, scan_root, config, provider, cache, budget
        )
    finally:
        discard(work)


def preview_chartests(path: Path, target: str, config: Config) -> str:
    """`rlens chartests --dry-run`: istem, çalışma ağacından; çağrı ve worktree yok."""
    root = repository_root(path)
    scan_prefix = Path(path).resolve().relative_to(root)
    report = scan_project(Path(path), config).to_dict()
    return chartests_request(target, _target_file(report, target, scan_prefix), root, config)
