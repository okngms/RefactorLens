<!-- Üretildi: experiments/hardening/dynamic_opacity.py. Elle düzenlemeyin. -->

Scan şeması 3. Oran: 1000 fonksiyon başına opak nokta. Toplam 1805 nokta; korpus medyanı 34.47.

| Proje | tür | fonksiyon | nokta | 1000 başına | noktası olan fonksiyon | getattr | setattr | delattr | hasattr | eval | exec | import | kwargs | kancalı sınıf |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| requests | library | 176 | 32 | 181.82 | %14.8 | 0 | 2 | 0 | 0 | 0 | 0 | 1 | 29 | 0/44 |
| flask | library | 290 | 41 | 141.38 | %11.7 | 6 | 0 | 0 | 0 | 1 | 1 | 2 | 31 | 1/46 |
| attrs | library | 117 | 13 | 111.11 | %8.6 | 8 | 1 | 1 | 0 | 1 | 0 | 0 | 2 | 1/33 |
| netbox | web_app | 3151 | 328 | 104.09 | %8.4 | 93 | 25 | 0 | 6 | 0 | 3 | 3 | 198 | 4/4116 |
| pandas | library | 3996 | 375 | 93.84 | %6.4 | 90 | 10 | 0 | 10 | 1 | 0 | 0 | 264 | 7/246 |
| sqlalchemy | library | 1673 | 126 | 75.31 | %5.5 | 43 | 17 | 4 | 6 | 0 | 1 | 0 | 55 | 7/256 |
| whisper | ml_research | 112 | 7 | 62.5 | %6.2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 7 | 0/36 |
| yolov5 | ml_research | 472 | 29 | 61.44 | %4.7 | 4 | 8 | 0 | 0 | 8 | 1 | 0 | 8 | 0/99 |
| fastapi | library | 134 | 8 | 59.7 | %6.0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0/89 |
| pydantic | library | 756 | 44 | 58.2 | %4.5 | 22 | 9 | 1 | 3 | 0 | 0 | 0 | 9 | 6/179 |
| detectron2 | ml_research | 901 | 45 | 49.94 | %3.5 | 13 | 7 | 0 | 2 | 0 | 1 | 1 | 21 | 4/213 |
| saleor | web_app | 6622 | 269 | 40.62 | %3.4 | 67 | 13 | 0 | 5 | 0 | 0 | 3 | 181 | 2/2535 |
| click | library | 354 | 13 | 36.72 | %3.4 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 8/66 |
| awscli | cli | 5587 | 180 | 32.22 | %2.5 | 78 | 13 | 1 | 11 | 0 | 0 | 7 | 70 | 6/1394 |
| mealie | web_app | 1371 | 43 | 31.36 | %1.8 | 23 | 12 | 0 | 3 | 0 | 0 | 0 | 5 | 0/662 |
| yt-dlp | cli | 4787 | 145 | 30.29 | %2.9 | 6 | 2 | 0 | 1 | 0 | 0 | 1 | 135 | 4/2323 |
| redash | web_app | 1346 | 34 | 25.26 | %2.3 | 8 | 2 | 0 | 0 | 0 | 2 | 3 | 19 | 1/247 |
| httpie | cli | 375 | 9 | 24.0 | %2.4 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 6 | 1/105 |
| black | cli | 363 | 7 | 19.28 | %1.9 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0/44 |
| healthchecks | web_app | 710 | 7 | 9.86 | %0.9 | 5 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0/214 |
| mypy | cli | 4636 | 41 | 8.84 | %0.5 | 17 | 4 | 1 | 11 | 0 | 0 | 5 | 3 | 2/420 |
| pipx | cli | 567 | 4 | 7.05 | %0.4 | 3 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0/91 |
| httpx | library | 309 | 2 | 6.47 | %0.7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0/85 |
| rich | library | 582 | 3 | 5.15 | %0.5 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 2 | 1/170 |
| nanogpt | ml_research | 17 | 0 | 0.0 | %0.0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/6 |
| segment-anything | ml_research | 81 | 0 | 0.0 | %0.0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/19 |

## Tür medyanları (betimsel)

| library | cli | web_app | ml_research |
|---:|---:|---:|---:|
| 67.505 | 21.64 | 31.36 | 49.94 |

## Ön kayıtlı koşullar

- (b) medyanın üstündeki metaprogramlama kütüphaneleri: attrs, pydantic, sqlalchemy → ret: **hayır**
- (c) belirteci satırında bulunmayan nokta: **0**
- (a) elle kesinlik 27/30 < 24: **hayır**
