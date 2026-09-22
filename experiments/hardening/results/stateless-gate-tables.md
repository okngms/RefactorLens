<!-- Üretildi: experiments/hardening/stateless_gate.py. Elle düzenlemeyin. -->

Scan şeması 3. Boyut koşulunu geçen 159 sınıf; bugünkü kapı 96 sınıfta ateşliyor, 3'ü taslak arayüz.

## Dağılım (en az iki durumlu metot adı olan sınıflar)

| Ölçü | proje | p50 | p75 | p90 | p95 |
|---|---:|---:|---:|---:|---:|
| lcom4_stateful | 13 | 1 | 2 | 2 | 2 |
| lcom3_stateful | 13 | 2 | 2 | 3 | 3.8 |

## Adaylar

| Aday | eşik | ateşler | yeni | kayıp | ateşleyen içinde durumsuz | ateşleyen taslak arayüz | çürütme |
|---|---:|---:|---:|---:|---:|---:|---|
| R1 | - | 93 | 0 | 3 | 41 | 0 | yok |
| R2 | - | 91 | 0 | 5 | 39 | 3 | b |
| R3 | 2 | 64 | 13 | 45 | 23 | 0 | c |
| R4 | 3 | 70 | 17 | 43 | 28 | 0 | yok |
