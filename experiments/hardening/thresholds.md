# Eşik adayları — kalibrasyon korpusu

Sertleştirme Blok 1b, eşik kararı (`docs/v2-sertlestirme.md`). 26 proje, scan
şeması 3. Karar `docs/v2-tanim-kararlari.md` K8'de; varsayılanların persentil
kaynağı `docs/04` §3'te.

```bash
python experiments/hardening/corpus.py fetch     # bir kez, ~850 MB
python experiments/hardening/thresholds.py       # ~2 dk
```

Çıktılar: `results/threshold-candidates.json` ve
`results/threshold-candidates-tables.md`; ikisi de tekrar üretildiğinde birebir
aynı. Ağırlıklandırma dağılım tablosuyla aynı: pay proje başına, genel değer
projelerin medyanı, paydası en az 30 olan projeler.

**Doğrulama.** LCOM4 ≥ 2 ve ≥ 4 için "hesaplanan içinde" payı (%32.1, %7.5)
dağılım tablosunun v2.0.0 varsayılanlarıyla ürettiği değerlere birebir eşit.
`too_many_params` sayımı her projede raporun koku sayısına eşit olmak zorunda;
değilse betik sonuç üretmez.

## Karar kuralı

Kural, dağılım tablosunun "korunur" dediği eşiklerden türetildi; yeni bir sayı
seçilmedi:

- **Uyarı:** proje medyanında birimlerin en fazla **%6.9**'unu işaretleyen en
  küçük tamsayı. %6.9, korunan uyarı eşiklerinin en gevşeğinin (CC ≥ 10)
  payı; diğerleri PARAMS %5.1, DCC %4.8, WMC %2.7, NESTING %2.6, NOM %1.3,
  `long_method` LOC %6.5.
- **Kritik:** en fazla **%1.2**'yi işaretleyen en küçük tamsayı; tek kritik
  referans CC ≥ 20.

Kural gürültüye üst sınır koyar, hedef pay koymaz. Korunan eşiklerden daha
tutucu olanlar (NOM, WMC, NESTING) bu yüzden düşürülmez: düşürmek yeni uyarı
üretir ve korpusta işaretlenen birimlerin gerçekten sorunlu olduğunu gösteren
bir doğruluk verisi yok. Yükseltmenin durumu farklı: sınıfların üçte birini
işaretleyen bir eşik tanım gereği "olağan dışı"yı işaretlemiyordur.

## LCOM4

<!-- results/threshold-candidates-tables.md -->

| LCOM4 >= | hesaplanan içinde | bilgi taşıyan içinde | en az bir eşik aşan sınıf | yalnız LCOM4 yüzünden |
|---:|---:|---:|---:|---:|
| 2 | %32.1 (18) | %60.4 (17) | %21.7 | %11.0 |
| 3 | %13.9 (18) | %22.3 (17) | %15.5 | %5.1 |
| 4 | %7.5 (18) | %14.3 (17) | %11.3 | %2.3 |
| **5** | **%5.5** (18) | %10.4 (17) | %11.0 | %1.1 |
| 6 | %3.2 (18) | %5.3 (17) | %9.5 | %0.6 |
| 7 | %2.5 (18) | %4.9 (17) | %9.5 | %0.2 |
| 8 | %1.6 (18) | %2.6 (17) | %8.9 | %0.0 |
| 9 | %1.5 (18) | %2.6 (17) | %8.9 | %0.0 |
| **10** | **%1.1** (18) | %2.6 (17) | %8.9 | %0.0 |

"En az bir eşik aşan sınıf" ve "yalnız LCOM4 yüzünden" bütün sınıflar içinde
(metotsuz sınıflar dahil), diğer sınıf eşikleri mevcut değerindeyken (NOM ≥ 20,
WMC ≥ 50, DCC ≥ 7).

Tür bazında, hesaplanan içinde:

| LCOM4 >= | library | cli | web_app | ml_research |
|---:|---:|---:|---:|---:|
| 2 | %42.6 (7) | %23.9 (4) | %32.2 (5) | %24.3 (2) |
| 4 | %12.5 (7) | %6.1 (4) | %7.9 (5) | %3.1 (2) |
| 5 | %10.9 (7) | %2.9 (4) | %5.8 (5) | %1.7 (2) |
| 10 | %2.7 (7) | %0.5 (4) | %0.7 (5) | %0.0 (2) |

### Bulgular

1. **Kural uyarıda 5, kritikte 10 veriyor.** 4, %7.5 ile üst sınırın hemen
   üstünde; 5, %5.5 ile içinde. Dağılım tablosunda LCOM4 p95 = 4.65, p99 = 9.35:
   yeni eşikler ≈ p95 ve ≈ p99'a oturuyor — diğer metriklerin uyarı/kritik
   bandı.
2. **Kullanıcının gördüğü etki.** Tipik projede en az bir eşiği aşan sınıf payı
   %21.7'den %11.0'a iniyor. v2.0.0'da sınıfların %11.0'ı yalnızca LCOM4
   yüzünden işaretleniyordu; 5'te bu pay %1.1.
3. **Payda duyarlılığı.** Tek adlı metotlu sınıflar (`coverage.md`) çıkarılınca
   5'in payı %10.4'e çıkıyor. Kural diğer metriklerle aynı paydayla
   (hesaplanmış bütün değerler) uygulandı; bilgi taşıyan payda seçilseydi kural
   6'yı (%5.3) verirdi. Aradaki fark bir tamsayı.
4. **Tür farkı sürüyor.** 5'te kütüphanelerde pay %10.9, cli'de %2.9.
   Kütüphane sınıfları LCOM4'te genel olarak daha bölünmüş görünüyor; nedeni
   incelenmedi (`metric-distribution.md` Bulgu 2).

## `too_many_params` ve yalnızca-anahtar parametreler

| Koku | yalnızca-anahtar sayılmasa kaybolur | havuz payı | proje medyanı |
|---:|---:|---:|---:|
| 2221 | 554 | %24.9 | %20.8 |

Yalnızca-anahtar parametreleri saymamak kokuların dörtte birini kaldırırdı.
Bu PARAMS'ın **tanımını** değiştirir (şema artışı) ve hangi kokuların kaybolması
gerektiği sorusunu cevaplamaz: `*` ile zorlanan anahtar parametreler çağrıyı
okunur kılar ama çağıranın bilmesi gereken şey sayısını azaltmaz. Eşik
değişmedi; seçenek ve ölçümü v2.2'nin girdisi (`FUTURE.md`).
