<!-- Üretildi: experiments/hardening/distribution.py. Elle düzenlemeyin. -->

Scan şeması 3. Proje başına persentil, projelerin medyanı; projenin katılması için metrikte en az 30 değer.

## Dağılım — tüm korpus

| Metrik | Birim | Proje | p50 | p75 | p90 | p95 | p99 | null | havuz p90 | havuz p99 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CC | function | 25 | 2 | 4 | 8 | 12 | 20 | %0.0 | 8 | 24 |
| LOC | function | 25 | 7 | 17 | 29.50 | 44.95 | 85.58 | %0.0 | 31 | 91 |
| PARAMS | function | 25 | 1 | 2 | 4 | 4.35 | 7 | %0.0 | 4 | 8 |
| NESTING | function | 25 | 1 | 1 | 2 | 3 | 4 | %0.0 | 2 | 4 |
| NOM | class | 24 | 1 | 2 | 5.55 | 9.93 | 17.60 | %0.0 | 5 | 24.63 |
| WMC | class | 24 | 1.25 | 5.50 | 19 | 31 | 66.53 | %0.0 | 15 | 87 |
| LCOM4 | class | 18 | 1 | 2 | 3 | 4.65 | 9.35 | %32.0 | 3 | 11.57 |
| DCC | class | 24 | 1 | 2 | 4.25 | 5.40 | 9.68 | %0.0 | 7 | 21 |
| DAM | class | 21 | 0 | 0 | 0.25 | 0.47 | 1 | %21.6 | 1 | 1 |
| CAM | class | 12 | 0.81 | 1 | 1 | 1 | 1 | %61.6 | 1 | 1 |
| Ca | module | 17 | 1 | 4 | 10 | 20 | 34.48 | %0.0 | 9 | 62 |
| Ce | module | 17 | 3 | 6 | 10 | 12 | 17.60 | %0.0 | 12 | 30 |
| I | module | 17 | 0.67 | 0.83 | 1 | 1 | 1 | %4.5 | 1 | 1 |

## p90 tür bazında

| Metrik | library | cli | web_app | ml_research |
|---|---:|---:|---:|---:|
| CC | 8.50 (10) | 9.50 (6) | 6 (5) | 8.50 (4) |
| LOC | 30 (10) | 34.95 (6) | 25 (5) | 33.90 (4) |
| PARAMS | 4 (10) | 3 (6) | 3 (5) | 4 (4) |
| NESTING | 2 (10) | 2.50 (6) | 2 (5) | 2.50 (4) |
| NOM | 7.80 (10) | 5.85 (6) | 4 (5) | 5 (3) |
| WMC | 25 (10) | 20 (6) | 12 (5) | 21.20 (3) |
| LCOM4 | 5 (7) | 3 (4) | 3 (5) | 2.50 (2) |
| DCC | 4.80 (10) | 3 (6) | 7 (5) | 2.50 (3) |
| DAM | 0.88 (8) | 0.47 (6) | 0 (5) | 0.50 (2) |
| CAM | 1 (7) | 1 (2) | 1 (3) | — (0) |
| Ca | 13.20 (5) | 6 (5) | 10 (5) | 8.40 (2) |
| Ce | 13 (5) | 7 (5) | 10 (5) | 8.50 (2) |
| I | 0.92 (5) | 0.89 (5) | 1 (5) | 1 (2) |

## Mevcut eşikler — eşiği karşılayan pay

Proje başına pay; medyan ve aralık. Eşiğin denk geldiği persentil ≈ 100 − medyan pay.

| Eşik | Proje | medyan | min | max | library | cli | web_app | ml_research | havuz |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CC>=10 (warn) | 25 | %6.9 | %1.2 | %18.5 | %8.1 | %9.5 | %3.7 | %7.5 | %6.7 |
| CC>=20 (critical) | 25 | %1.2 | %0.0 | %6.1 | %1.7 | %2.0 | %0.6 | %2.4 | %1.6 |
| PARAMS>=5 (warn) | 25 | %5.1 | %1.1 | %31.3 | %9.3 | %3.5 | %2.1 | %6.9 | %5.7 |
| NESTING>=4 (warn) | 25 | %2.6 | %0.0 | %8.8 | %3.4 | %2.9 | %2.0 | %3.7 | %2.7 |
| NOM>=20 (warn) | 24 | %1.3 | %0.0 | %18.7 | %2.9 | %1.4 | %0.9 | %1.0 | %1.5 |
| WMC>=50 (warn) | 24 | %2.7 | %0.0 | %21.1 | %6.0 | %1.8 | %1.1 | %4.0 | %2.2 |
| LCOM4>=2 (warn) | 18 | %32.1 | %11.1 | %61.8 | %42.6 | %23.9 | %32.2 | %24.3 | %27.6 |
| LCOM4>=4 (critical) | 18 | %7.5 | %1.2 | %29.1 | %12.5 | %6.1 | %7.9 | %3.1 | %7.5 |
| DCC>=7 (warn) | 24 | %4.8 | %0.0 | %25.2 | %7.9 | %2.1 | %11.5 | %2.8 | %12.3 |
| LOC>=40 (long_method) | 25 | %6.5 | %2.2 | %36.6 | %6.6 | %8.5 | %3.1 | %7.3 | %6.5 |

## `god_class` kapısı (K4)

| Tür | Boyut koşulunu geçen | Ateşlendi | LCOM4'te elendi | Yalnız çağrı kenarı yüzünden |
|---|---:|---:|---:|---:|
| library | 67 | 52 | 15 | 15 |
| cli | 67 | 31 | 36 | 34 |
| web_app | 23 | 12 | 11 | 11 |
| ml_research | 2 | 1 | 1 | 1 |
| all | 159 | 96 | 63 | 61 |

## Koku oranları — 1000 birim başına, projelerin medyanı

`god_class`, `data_class`: 1000 sınıf başına; diğerleri 1000 fonksiyon başına.

| Koku | library | cli | web_app | ml_research |
|---|---:|---:|---:|---:|
| data_class | 0 | 2.15 | 0 | 0 |
| feature_envy_candidate | 57.09 | 49.99 | 77.12 | 67.70 |
| god_class | 17.35 | 1.29 | 1.51 | 0 |
| long_method | 45.88 | 59.10 | 18.31 | 58.82 |
| too_many_params | 92.81 | 35.23 | 21.15 | 63.26 |
