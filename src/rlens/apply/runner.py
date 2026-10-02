"""`apply` akışı: öneriden branch'e (`docs/02` §2, Aşama 1).

1. Repo ve temiz ağaç denetimi; `tests.command` yoksa çağrı yapılmadan durulur.
2. İzole worktree; "önce" taraması worktree'de (HEAD ile aynı).
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
    commit_paths,
    create_worktree,
    discard,
    ensure_clean,
    release,
    repository_root,
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
    if config.tests is None or not config.tests.command:
        raise ApplyError(
            "Set `tests.command` in rlens.yaml (for example 'pytest -q'). `apply` never "
            "lands a change that has not passed your own tests."
        )
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

        if not _patch_until_applied(
            result, work, original, allowed, config, provider, cache, budget
        ):
            discard(work)
            return result

        result.gate = run_gate(config.tests.command, work.path, timeout=config.tests.timeout)
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
