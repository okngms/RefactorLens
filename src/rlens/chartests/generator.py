"""Karakterizasyon testi üretimi, ön doğrulama ve kapı seviye 2 (`docs/02` §3).

Model, hedef sınıfın **bugünkü** davranışını kaydeden pytest testleri yazar.
Testler doğruluk iddia etmez; mevcut davranışı belgeler (EMSE 2026'daki
yüksek davranışsal tutarsızlık bulgusuna karşı savunma). Refactoring'den önce
değişmemiş kodda koşulurlar:

1. Geçmeyen her test fonksiyonu atılır (parametreli testin bir durumu
   düşerse fonksiyonun tamamı).
2. Kalanlar yeniden koşulur ve geçmek zorundadır; düşen kararsızdır, atılır;
   üçüncü koşu da yeşil değilse hiçbir test tutulmaz.
3. Geçme oranı (`kept / generated`) raporlanır.

Testler worktree'de `.rlens-chartests/` altına yazılır: tarayıcı nokta ile
başlayan dizinleri atlar, metriklere karışmazlar; patch onlara dokunamaz
(izinli dosya değiller) ve commit'e girmezler.

**Hangi Python.** Testler `chartests.python` ile koşar, rlens'in kendi
yorumlayıcısıyla değil: rlens pipx ile kurulduğunda projenin bağımlılıkları
onun ortamında yoktur. O Python'da pytest kurulu olmalıdır.

**Bu, modelin yazdığı kodu çalıştırmaktır.** `tests.command`'dan farklı
olarak kodu kullanıcı yazmadı; yalnızca worktree'de, zaman limitiyle koşar.
README bunu açıkça söyler; `--dry-run` istemi gösterir.
"""

from __future__ import annotations

import ast
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from rlens.apply.gate import GateResult
from rlens.apply.worktree import ApplyError

#: Üretilen testlerin dizini, taranan köke göre. Nokta ile başlar: tarayıcı atlar.
CHARTESTS_DIR = ".rlens-chartests"
CHARTESTS_FILE = "test_characterization.py"

SYSTEM_INSTRUCTION = """\
You write characterization tests: pytest tests that record what the code does \
today, so that a later refactoring can be checked against it.

Rules you must follow:

1. Assert the behaviour the code has now, even if it looks wrong. Do not fix \
or judge it.
2. Cover the public methods of the target class. Use pytest.raises for the \
exceptions the code raises today.
3. Write top-level test functions named test_..., no test classes.
4. Keep the tests deterministic and isolated: no network, no clock, no \
randomness, no files outside pytest's tmp_path.
5. Reply with a single ```python fenced block containing the whole test file.
"""

_FENCE = re.compile(r"```python[ \t]*\n(.*?)```", re.DOTALL)

#: Ön doğrulamada en fazla kaç koşu (ilk koşu + iki doğrulama).
MAX_RUNS = 3


class ChartestsFormatError(ValueError):
    """Yanıt sözleşmeye uymuyor."""


@dataclass
class ChartestsResult:
    generated: int = 0
    kept: int = 0
    dropped: list[str] = field(default_factory=list)
    code: str = ""
    """Ön doğrulamadan geçen test dosyası."""
    reason: str | None = None
    """Hiç test tutulmadıysa neden."""
    runs: int = 0
    reply: str | None = None

    @property
    def pass_rate(self) -> float | None:
        return round(self.kept / self.generated, 4) if self.generated else None

    def to_dict(self) -> dict:
        return {
            "generated": self.generated,
            "kept": self.kept,
            "pass_rate": self.pass_rate,
            "dropped": list(self.dropped),
            "runs": self.runs,
            "reason": self.reason,
            "code": self.code,
            "reply": self.reply,
        }


def build_chartests_prompt(target: str, path: str, source: str, per_method_cases: int) -> str:
    module, _, name = target.partition(":")
    return "\n".join(
        [
            f"Target: {target}",
            f"Import it with: from {module} import {name}",
            f"Write up to {per_method_cases} cases per public method of {name}.",
            "",
            f"### {path}",
            "```python",
            source.rstrip("\n"),
            "```",
            "",
        ]
    )


def parse_tests(reply: str) -> str:
    blocks = _FENCE.findall(reply)
    if not blocks:
        raise ChartestsFormatError("The reply contains no ```python block.")
    if len(blocks) > 1:
        raise ChartestsFormatError(
            f"The reply contains {len(blocks)} ```python blocks; expected one."
        )
    return blocks[0]


def _test_functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test")
    ]


def _without(code: str, names: set[str]) -> str:
    """Adı verilen üst düzey test fonksiyonlarını, dekoratörleriyle birlikte siler.

    Satır aralığıyla silinir (`ast.unparse` değil): kalan kodun biçimi korunur.
    """
    lines = code.splitlines(keepends=True)
    doomed = [node for node in _test_functions(ast.parse(code)) if node.name in names]
    for node in sorted(doomed, key=lambda n: n.lineno, reverse=True):
        start = min([node.lineno, *(d.lineno for d in node.decorator_list)]) - 1
        del lines[start : node.end_lineno]
    return "".join(lines)


def _command(python: str, test_file: str, extra: list[str]) -> list[str]:
    # `-o addopts=` kullanıcının pytest ayarındaki eklentileri (ör. --cov) devre
    # dışı bırakır: yalnızca bu dosyanın sonucu sorulur.
    return [
        python,
        "-m",
        "pytest",
        test_file,
        "-q",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        *extra,
    ]


def _run(scan_root: Path, python: str, timeout: int, junit: Path | None = None):
    relative = f"{CHARTESTS_DIR}/{CHARTESTS_FILE}"
    extra = [f"--junitxml={junit}"] if junit is not None else []
    try:
        return subprocess.run(
            _command(python, relative, extra),
            cwd=scan_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ApplyError(
            f"`chartests.python` ({python}) could not be run: {exc}. Set it to the "
            "Python of your project's environment, with pytest installed."
        ) from exc


def _outcomes(junit: Path) -> tuple[set[str], set[str]]:
    """(geçen fonksiyonlar, geçmeyen fonksiyonlar). Parametre kimliği atılır."""
    passed: set[str] = set()
    failed: set[str] = set()
    if not junit.exists():
        return passed, failed
    for case in ET.parse(junit).getroot().iter("testcase"):
        name = case.get("name", "").split("[", 1)[0]
        bad = any(child.tag in ("failure", "error", "skipped") for child in case)
        (failed if bad else passed).add(name)
    return passed - failed, failed


def validate(code: str, scan_root: Path, *, python: str, timeout: int) -> ChartestsResult:
    """Testleri değişmemiş kodda koşar, geçmeyenleri atar, kalanları doğrular."""
    result = ChartestsResult()
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        result.reason = f"The test file does not parse: {exc.msg} (line {exc.lineno})."
        return result
    result.generated = len(_test_functions(tree))
    if not result.generated:
        result.reason = "The reply contains no test function."
        return result

    target = Path(scan_root) / CHARTESTS_DIR / CHARTESTS_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    current = code
    dropped: list[str] = []
    with tempfile.TemporaryDirectory() as scratch:
        for run in range(1, MAX_RUNS + 1):
            target.write_text(current, encoding="utf-8")
            junit = Path(scratch) / f"run{run}.xml"
            try:
                done = _run(scan_root, python, timeout, junit)
            except subprocess.TimeoutExpired:
                result.reason = f"The tests did not finish within {timeout} seconds."
                break
            result.runs = run
            if "No module named pytest" in done.stdout + done.stderr:
                raise ApplyError(f"pytest is not installed for `chartests.python` ({python}).")
            names = {node.name for node in _test_functions(ast.parse(current))}
            passed, _ = _outcomes(junit)
            failing = names - passed
            if not failing:
                if run > 1:
                    result.kept = len(names)
                    result.code = current
                    break
                continue  # ilk koşu yeşil: bir kez daha, kararsızlığa karşı
            dropped += sorted(failing)
            current = _without(current, failing)
            if not names - failing:
                result.reason = "No characterization test passed on the current code."
                break
        else:
            result.reason = "The tests did not settle: some failed on every rerun."
    result.dropped = dropped
    if result.kept:
        target.write_text(result.code, encoding="utf-8")
    else:
        result.code = ""
        target.unlink(missing_ok=True)
    return result


def run_chartests(scan_root: Path, *, python: str, timeout: int) -> GateResult:
    """Kapı seviye 2: tutulan karakterizasyon testleri (değişiklikten sonra)."""
    started = time.perf_counter()
    try:
        done = _run(scan_root, python, timeout)
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return GateResult(2, False, None, time.perf_counter() - started, True, output[-4000:])
    output = "\n".join((done.stdout + done.stderr).splitlines()[-40:])
    return GateResult(
        level=2,
        passed=done.returncode == 0,
        exit_code=done.returncode,
        duration=time.perf_counter() - started,
        timed_out=False,
        output_tail=output,
    )
