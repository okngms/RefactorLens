# DAM ve fiili açıklık — ön kayıt

v2.2, K7'nin açık bıraktığı DAM sorusu. **Bu bölüm ölçümden önce yazıldı**
(2026-09-22) ve sonuçlar görüldükten sonra değiştirilmez; sonuçlar "Ölçüm"
bölümüne eklenir.

## Durum

- K7'nin çürütme koşulu ("kütüphanelerin çoğunda yayılım yoksa DAM düşer")
  kapsama ölçümünde sınandı: kütüphanelerin 7'sinden 6'sında yayılım var,
  koşul **tetiklenmedi**. DAM kalır.
- DAM değiştirilemez: `data_class` kokusunun koşulu ve kanıt alanı, `advise`
  prompt'unun metrik listesi (ikisi de deney protokolü sonrası donmuş).
  "Yeniden tanım" bu yüzden DAM'ın **yerine** değil **yanına** yeni bir ölçüdür.
- K7 bir ölçümü açık bıraktı: DAM'ın proje içi / projeler arası varyans
  ayrıştırması ("DAM projenin adlandırma geleneğini ölçüyor" yorumu için).

## Soru 1 — DAM'ın varyansı nereden geliyor

Bilgi taşıyan DAM değerlerinde (en az iki attribute'lu sınıflar) η² = projeler
arası kareler toplamı / toplam kareler toplamı. Projeler eşit ağırlıkla değil,
sınıf sayısıyla girer (netbox ve yt-dlp baskın olur); bu yüzden ikinci bir
değer de raporlanır: her projeden en fazla 200 sınıf, sabit tohumla.

**Yorum kuralı (ölçümden önce):** iki değerden de η² ≥ 0.5 ise "DAM ağırlıkla
projenin geleneğini ölçüyor" iddiası **desteklenir**; ikisi de < 0.3 ise
**çürür**; arada ise kararsız diye yazılır.

## Soru 2 — aday ölçü: fiili açıklık (EXP)

DAM niyeti ölçer (`_x` adı: "dışarıdan kullanmayın"). EXP olguyu ölçer:
sınıfın attribute'larından kaçına sınıfın dışından erişiliyor.

1. **Neyi sayıyor.** Sınıf C'nin attribute kümesi `assigned_attributes(C)`
   (DAM'ın kümesi). Projedeki bütün modüllerde, alıcısı `self`/`cls` olmayan
   her `X.a` erişimi bir **dış erişimdir** (`self.a` alt sınıfta olsa bile iç
   sayılır: kalıtım hiyerarşisinin içi). Bir attribute adı **çözülebilir**
   ise — projede o adı attribute kümesinde taşıyan **tek** sınıf C ise — dış
   erişim C.a'ya bağlanır. EXP(C) = dışarıdan erişilen çözülebilir attribute /
   C'nin çözülebilir attribute'ları.
2. **Birim.** Sınıf; erişim taraması proje genelinde (DCC gibi iki geçiş).
3. **Aralık, yön.** 0..1. Yön yok: yüksek "kötü" değil, sınıfın verisinin
   dışarıya açık kullanıldığı demek (veri sınıfı için beklenen durum).
4. **Hesaplanamaz.** Çözülebilir attribute yoksa `null`.
5. **Altın değerler.** `tests/test_exposure.py`, elle, koddan önce.
6. **Bilinen yanlış pozitif / negatifler.** Üçüncü parti bir nesnenin aynı adlı
   attribute'una erişim (`response.status`, projede tek `status` taşıyan
   sınıf varsa) yanlışlıkla açıklık sayılır. `getattr(obj, "a")`, ORM'in
   string ile erişimi ve şablon dilleri (Django template) görülmez. Aynı adı
   taşıyan iki sınıfın attribute'u çözülemez ve paydaya girmez.
7. **Kanıt alanları.** Koku yok. Kabul edilirse yeni rapor alanı
   `classes[].exposure` (şema artışı yok, `04` §1). DAM ve `data_class`
   değişmez; prompt'a girmez.
8. **Eşik.** Tanımlanmaz (K11 gibi betimsel).
9. **Geçerlilik iddiası ve çürütme — ölçümden önce.** İddia: EXP, bir sınıfın
   verisine sınıf dışından ne kadar dokunulduğunu isim çözümünün izin verdiği
   ölçüde ölçer. Aday şu koşullardan **herhangi biri** gerçekleşirse
   reddedilir ve araca eklenmez:
   - (a) **Çözülebilirlik:** projelerin medyanında attribute'ların %50'sinden
     azı çözülebiliyorsa (ölçü çoğu yerde tanımsız).
   - (b) **Ayrım:** DAM'ın yayılım göstermediği 7 projenin (fastapi, pipx,
     healthchecks, netbox, saleor, mealie, yolov5; `coverage.md`) **4'ünden
     azında** EXP yayılım (p10 < p90, en az 30 bilgi taşıyan sınıf)
     gösteriyorsa (DAM'ın sessiz olduğu yerde de sessiz).
   - (c) **Adlandırmayla tutarlılık:** çözülebilir attribute'lar arasında `_`
     önekli olanların dışarıdan erişilme payı, öneksizlerinkinden **küçük
     olmayan** projeler, uygun projelerin (her iki grupta en az 20 attribute)
     **%20'sinden fazlaysa** (konvansiyonu yakalayamayan ölçü isim
     çakışmasını ölçüyordur).
   - (d) **Elle kesinlik:** dışarıdan erişildi denen çözülebilir
     attribute'lardan sabit tohumla çekilen 30 örneğin erişim satırı okunur;
     erişilen nesnenin gerçekten C'nin örneği (ya da alt sınıfı) olduğu
     30'un **24'ünden azında** doğrulanırsa (kesinlik < %80). Kararlar
     `exposure-verdicts.json`'a satır numarasıyla yazılır.

**Kabulün tavanı.** (a)-(d) geçerse EXP betimsel bir alan olarak eklenir;
DAM'ın yerini almaz. `data_class` koşulu değişmez.

---

## Ölçüm

*Bu bölüm ölçümden sonra eklendi; yukarısı değiştirilmedi.*

```bash
python experiments/hardening/exposure_measure.py measure   # ~3 dk
python experiments/hardening/exposure_measure.py summary   # (d)
```

Çıktılar `results/exposure.json`, `results/exposure-tables.md` (proje başına
tablo orada); elle kesinlik örneklemi `exposure-sample.json`, kararlar
`exposure-verdicts.json` (her biri dosya:satır ve gerekçeyle). İkisi birlikte
yeniden koşulduğunda birebir aynı.

### Soru 1 — DAM'ın varyansı

| | η² |
|---|---:|
| bütün bilgi taşıyan sınıflar | 0.7361 |
| proje başına en fazla 200 sınıf | 0.4978 |

Ön kayıtlı okuma: **kararsız** (ikisi de ≥ 0.5 değil; ikisi de < 0.3 değil).
Sınıf sayısıyla ağırlıklı değer, en büyük iki web uygulamasının DAM'da tek
değere yığılmasıyla tutarlı (netbox bilgi taşıyan sınıflarının %97'si,
saleor'un %98.5'i 0; `coverage.json`); her projeye eşit söz verildiğinde
projeler arası pay yarının hemen altına iniyor. Farkın başka nedeni
incelenmedi. K7'nin
"projenin adlandırma geleneği" yorumu ne desteklendi ne çürüdü: DAM'ın
varyansının kabaca yarısı ile dörtte üçü projeler arası farktan geliyor.

### Soru 2 — EXP

- (a) Çözülebilir attribute payı projelerin medyanında **%44.7** < %50:
  **gerçekleşti.** En düşükler netbox %11.5, yt-dlp %12.7, saleor %23.6.
  Ölçülen çakışma: netbox'ta `queryset` 1242, `name` 329, `status` 275 sınıfın
  attribute kümesinde; saleor'da `name` 190, `id` 158 sınıfta. yt-dlp için
  çakışma sayılmadı.
- (b) DAM'ın sessiz olduğu 7 projenin **7'sinde** EXP yayılım gösteriyor:
  gerçekleşmedi.
- (c) Adlandırmayla tutarsız proje **2/15**: gerçekleşmedi. `_` önekli
  attribute'lar dışarıdan belirgin biçimde daha az erişiliyor (ör. awscli
  10/768'e karşı 218/549).
- (d) Elle kesinlik **25/30** (%83): gerçekleşmedi. Yanlış beşi isim
  çakışması: torch `GradScaler.scale`, `RequestDirector.close`,
  `dict.values`, `sys.path`, SAML öğesinin `.text`'i. Doğru 25'in beşinde
  nesnenin türü değişken adından ve bağlamdan çıkarıldı; kararlarda
  "inferred" diye işaretli.

**Sonuç: reddedildi (a).** Ön kayda göre EXP araca eklenmedi. DAM ve
`data_class` değişmedi.

### Bulgular

1. **Ölçü çözülebildiği yerde çalışıyor, çözülebildiği yer az.** (b), (c),
   (d) geçti: EXP DAM'ın sessiz olduğu projelerde ayırıyor, adlandırma
   konvansiyonunu yakalıyor ve bağladığı erişimlerin %83'ü doğru. Ama tipik
   projede attribute'ların yarısından fazlası çözülemiyor ve en çok ihtiyaç
   duyulan yerde (web uygulamaları, DAM'ın sessiz olduğu yer) çözülebilirlik
   en düşük.
2. **Darboğaz isim çözümü.** Yalnızca `ast` ile (kilitli karar) bir `X.a`
   erişiminin hangi sınıfa ait olduğu ancak ad tekse bilinebiliyor. K11'in
   anotasyon kapsamı, annotation'lı projelerde alıcının türünü imzadan
   okumayı mümkün kılabilir; bu ayrı bir aday (FUTURE.md) ve kendi ön
   kaydını gerektirir.
3. **`_` konvansiyonu Python'da gerçekten uyuluyor.** Çözülebilir `_`
   attribute'larının dışarıdan erişilme payı, uygun 15 projenin 13'ünde
   öneksizlerinkinden düşük. DAM'ın ölçtüğü niyet kodda bir karşılık buluyor;
   sorun DAM'ın bir sınıfın hangi verisinin dışarıda kullanıldığını
   söylememesi.
