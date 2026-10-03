"""LensBench koşusu: her (hedef × koşul × tekrar) bir `loop` koşusu.

* **Dondurma:** her proje geçici bir git deposuna kopyalanır (tek commit);
  kullanıcının deposu hiç kullanılmaz. Projenin içerik özeti sonuca yazılır.
* **Önbellek yok:** tekrarlar bağımsız örneklemlerdir; önbellek aynı yanıtı
  döndürüp varyansı sıfırlardı.
* **Kayıt:** her birim bitince `journal.jsonl`'e yazılır. Kesilen koşu aynı
  komutla yeniden başlatılınca biten birimler atlanır; anahtar suite, istem
  ve proje özetlerini taşır, biri değiştiyse eski sonuç kullanılmaz.
* **Bütçe:** birim başına ayrı bütçe (`MAX_CALLS_PER_UNIT`); `loop3` en kötü
  durumda iterasyon başına 5 çağrı ister.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from rlens import __version__
from rlens.bench.suite import IGNORED_PARTS, BenchError, Suite, project_hash, prompt_hash
from rlens.config import load_config
from rlens.llm.budget import Budget
from rlens.loop.runner import run_loop

BENCH_SCHEMA_VERSION = 1
MAX_CALLS_PER_UNIT = 40
JOURNAL = "journal.jsonl"


def plan(suite: Suite) -> list[tuple[int, int, int]]:
    """(hedef indeksi, koşul indeksi, tekrar) üçlüleri, sabit sırada."""
    return [
        (t, c, r)
        for t in range(len(suite.targets))
        for c in range(len(suite.conditions))
        for r in range(1, suite.repeats + 1)
    ]


def estimate_calls(suite: Suite) -> tuple[int, int]:
    """(en az, en çok) çağrı. En az: her iterasyon öneri + patch, onarımsız.

    En çok: her çağrı bir onarım ister ve `loop` hiç erken durmaz; testsiz
    projede iterasyon başına bir karakterizasyon çağrısı daha.
    """
    low = high = 0
    for t, c, _ in plan(suite):
        condition = suite.conditions[c]
        extra = 0 if suite.targets[t].tests else 1
        low += 2 + extra
        high += condition.max_iter * (4 + extra)
    return low, high


def materialize(source: Path, workdir: Path) -> Path:
    """Projeyi tek commit'lik bağımsız bir git deposuna kopyalar."""
    target = workdir / source.name
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(*IGNORED_PARTS, "*.pyc"))
    (target / ".gitignore").write_text(
        "reports/\n.rlens-cache/\n__pycache__/\n.pytest_cache/\n", encoding="utf-8"
    )
    identity = ["-c", "user.name=LensBench", "-c", "user.email=bench@localhost"]
    for args in (
        ["init", "-q", "-b", "main"],
        ["add", "."],
        [*identity, "commit", "-q", "-m", "frozen"],
    ):
        subprocess.run(["git", *args], cwd=target, check=True, capture_output=True)
    return target


def unit_config(project: Path, suite: Suite, target, provider: str, model: str, python: str):
    config = load_config(search_from=project)
    command = target.tests.format(python=f'"{python}"') if target.tests else None
    return replace(
        config,
        # N3: öneri çağrıları da patch'lerle aynı çıktı sınırını alır.
        provider=replace(
            config.provider,
            name=provider,
            model=model,
            max_output_tokens=config.apply.max_output_tokens,
        ),
        advise=replace(config.advise, temperature=suite.temperature),
        tests=replace(config.tests, command=command),
        chartests=replace(config.chartests, enabled_when_no_tests=True, python=python),
        budget=replace(config.budget, max_calls_per_run=MAX_CALLS_PER_UNIT),
    )


def _key(header: dict, target: str, condition: str, repeat: int) -> str:
    project = header["project_hashes"]
    return json.dumps(
        [header["suite_hash"], header["prompt_hash"], project, target, condition, repeat],
        sort_keys=True,
    )


def _load_journal(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    done = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            done[record["key"]] = record["unit"]
    return done


def run_bench(
    suite: Suite,
    repo_root: Path,
    provider_name: str,
    model: str,
    adapter,
    out_dir: Path,
    *,
    python: str | None = None,
    progress=None,
) -> Path:
    """Suite'i koşar ve sonuç dosyasının yolunu döndürür."""
    python = python or sys.executable
    projects = sorted({target.project for target in suite.targets})
    sources = {name: Path(repo_root) / name for name in projects}
    missing = [name for name, path in sources.items() if not path.is_dir()]
    if missing:
        raise BenchError(f"Suite projects not found: {', '.join(missing)}")
    header = {
        "schema_version": BENCH_SCHEMA_VERSION,
        "suite": suite.name,
        "suite_hash": suite.sha,
        "prompt_hash": prompt_hash(),
        "project_hashes": {name: project_hash(path) for name, path in sources.items()},
        "rlens_version": __version__,
        "provider": provider_name,
        "model": model,
        "temperature": suite.temperature,
        "repeats": suite.repeats,
    }
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    journal = out_dir / JOURNAL
    done = _load_journal(journal)
    units: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="lensbench-") as scratch:
        copies = {name: materialize(path, Path(scratch)) for name, path in sources.items()}
        for t, c, repeat in plan(suite):
            target, condition = suite.targets[t], suite.conditions[c]
            key = _key(header, target.target, condition.name, repeat)
            if key in done:
                units.append(done[key])
                continue
            project = copies[target.project]
            config = unit_config(project, suite, target, provider_name, model, python)
            result = run_loop(
                project,
                target.target,
                config,
                adapter,
                max_iter=condition.max_iter,
                cache=None,
                budget=Budget(config.budget),
                arch_context=condition.arch_context,
                metric_rules=condition.metric_rules,
            )
            unit = {
                "project": target.project,
                "target": target.target,
                "condition": condition.name,
                "repeat": repeat,
                "loop": result.to_dict(),
            }
            units.append(unit)
            with journal.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"key": key, "unit": unit}, ensure_ascii=False) + "\n")
            if progress:
                progress(len(units), len(plan(suite)), unit)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"{suite.name}-{stamp}.json"
    payload = {**header, "generated_at": stamp, "units": units}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def run_rotation(entries, run_one, *, wait_minutes: int = 0, sleep=time.sleep, log=print):
    """Modelleri sırayla koşar; kotaya takılan modeli bırakıp sıradakine geçer.

    Bütün kalan modeller takıldıysa ve `wait_minutes` > 0 ise o kadar bekleyip
    takılanları yeniden dener: ücretsiz katmanın günlük sınırı kayan bir
    pencere olduğu için her bekleme ilerleme getirir. Kota dışındaki
    sağlayıcı hataları (yetki, model yok) koşuyu durdurur.

    Returns:
        (biten modeller {etiket: sonuç yolu}, takılı kalan modeller)
    """
    from rlens.providers.base import ProviderRateLimited

    done = {}
    pending = list(entries)
    while pending:
        blocked = []
        for entry in pending:
            try:
                done[entry.label] = run_one(entry)
            except ProviderRateLimited as exc:
                log(f"{entry.label}: rate limited ({str(exc)[:160]}); moving on.")
                blocked.append(entry)
        if not blocked or wait_minutes <= 0:
            return done, blocked
        log(f"{len(blocked)} model(s) rate limited; waiting {wait_minutes} minutes.")
        sleep(wait_minutes * 60)
        pending = blocked
    return done, []
