<!-- Üretildi: experiments/hardening/unreported.py. Elle düzenlemeyin. -->

Scan şeması 3. Toplam 223 koşullu tanım. Aynı modülde birden fazla birimle görünen ad: bugün raporda 1, koşullu tanımlar da girseydi 48.

Koşul türleri: type_checking 63, import_fallback 18, version_platform 38, other_if 101, other_try 2, other 1

Projelerin medyanı: ölçülmeyen mantık %2.9; bunun koşullu tanımlardan gelen payı %3.0; sınıfsız modül kodu (ölçülmeyen − koşullu) %2.6.

| Proje | tür | koşullu tanım | fonk. | sınıf | TYPE_CHECKING | import yedeği | sürüm/platform | diğer | çakışan ad (bugün / koşullularla) | ölçülmeyen | koşullu payı | sınıfsız kod |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| requests | library | 3 | 3 | 0 | 0 | 1 | 2 | 0 | 0 / 0 | %3.6 | %25.4 | %2.7 |
| httpx | library | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 / 0 | %2.9 | %3.6 | %2.8 |
| rich | library | 16 | 9 | 7 | 0 | 2 | 1 | 13 | 0 / 1 | %12.6 | %3.2 | %12.2 |
| pydantic | library | 47 | 14 | 33 | 34 | 0 | 13 | 0 | 0 / 7 | %8.1 | %29.6 | %5.7 |
| fastapi | library | 45 | 39 | 6 | 0 | 1 | 0 | 44 | 0 / 17 | %3.1 | %67.3 | %1.0 |
| attrs | library | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 / 0 | %1.9 | %2.0 | %1.9 |
| click | library | 10 | 9 | 1 | 0 | 2 | 4 | 4 | 0 / 3 | %3.3 | %49.0 | %1.7 |
| flask | library | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 0 | %2.9 | %0.0 | %2.9 |
| sqlalchemy | library | 23 | 23 | 0 | 23 | 0 | 0 | 0 | 0 / 2 | %1.1 | %7.8 | %1.0 |
| pandas | library | 3 | 2 | 1 | 1 | 0 | 0 | 2 | 0 / 0 | %1.5 | %2.1 | %1.5 |
| black | cli | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 0 | %3.1 | %0.0 | %3.1 |
| mypy | cli | 5 | 5 | 0 | 0 | 0 | 5 | 0 | 0 / 2 | %1.6 | %4.8 | %1.5 |
| httpie | cli | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 / 0 | %17.4 | %2.0 | %17.1 |
| yt-dlp | cli | 18 | 15 | 3 | 2 | 4 | 8 | 4 | 0 / 4 | %0.5 | %9.0 | %0.5 |
| awscli | cli | 35 | 33 | 2 | 0 | 5 | 5 | 25 | 1 / 10 | %2.9 | %9.8 | %2.6 |
| pipx | cli | 3 | 2 | 1 | 0 | 0 | 0 | 3 | 0 / 1 | %3.5 | %3.9 | %3.3 |
| healthchecks | web_app | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 0 | %5.0 | %0.0 | %5.0 |
| netbox | web_app | 2 | 1 | 1 | 0 | 1 | 0 | 1 | 0 / 0 | %2.6 | %0.4 | %2.6 |
| saleor | web_app | 3 | 0 | 3 | 3 | 0 | 0 | 0 | 0 / 0 | %2.3 | %0.2 | %2.3 |
| redash | web_app | 2 | 2 | 0 | 0 | 0 | 0 | 2 | 0 / 0 | %6.6 | %1.7 | %6.5 |
| mealie | web_app | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 0 | %2.2 | %0.0 | %2.2 |
| nanogpt | ml_research | 2 | 2 | 0 | 0 | 0 | 0 | 2 | 0 / 0 | %55.9 | %2.9 | %54.3 |
| yolov5 | ml_research | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 0 | %3.5 | %0.0 | %3.5 |
| detectron2 | ml_research | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 0 / 0 | %1.4 | %3.0 | %1.3 |
| whisper | ml_research | 2 | 2 | 0 | 0 | 0 | 0 | 2 | 0 / 1 | %1.3 | %15.6 | %1.1 |
| segment-anything | ml_research | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 0 | %0.3 | %0.0 | %0.3 |
