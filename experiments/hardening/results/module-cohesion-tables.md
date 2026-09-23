<!-- Üretildi: experiments/hardening/module_cohesion.py. Elle düzenlemeyin. -->

Scan şeması 3. MCOH: durum + kullanım kenarı; MCOH-S: yalnız durum kenarı.

## Ön kayıtlı koşullar

| Değişken | çift | R medyanı | R < 1 payı | tamamen dağınık (medyan) | yayılım | (a) | (b) | (c) |
|---|---:|---:|---:|---:|---|---|---|---|
| mcoh | 3193 | 1.0 | %39.5 | %12.6 | 16/16 | ret | geçti | geçti |
| mcoh_s | 4388 | 1.0 | %18.0 | %79.5 | 16/16 | ret | ret | geçti |

## Sonradan eklenen analiz (ön kayıtta yok)

Kullanan modül M'nin bütün birimlerini alıyorsa seçim yoktur ve R tanım gereği 1'dir. Yalnız seçim yapılan çiftler:

| Değişken | bilgi taşıyan çift | R medyanı | R < 1 payı |
|---|---:|---:|---:|
| mcoh | 2811 | 1.0 | %44.9 |
| mcoh_s | 3836 | 1.0 | %20.6 |

## Proje başına

| Proje | tür | modül | MCOH p50 | MCOH p90 | MCOH dağınık | MCOH-S p50 | MCOH-S p90 | MCOH-S dağınık | çift (MCOH) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| requests | library | 13 | 2.0 | 2.8 | %30.8 | 5.0 | 22.4 | %100.0 | 15 |
| httpx | library | 18 | 1.5 | 4.3 | %11.1 | 7.0 | 12.6 | %88.9 | 22 |
| rich | library | 37 | 1.0 | 3.0 | %10.8 | 3.0 | 13.2 | %67.6 | 48 |
| pydantic | library | 55 | 2.0 | 5.0 | %12.7 | 4.0 | 17.8 | %69.1 | 37 |
| fastapi | library | 18 | 2.5 | 4.0 | %16.7 | 5.0 | 16.8 | %77.8 | 18 |
| attrs | library | 12 | 2.5 | 6.7 | %41.7 | 4.0 | 29.7 | %83.3 | 12 |
| click | library | 14 | 2.0 | 8.8 | %0.0 | 9.5 | 18.8 | %57.1 | 20 |
| flask | library | 18 | 2.0 | 5.0 | %22.2 | 4.0 | 11.5 | %88.9 | 18 |
| sqlalchemy | library | 37 | 2.0 | 8.0 | %2.7 | 8.0 | 20.0 | %35.1 | 82 |
| pandas | library | 130 | 2.0 | 4.0 | %12.3 | 5.0 | 17.1 | %83.9 | 223 |
| black | cli | 19 | 2.0 | 4.2 | %5.3 | 9.0 | 18.2 | %47.4 | 25 |
| mypy | cli | 105 | 1.0 | 3.0 | %9.5 | 7.0 | 28.0 | %63.8 | 145 |
| httpie | cli | 52 | 1.0 | 3.0 | %15.4 | 4.0 | 9.0 | %86.5 | 23 |
| yt-dlp | cli | 441 | 1.0 | 2.0 | %16.3 | 3.0 | 8.0 | %95.9 | 234 |
| awscli | cli | 294 | 1.0 | 4.0 | %6.8 | 4.0 | 14.0 | %78.9 | 163 |
| pipx | cli | 43 | 1.0 | 2.0 | %0.0 | 9.0 | 18.4 | %53.5 | 65 |
| healthchecks | web_app | 68 | 2.0 | 4.0 | %26.5 | 3.0 | 12.5 | %85.3 | 41 |
| netbox | web_app | 446 | 3.0 | 13.0 | %46.6 | 4.0 | 17.0 | %94.2 | 393 |
| saleor | web_app | 652 | 2.0 | 6.0 | %22.7 | 4.0 | 14.0 | %87.3 | 1192 |
| redash | web_app | 105 | 1.0 | 5.0 | %12.4 | 3.0 | 11.0 | %71.4 | 149 |
| mealie | web_app | 150 | 1.0 | 3.0 | %16.0 | 3.0 | 8.0 | %80.0 | 156 |
| nanogpt | ml_research | 3 | 2.0 | 2.0 | %33.3 | 2.0 | 5.2 | %66.7 | 0 |
| yolov5 | ml_research | 38 | 1.5 | 8.2 | %10.5 | 4.0 | 18.4 | %50.0 | 69 |
| detectron2 | ml_research | 97 | 1.0 | 4.0 | %12.4 | 4.0 | 8.0 | %75.3 | 34 |
| whisper | ml_research | 11 | 1.0 | 2.0 | %0.0 | 3.0 | 16.0 | %81.8 | 7 |
| segment-anything | ml_research | 7 | 1.0 | 7.2 | %14.3 | 3.0 | 11.6 | %100.0 | 2 |
