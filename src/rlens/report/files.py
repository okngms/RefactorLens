"""JSON rapor yazımı ve okunması.

**Adlandırma şeması kasıtlıdır.** Rapor adı zaman damgası içerir
(`scan-20260829-141530.json`), böylece art arda yapılan taramalar birbirini
ezmez ve `verify` "en son rapor"u ada göre bulabilir. Zaman damgası UTC'dir;
yerel saat kullanılsaydı yaz saati geçişinde sıralama bozulurdu.

**`schema_version` her raporun kökündedir.** Metrik kuralları sürümler arasında
değişeceği için, iki raporu karşılaştıran `verify` bu alanı kontrol etmek
zorundadır; olmadan sessizce yanlış delta üretir.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from rlens.analysis.model import SCHEMA_VERSION, ProjectReport

REPORT_PREFIX = "scan-"
REPORT_SUFFIX = ".json"
TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"


class ReportError(Exception):
    """Rapor yazılamadığında veya okunamadığında yükseltilir."""


def report_filename(moment: datetime | None = None) -> str:
    """Zaman damgalı rapor dosyası adı üretir."""
    moment = moment or datetime.now(UTC)
    return f"{REPORT_PREFIX}{moment.strftime(TIMESTAMP_FORMAT)}{REPORT_SUFFIX}"


def write_report(report: ProjectReport, output_dir: Path) -> Path:
    """Raporu JSON olarak yazar ve yazılan yolu döndürür.

    Dizin yoksa oluşturulur — kullanıcıdan `mkdir` beklemek gereksiz sürtünmedir.
    """
    output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ReportError(f"Rapor dizini oluşturulamadı: {output_dir} ({exc})") from exc

    target = output_dir / report_filename()
    payload = report.to_dict()

    try:
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise ReportError(f"Rapor yazılamadı: {target} ({exc})") from exc

    return target


def list_reports(output_dir: Path) -> list[Path]:
    """Dizindeki raporları eskiden yeniye sıralar.

    Ad zaman damgalı ve sabit uzunlukta olduğu için alfabetik sıralama
    kronolojik sıralamayla aynıdır.
    """
    output_dir = Path(output_dir)
    if not output_dir.is_dir():
        return []
    return sorted(output_dir.glob(f"{REPORT_PREFIX}*{REPORT_SUFFIX}"))


def latest_report(output_dir: Path) -> Path | None:
    """En son yazılmış rapor, yoksa None."""
    reports = list_reports(output_dir)
    return reports[-1] if reports else None


def read_report(path: Path) -> dict:
    """Bir raporu okur ve şema sürümünü doğrular.

    Şema sürümü eksikse veya bilinmeyense hata verilir; sessizce devam etmek
    `verify` aşamasında yanlış delta üretir.
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportError(f"Rapor okunamadı: {path} ({exc})") from exc

    if not isinstance(payload, dict):
        raise ReportError(f"Rapor bir JSON nesnesi değil: {path}")

    version = payload.get("schema_version")
    if version is None:
        raise ReportError(f"Raporda `schema_version` yok: {path}")
    if not isinstance(version, int):
        raise ReportError(f"`schema_version` tam sayı olmalı: {path}")
    if version > SCHEMA_VERSION:
        raise ReportError(
            f"Rapor şema sürümü {version}, bu rlens sürümü en fazla "
            f"{SCHEMA_VERSION} okuyabiliyor: {path}"
        )

    return payload
