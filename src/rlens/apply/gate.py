"""Davranış kapısı, seviye 1: kullanıcının test komutu (`docs/02` §3, invariant 6).

RefactorLens hedef kodu kendisi çalıştırmaz; kullanıcının `tests.command`'ını
worktree'de, zaman limitiyle, alt süreçte çalıştırır. Bu, v1-v2'nin "kod
çalıştırmaz" garantisinden bilinçli bir sapmadır ve yalnızca `apply` için
geçerlidir (`docs/02` §2.6).

Komut kabuk üzerinden çalışır: kullanıcı onu kendi config'ine yazdı, bir
Makefile satırıyla aynı güven düzeyindedir, ve `pytest -q && mypy .` gibi
bileşik komutlar ancak böyle çalışır. Zaman aşımında kabuk süreci öldürülür;
Windows'ta kabuğun başlattığı alt süreçler hayatta kalabilir (bilinen sınır).
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

#: Rapora konan çıktının son kaç satırı.
TAIL_LINES = 40


@dataclass(frozen=True)
class GateResult:
    level: int
    passed: bool
    exit_code: int | None
    """Zaman aşımında `None`."""
    duration: float
    timed_out: bool
    output_tail: str

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "passed": self.passed,
            "exit_code": self.exit_code,
            "duration": round(self.duration, 2),
            "timed_out": self.timed_out,
            "output_tail": self.output_tail,
        }


def _tail(text: str) -> str:
    return "\n".join(text.splitlines()[-TAIL_LINES:])


def run_gate(command: str, cwd: Path, *, timeout: int) -> GateResult:
    """Komutu `cwd`'de koşar; çıkış kodu 0 ise kapı geçer."""
    started = time.perf_counter()
    try:
        done = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return GateResult(1, False, None, time.perf_counter() - started, True, _tail(output))
    return GateResult(
        level=1,
        passed=done.returncode == 0,
        exit_code=done.returncode,
        duration=time.perf_counter() - started,
        timed_out=False,
        output_tail=_tail(done.stdout + done.stderr),
    )
