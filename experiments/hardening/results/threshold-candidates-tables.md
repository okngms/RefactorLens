<!-- Üretildi: experiments/hardening/thresholds.py. Elle düzenlemeyin. -->

Scan şeması 3. Proje başına pay, projelerin medyanı; paydası en az 30 olan projeler.

## LCOM4 adayları

Sınıf payları diğer sınıf eşikleri mevcut değerindeyken (NOM >= 20, WMC >= 50, DCC >= 7).

| LCOM4 >= | hesaplanan içinde | bilgi taşıyan içinde | en az bir eşik aşan sınıf | yalnız LCOM4 yüzünden |
|---:|---:|---:|---:|---:|
| 2 | %32.1 (18) | %60.4 (17) | %21.7 | %11.0 |
| 3 | %13.9 (18) | %22.3 (17) | %15.5 | %5.1 |
| 4 | %7.5 (18) | %14.3 (17) | %11.3 | %2.3 |
| 5 | %5.5 (18) | %10.4 (17) | %11.0 | %1.1 |
| 6 | %3.2 (18) | %5.3 (17) | %9.5 | %0.6 |
| 7 | %2.5 (18) | %4.9 (17) | %9.5 | %0.2 |
| 8 | %1.6 (18) | %2.6 (17) | %8.9 | %0.0 |
| 9 | %1.5 (18) | %2.6 (17) | %8.9 | %0.0 |
| 10 | %1.1 (18) | %2.6 (17) | %8.9 | %0.0 |

## LCOM4 adayları — tür bazında, hesaplanan içinde

| LCOM4 >= | library | cli | web_app | ml_research |
|---:|---:|---:|---:|---:|
| 2 | %42.6 (7) | %23.9 (4) | %32.2 (5) | %24.3 (2) |
| 3 | %24.0 (7) | %12.8 (4) | %13.0 (5) | %9.7 (2) |
| 4 | %12.5 (7) | %6.1 (4) | %7.9 (5) | %3.1 (2) |
| 5 | %10.9 (7) | %2.9 (4) | %5.8 (5) | %1.7 (2) |
| 6 | %5.0 (7) | %1.5 (4) | %2.7 (5) | %0.6 (2) |
| 7 | %4.0 (7) | %1.1 (4) | %1.4 (5) | %0.0 (2) |
| 8 | %4.0 (7) | %0.8 (4) | %1.1 (5) | %0.0 (2) |
| 9 | %4.0 (7) | %0.6 (4) | %0.7 (5) | %0.0 (2) |
| 10 | %2.7 (7) | %0.5 (4) | %0.7 (5) | %0.0 (2) |

## `too_many_params` ve yalnızca-anahtar parametreler

| Koku | yalnızca-anahtar sayılmasa kaybolur | havuz payı | proje medyanı |
|---:|---:|---:|---:|
| 2221 | 554 | %24.9 | %20.8 |
