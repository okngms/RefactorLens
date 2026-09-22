<!-- Üretildi: experiments/hardening/density_gate.py. Elle düzenlemeyin. -->

Scan şeması 3. En az iki farklı adlı metodu olan sınıflar; proje başına persentil, projelerin medyanı (17 proje, en az 30 sınıf).

## Dağılım

| Ölçü | p5 | p10 | p25 | p50 | p75 | p90 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| TCC | 0 | 0 | 0 | 0.059 | 0.368 | 1 | 1 |
| LCOM3-HM | 1 | 1 | 2 | 3 | 5 | 7.300 | 11 |

| Aday | sınıfların payı |
|---|---:|
| TCC < 0.05 | %47.6 |
| TCC < 0.1 | %52.4 |
| TCC < 0.2 | %59.2 |
| TCC < 0.333 | %73.8 |
| LCOM3-HM >= 3 | %53.5 |
| LCOM3-HM >= 5 | %26.2 |
| LCOM3-HM >= 10 | %7.4 |

## Kapılar — boyut koşulunu geçen 159 sınıf

Durumsuz: metotlarının en az %50'si hiçbir attribute'a dokunmuyor (65 büyük sınıf). Yeni / kayıp: bugünkü `lcom4 >= 3` kapısına göre.

| Kapı | ateşler | yeni | kayıp | yeni içinde durumsuz | ateşleyen içinde durumsuz |
|---|---:|---:|---:|---:|---:|
| lcom4 >= 3 | 96 | 0 | 0 | 0 | 44 |
| lcom3 >= 3 | 157 | 61 | 0 | 21 | 65 |
| lcom3 >= 5 | 151 | 56 | 1 | 21 | 65 |
| lcom3 >= 10 | 115 | 35 | 16 | 21 | 65 |
| tcc < 0.05 | 56 | 15 | 55 | 15 | 53 |
| tcc < 0.1 | 74 | 20 | 42 | 19 | 61 |
| tcc < 0.2 | 101 | 32 | 27 | 21 | 65 |
| tcc < 0.333 | 125 | 44 | 15 | 21 | 65 |

## Durumsuz metotların türü — büyük sınıflar

Metot: bütün büyük sınıflardaki durumsuz metot adları. Baskın: durumsuz sınıflardan kaçında bu tür en kalabalık (eşitlikte birden fazla türe sayılır).

| Tür | metot | baskın olduğu durumsuz sınıf |
|---|---:|---:|
| stub | 283 | 3 |
| no_receiver | 285 | 6 |
| delegates | 2481 | 38 |
| self_unused | 1018 | 20 |
