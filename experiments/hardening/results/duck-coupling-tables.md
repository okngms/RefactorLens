<!-- Üretildi: experiments/hardening/duck_coupling.py. Elle düzenlemeyin. -->

Scan şeması 3. Parametreli fonksiyonlar; toplam 24401 (parametre, attribute) çifti.

| Proje | tür | fonksiyon | p10 | p50 | p90 | yayılım | değer > 0 | modül fonk. değer > 0 | tipli çift | üye payı |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| requests | library | 128 | 0.0 | 0.0 | 2.0 | evet | %32.8 | %31.2 | 1 | %100.0 |
| httpx | library | 195 | 0.0 | 0.0 | 2.0 | evet | %31.3 | %47.5 | 76 | %100.0 |
| rich | library | 403 | 0.0 | 0.0 | 1.0 | evet | %20.6 | %15.0 | 130 | %100.0 |
| pydantic | library | 653 | 0.0 | 0.0 | 2.0 | evet | %31.4 | %38.1 | 61 | %80.3 |
| fastapi | library | 126 | 0.0 | 0.0 | 3.0 | evet | %30.2 | %45.1 | 44 | %90.9 |
| attrs | library | 95 | 0.0 | 0.0 | 2.0 | evet | %34.7 | %34.5 | 2 | %100.0 |
| click | library | 267 | 0.0 | 0.0 | 2.0 | evet | %28.8 | %24.8 | 100 | %95.0 |
| flask | library | 245 | 0.0 | 0.0 | 1.0 | evet | %26.5 | %42.1 | 43 | %37.2 |
| sqlalchemy | library | 1226 | 0.0 | 0.0 | 3.0 | evet | %35.7 | %42.5 | 55 | %89.1 |
| pandas | library | 3001 | 0.0 | 0.0 | 1.0 | evet | %19.9 | %33.6 | 216 | %81.9 |
| black | cli | 327 | 0.0 | 1.0 | 3.0 | evet | %58.4 | %59.6 | 152 | %100.0 |
| mypy | cli | 4213 | 0.0 | 1.0 | 3.0 | evet | %53.0 | %59.5 | 3736 | %79.0 |
| httpie | cli | 282 | 0.0 | 0.0 | 2.0 | evet | %34.8 | %49.7 | 85 | %91.8 |
| yt-dlp | cli | 4414 | 0.0 | 0.0 | 1.0 | evet | %12.7 | %25.0 | 62 | %83.9 |
| awscli | cli | 4419 | 0.0 | 0.0 | 2.0 | evet | %37.2 | %44.5 | 3 | %100.0 |
| pipx | cli | 470 | 0.0 | 1.0 | 3.0 | evet | %50.8 | %57.6 | 287 | %99.0 |
| healthchecks | web_app | 546 | 0.0 | 0.0 | 2.5 | evet | %49.6 | %54.1 | 382 | %63.1 |
| netbox | web_app | 2175 | 0.0 | 0.0 | 2.0 | evet | %48.5 | %46.1 | 3 | %66.7 |
| saleor | web_app | 6094 | 0.0 | 1.0 | 3.0 | evet | %55.2 | %55.8 | 1527 | %94.6 |
| redash | web_app | 833 | 0.0 | 0.0 | 2.0 | evet | %29.3 | %38.3 | 0 | - |
| mealie | web_app | 987 | 0.0 | 0.0 | 2.0 | evet | %37.0 | %45.5 | 390 | %65.6 |
| nanogpt | ml_research | 16 | 0.0 | 0.0 | 1.5 | - | %18.8 | %0.0 | 0 | - |
| yolov5 | ml_research | 418 | 0.0 | 0.0 | 2.0 | evet | %29.7 | %37.5 | 2 | %100.0 |
| detectron2 | ml_research | 713 | 0.0 | 0.0 | 2.0 | evet | %31.3 | %38.4 | 23 | %82.6 |
| whisper | ml_research | 86 | 0.0 | 0.0 | 2.0 | evet | %27.9 | %32.4 | 24 | %95.8 |
| segment-anything | ml_research | 73 | 0.0 | 0.0 | 1.0 | evet | %23.3 | %20.8 | 2 | %100.0 |

## Ön kayıtlı koşullar

- (b) tipli çiftlerde üye payı medyanı (16 proje) %90.0 < %60: **hayır**
- (c) yayılım gösteren proje 25/25 < yarısı: **hayır**
- (a) elle kesinlik 30/30 < 24: **hayır**
