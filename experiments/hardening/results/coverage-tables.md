<!-- Üretildi: experiments/hardening/coverage.py. Elle düzenlemeyin. -->

Scan şeması 3. Paylar birim başına, projelerin medyanı. Yayılım ve mod: bilgi taşıyan en az 30 değeri olan projeler.

## Kapsama — tüm korpus

| Metrik | Birim | Proje | hesaplanan | tanım gereği belli | bilgi taşıyan | yayılım (p10 < p90) | mod | mod payı |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| CC | function | 26 | %100.0 | %0.0 | %100.0 | 25/25 | 1 | %39.6 |
| LOC | function | 26 | %100.0 | %0.0 | %100.0 | 25/25 | 2 | %22.1 |
| PARAMS | function | 26 | %100.0 | %0.0 | %100.0 | 25/25 | 1 | %35.8 |
| NESTING | function | 26 | %100.0 | %0.0 | %100.0 | 25/25 | 0 | %42.4 |
| NOM | class | 26 | %100.0 | %0.0 | %100.0 | 24/24 | 0 | %43.2 |
| WMC | class | 26 | %100.0 | %0.0 | %100.0 | 24/24 | 0 | %39.6 |
| LCOM4 | class | 26 | %63.1 | %21.8 | %35.6 | 17/17 | 1 | %42.9 |
| DCC | class | 26 | %100.0 | %0.0 | %100.0 | 24/24 | 1 | %37.1 |
| DAM | class | 26 | %78.7 | %17.8 | %59.9 | 12/19 | 0 | %86.5 |
| CAM | class | 26 | %27.7 | %6.9 | %15.9 | 8/8 | 0.50 | %23.5 |
| Ca | module | 26 | %100.0 | %0.0 | %100.0 | 17/17 | 1 | %32.1 |
| Ce | module | 26 | %100.0 | %0.0 | %100.0 | 17/17 | 0 | %24.6 |
| I | module | 26 | %96.2 | %0.0 | %96.2 | 17/17 | 0 | %23.4 |

## Bilgi taşıyan pay — tür bazında

Hücre: bilgi taşıyan pay (yayılım gösteren proje / uygun proje).

| Metrik | library | cli | web_app | ml_research |
|---|---:|---:|---:|---:|
| CC | %100.0 (10/10) | %100.0 (6/6) | %100.0 (5/5) | %100.0 (4/4) |
| LOC | %100.0 (10/10) | %100.0 (6/6) | %100.0 (5/5) | %100.0 (4/4) |
| PARAMS | %100.0 (10/10) | %100.0 (6/6) | %100.0 (5/5) | %100.0 (4/4) |
| NESTING | %100.0 (10/10) | %100.0 (6/6) | %100.0 (5/5) | %100.0 (4/4) |
| NOM | %100.0 (10/10) | %100.0 (6/6) | %100.0 (5/5) | %100.0 (3/3) |
| WMC | %100.0 (10/10) | %100.0 (6/6) | %100.0 (5/5) | %100.0 (3/3) |
| LCOM4 | %38.5 (7/7) | %38.1 (4/4) | %27.0 (5/5) | %30.6 (1/1) |
| DCC | %100.0 (10/10) | %100.0 (6/6) | %100.0 (5/5) | %100.0 (3/3) |
| DAM | %53.2 (6/7) | %59.4 (4/5) | %51.9 (1/5) | %69.7 (1/2) |
| CAM | %18.2 (4/4) | %11.5 (1/1) | %5.0 (3/3) | %9.4 (0/0) |
| Ca | %100.0 (5/5) | %100.0 (5/5) | %100.0 (5/5) | %100.0 (2/2) |
| Ce | %100.0 (5/5) | %100.0 (5/5) | %100.0 (5/5) | %100.0 (2/2) |
| I | %100.0 (5/5) | %95.4 (5/5) | %93.7 (5/5) | %93.3 (2/2) |

## Ölçülen mantık payı

Raporun birimlerinin (fonksiyon, metot, sınıf gövdesi) kapsadığı mantık satırı payı; kaynak `corpus-inventory.json`.

| Genel | library | cli | web_app | ml_research | en düşük üç |
|---:|---:|---:|---:|---:|---|
| %97.1 | %97.0 | %97.0 | %97.4 | %98.6 | nanogpt %44.1, httpie %82.5, rich %87.4 |
