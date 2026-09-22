<!-- Üretildi: experiments/hardening/exposure_measure.py. Elle düzenlemeyin. -->

Scan şeması 3.

## Soru 1 — DAM'ın varyansı

- η² (bütün bilgi taşıyan sınıflar): 0.7361
- η² (proje başına en fazla 200 sınıf): 0.4978
- Ön kayıtlı okuma: **kararsız**

## Soru 2 — EXP

| Proje | tür | çözülebilir | EXP sınıf | p10 | p50 | p90 | yayılım | `_` erişilen/toplam | öneksiz erişilen/toplam |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|
| requests | library | %60.3 | 12 | 0.0 | 0.0 | 1.0 | - | 3/14 | 12/24 |
| httpx | library | %66.5 | 34 | 0.0 | 0.0 | 1.0 | evet | 3/27 | 34/116 |
| rich | library | %53.4 | 94 | 0.0 | 0.3333 | 1.0 | evet | 18/83 | 130/284 |
| pydantic | library | %37.1 | 68 | 0.0 | 0.0 | 1.0 | evet | 3/38 | 67/137 |
| fastapi | library | %43.3 | 36 | 0.0 | 0.0 | 1.0 | evet | 0/1 | 60/174 |
| attrs | library | %59.3 | 20 | 0.0 | 0.0 | 1.0 | - | 4/24 | 10/30 |
| click | library | %60.8 | 43 | 0.0 | 0.0 | 0.6674 | evet | 4/28 | 42/135 |
| flask | library | %65.8 | 23 | 0.0 | 0.3333 | 0.9286 | - | 1/13 | 41/89 |
| sqlalchemy | library | %44.7 | 104 | 0.0 | 0.6667 | 1.0 | evet | 123/190 | 200/328 |
| pandas | library | %31.9 | 92 | 0.0 | 0.3333 | 1.0 | evet | 27/83 | 94/226 |
| black | cli | %84.7 | 32 | 0.0 | 1.0 | 1.0 | evet | 0/10 | 91/134 |
| mypy | cli | %51.5 | 203 | 0.0 | 1.0 | 1.0 | evet | 8/49 | 558/808 |
| httpie | cli | %56.5 | 53 | 0.0 | 0.5 | 1.0 | evet | 0/14 | 90/148 |
| yt-dlp | cli | %12.7 | 401 | 0.0 | 0.0 | 1.0 | evet | 39/609 | 184/296 |
| awscli | cli | %38.4 | 494 | 0.0 | 0.0 | 0.8 | evet | 10/768 | 218/549 |
| pipx | cli | %34.7 | 46 | 0.0 | 1.0 | 1.0 | evet | 0/25 | 74/100 |
| healthchecks | web_app | %28.9 | 67 | 0.0 | 0.8125 | 1.0 | evet | 0/4 | 86/169 |
| netbox | web_app | %11.5 | 425 | 0.0 | 0.0 | 1.0 | evet | 20/72 | 294/1806 |
| saleor | web_app | %23.6 | 529 | 0.0 | 0.5 | 1.0 | evet | 2/24 | 1083/1943 |
| redash | web_app | %31.1 | 57 | 0.0 | 0.0 | 1.0 | evet | 0/15 | 64/131 |
| mealie | web_app | %25.1 | 188 | 0.0 | 0.25 | 1.0 | evet | 5/31 | 284/523 |
| nanogpt | ml_research | %60.7 | 6 | 0.0 | 0.2916 | 1.0 | - | 0/0 | 6/17 |
| yolov5 | ml_research | %37.1 | 43 | 0.0 | 0.3158 | 1.0 | evet | 0/2 | 49/157 |
| detectron2 | ml_research | %47.9 | 125 | 0.0 | 0.0 | 1.0 | evet | 5/108 | 67/199 |
| whisper | ml_research | %65.8 | 19 | 0.0 | 0.0 | 1.0 | - | 0/0 | 37/96 |
| segment-anything | ml_research | %78.3 | 17 | 0.0 | 0.0 | 0.44 | - | 0/1 | 13/82 |

## Ön kayıtlı çürütme koşulları

- (a) çözülebilir pay medyanı %44.7 < %50: **evet**
- (b) DAM'ın sessiz olduğu 7 projeden yayılım gösteren 7 < 4: **hayır**
- (c) adlandırmayla tutarsız proje 2/15 > %20: **hayır**
- (d) elle kesinlik 25/30 < 24: **hayır**
