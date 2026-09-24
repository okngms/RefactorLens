"""Gerçek projede dayanıklılık ve süre: sertleştirme Blok 2, madde 1.

    python experiments/hardening/robustness.py [--only a,b]

Korpusun her projesinde üç komut **CLI olarak** (alt süreçte) koşulur:
`rlens scan`, `rlens arch`, `rlens advise --dry-run`. Kullanıcının gördüğü
yol budur: içe aktarma, config, render ve rapor yazımı dahil. `corpus.py
inventory` yalnızca `scan_project` süresini ölçer; bu betik uçtan uca.

Kaydedilenler:

* `results/robustness.json` — çıkış kodları, atlanan dosyaların nedenleri
  (kategori ve dosya), `advise --dry-run`'ın seçtiği hedef sayısı, her hedefin
  tahmini bağlam token'ı ve `budget.max_tokens_per_call`'ı aşıp gerçek koşuda
  atlanacak prompt sayısı. Tekrar üretildiğinde birebir aynı çıkmalı.
* `results/robustness-timing.json` — komut başına duvar saati süresi. Ortama
  bağlı, ayrı dosyada.

Config tuzağı `corpus.py`'deki gibi: config proje başına açıkça yazılır.
`advise --dry-run` model adı ister (koda gömülmez, AGENTS); dry-run hiçbir
çağrı yapmadığı için buradaki ad yalnızca config doğrulamasını geçer.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import yaml
from corpus import HERE, load_corpus, skip_category

RESULTS = HERE / "results" / "robustness.json"
TIMING = HERE / "results" / "robustness-timing.json"
TABLES = HERE / "results" / "robustness-tables.md"

#: Yalnızca config doğrulaması için; `--dry-run` sağlayıcıyı çağırmaz.
DRY_RUN_MODEL = "dry-run-placeholder"

TOKENS = re.compile(r"^~(\d+) tokens$", re.MULTILINE)
TARGETS = re.compile(r"^(\d+) target\(s\)", re.MULTILINE)
OVERSIZED = re.compile(r"^(\d+) prompt\(s\) exceed the per-call token ceiling", re.MULTILINE)
NOTHING = "Nothing over threshold."


def rlens_command() -> list[str]:
    """Bu yorumlayıcının `rlens`'i: kurulu betik değil, aynı ortam."""
    return [sys.executable, "-m", "rlens.cli"]


def write_config(project, workdir: Path) -> Path:
    """`corpus.project_config` ile aynı kural, artı dry-run için sağlayıcı adı."""
    from rlens.config import DEFAULTS

    excludes = list(DEFAULTS["scan"]["exclude"]) + [f"{name}/" for name in project.excludes]
    path = workdir / f"{project.name}.rlens.yaml"
    raw = {"scan": {"exclude": excludes}, "provider": {"model": DRY_RUN_MODEL}}
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def run(args: list[str]) -> tuple[int, float, str, str]:
    started = time.perf_counter()
    done = subprocess.run(
        rlens_command() + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "200"},
    )
    return done.returncode, time.perf_counter() - started, done.stdout, done.stderr


def tail(text: str, lines: int = 5) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def advise_summary(stdout: str) -> dict:
    """`--dry-run` çıktısından hedefler, prompt tahminleri ve atlanacaklar.

    `oversized`: `budget.max_tokens_per_call`'ı aşan ve gerçek koşuda
    **çağrılmadan atlanacak** prompt sayısı (dry-run kendisi söylüyor).
    """
    if NOTHING in stdout:
        return {"targets": 0, "prompt_tokens": [], "oversized": 0}
    targets = TARGETS.search(stdout)
    oversized = OVERSIZED.search(stdout)
    return {
        "targets": int(targets.group(1)) if targets else None,
        "prompt_tokens": [int(value) for value in TOKENS.findall(stdout)],
        "oversized": int(oversized.group(1)) if oversized else 0,
    }


def skipped_summary(report_path: Path) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    entries = report.get("skipped_files", [])
    categories = Counter(skip_category(entry["reason"]) for entry in entries)
    return {
        "categories": dict(sorted(categories.items())),
        "files": sorted(f"{entry['path']}: {entry['reason']}" for entry in entries),
    }


def measure(project, workdir: Path) -> tuple[dict, dict]:
    config = write_config(project, workdir)
    root = str(project.scan_root)
    out = workdir / project.name
    entry: dict = {"type": project.type}
    timing: dict = {}

    code, seconds, stdout, stderr = run(["scan", root, "-c", str(config), "-o", str(out)])
    entry["scan_exit"] = code
    timing["scan"] = round(seconds, 1)
    reports = sorted(out.glob("scan-*.json"))
    if code in (0, 1) and reports:
        entry["skipped"] = skipped_summary(reports[-1])
    else:
        entry["scan_error"] = tail(stderr or stdout)

    code, seconds, stdout, stderr = run(["arch", root, "-c", str(config), "--no-report"])
    entry["arch_exit"] = code
    timing["arch"] = round(seconds, 1)
    if code not in (0, 1):
        entry["arch_error"] = tail(stderr or stdout)

    code, seconds, stdout, stderr = run(["advise", root, "-c", str(config), "--dry-run"])
    entry["advise_exit"] = code
    timing["advise_dry_run"] = round(seconds, 1)
    if code == 0:
        entry["advise"] = advise_summary(stdout)
    else:
        entry["advise_error"] = tail(stderr or stdout)
    return entry, timing


def tables(results: dict, timing: dict) -> str:
    lines = [
        "# Dayanıklılık ve süre (üretilmiş)",
        "",
        "`robustness.py` çıktısı. Süreler saniye, duvar saati, alt süreç dahil;",
        "ortama bağlıdır.",
        "",
        "| Proje | Tür | scan | arch | advise | Atlanan | Hedef | Prompt token "
        "| Tavanı aşan | scan s | arch s | advise s |",
        "|---|---|---:|---:|---:|---|---:|---|---:|---:|---:|---:|",
    ]
    for name, entry in results["projects"].items():
        skipped = entry.get("skipped", {}).get("categories", {})
        advise = entry.get("advise", {})
        times = timing["projects"][name]
        lines.append(
            f"| {name} | {entry['type']} | {entry['scan_exit']} | {entry['arch_exit']} | "
            f"{entry['advise_exit']} | "
            f"{', '.join(f'{k} {v}' for k, v in skipped.items()) or '—'} | "
            f"{advise.get('targets', '—')} | "
            f"{', '.join(map(str, advise.get('prompt_tokens', []))) or '—'} | "
            f"{advise.get('oversized', '—')} | "
            f"{times['scan']} | {times['arch']} | {times['advise_dry_run']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", default="")
    args = parser.parse_args(argv)

    corpus = load_corpus()
    if args.only:
        wanted = set(args.only.split(","))
        corpus = [project for project in corpus if project.name in wanted]
    missing = [project.name for project in corpus if not project.scan_root.is_dir()]
    if missing:
        print(f"not fetched: {', '.join(missing)} — run `corpus.py fetch` first")
        return 1

    results: dict = {"projects": {}}
    timing: dict = {"note": "wall-clock seconds incl. process start; environment-dependent"}
    timing["projects"] = {}
    with tempfile.TemporaryDirectory() as workdir:
        for project in corpus:
            entry, times = measure(project, Path(workdir))
            results["projects"][project.name] = entry
            timing["projects"][project.name] = times
            print(
                f"{project.name:<17} scan={entry['scan_exit']} arch={entry['arch_exit']} "
                f"advise={entry['advise_exit']}  {times}",
                flush=True,
            )

    if not args.only:
        RESULTS.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        TIMING.write_text(json.dumps(timing, indent=2) + "\n", encoding="utf-8")
        TABLES.write_text(tables(results, timing), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
