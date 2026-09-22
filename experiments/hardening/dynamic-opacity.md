# Dinamik opaklık — ön kayıt

v2.2 §3'ün dört yeni ölçüsünden biri (`docs/v2.2-python-metrikleri.md`).
**Bu bölüm ölçümden önce yazıldı** (2026-09-22) ve sonuçlar görüldükten sonra
değiştirilmez; sonuçlar "Ölçüm" bölümüne eklenir.

## v2.2'nin kendi çürütme koşulu neden olduğu gibi kullanılamıyor

§3'ün örneği: "korpusta dağılım proje tipiyle ilişkisizse **ve** bakımlı
projelerle ihmal edilmişler ayırt edilemiyorsa, ölçü hiçbir şey ayırt
etmiyordur". Korpusun 26 projesinin hepsi bakımlı; ikinci yarı bu korpusta
ölçülemez. Birinci yarı betimsel olarak raporlanır (madde 9, ek). Ret
koşulları aşağıda, ölçülebilir olarak yeniden yazıldı.

## Dokuz madde

1. **Neyi sayıyor.** Bir fonksiyonun kendi kapsamında (iç içe tanımlara
   girilmez; CC ile aynı kural) şu **opak noktalar**:
   - `getattr`, `setattr`, `delattr`, `hasattr` çağrısı, ikinci argümanı
     **string sabiti değilse** (`getattr(x, "a")` izlenebilir, sayılmaz;
     `getattr(x, name)` ve `getattr(x, "visit_" + kind)` sayılır);
   - `eval(...)`, `exec(...)`;
   - `__import__(...)` ve `importlib.import_module(...)`, ilk argümanı string
     sabiti değilse;
   - fonksiyonun **kendi** `**kwargs` parametresinin bir çağrıya `**kwargs`
     olarak aktarılması (hangi anahtarların nereye gittiği imzadan okunamaz).

   Sınıf için ayrıca: sınıf gövdesinde `__getattr__`, `__getattribute__` ya da
   `__setattr__` tanımlı mı.
2. **Birim.** Fonksiyon (`dynamic_sites`: sayı) ve sınıf
   (`dynamic_attribute_hooks`: evet/hayır). Proje düzeyi değer: 1000 fonksiyon
   başına opak nokta.
3. **Aralık, yön.** ≥ 0 tam sayı. **Yön yok:** yüksek "kötü" değil, statik
   analizin ve otomatik refactoring'in o fonksiyonda kör kaldığı yer sayısı.
4. **Hesaplanamaz.** Hiçbir zaman: her fonksiyonun sayısı vardır; 0 geçerli bir
   değerdir (hiç opak nokta yok).
5. **Altın değerler.** `tests/test_dynamic_opacity.py`, elle, koddan önce.
6. **Bilinen yanlış pozitifler.** Ad değişkende ama birkaç satır yukarıda
   sabite bağlanmış (`name = "x"; getattr(o, name)`); ziyaretçi sevki
   (`getattr(self, "visit_" + kind)`) — opak ama deyimsel; dekoratör
   fabrikaları ve `functools.wraps` sarmalayıcılarında `**kwargs` aktarımı;
   plugin yükleyiciler; serileştirme (`setattr(obj, key, value)` döngüleri);
   test mock'ları (testler zaten taranmaz). Bilinen yanlış negatifler:
   `obj.__dict__[name]`, `vars(obj)[name]`, `operator.attrgetter(name)`,
   `type(...)` ile sınıf üretimi sayılmaz.
7. **Kanıt alanları.** Koku yok. Kabul edilirse rapor alanları
   `functions[].dynamic_sites`, `classes[].dynamic_attribute_hooks` (alan
   ekleme, şema artışı yok). `advise` prompt'u donmuş; alanlar prompt'a girmez.
8. **Eşik.** Tanımlanmaz (K11 gibi): ölçü "burada statik analiz kör" der,
   "burası kötü" demez; eşik ikinci iddiayı gizlice sokar.
9. **Geçerlilik iddiası ve çürütme — ölçümden önce.** İddia: sayılan her nokta,
   fonksiyonun kendi kodu okunarak hedefi (attribute adı, çalıştırılan kod,
   import edilen modül, aktarılan anahtarlar) belirlenemeyen bir yerdir. Aday şu
   koşullardan **herhangi biri** gerçekleşirse reddedilir ve araca eklenmez:
   - (a) **Elle kesinlik:** sabit tohumla çekilen 30 opak noktanın **24'ünden
     azında** hedef fonksiyonun kendi kodundan belirlenemiyorsa (kesinlik
     < %80). Her karar `dynamic-verdicts.json`'a dosya:satır ve gerekçeyle
     yazılır.
   - (b) **Beklenen yoğunlaşma:** çalışma zamanında sınıf/attribute üretmeyi
     amaç edinmiş üç kütüphaneden (attrs, pydantic, sqlalchemy) **ikiden
     azının** 1000 fonksiyon başına oranı korpus medyanının üstündeyse. Bu
     liste ölçümden önce, amaçlarına göre seçildi; bir önsel yargıdır ve
     öyle raporlanır.
   - (c) **Uygulama tutarlılığı (ret değil, önce düzeltme):** raporlanan her
     noktanın satırında tetikleyen belirteç (`getattr`, `eval`, `**` ...)
     metin olarak bulunmalı; bulunmayan varsa bu bir uygulama hatasıdır ve
     karar ondan önce düzeltilir.

   Ek (ret koşulu değil): tür bazında oranlar ve v2.2'nin "proje tipiyle
   ilişki" sorusu betimsel olarak raporlanır.

**Kabulün tavanı.** (a) ve (b) geçerse iki alan betimsel olarak rapora eklenir;
koku ve eşik yok.

---

## Ölçüm

*Bu bölüm ölçümden sonra eklendi; yukarısı değiştirilmedi.*

```bash
python experiments/hardening/dynamic_opacity.py measure   # ~2 dk
python experiments/hardening/dynamic_opacity.py summary   # (a)
```

Çıktılar `results/dynamic-opacity.json`, `results/dynamic-opacity-tables.md`
(proje başına tablo orada); elle kesinlik örneklemi `dynamic-sample.json`,
kararlar `dynamic-verdicts.json` (her biri dosya:satır ve gerekçeyle).
Birlikte yeniden koşulduğunda birebir aynı. Ölçü araca taşındıktan sonra
yeniden koşuldu; çıktılar aynı hash'i verdi (aday ile araçtaki tanım özdeş).

Korpusta 1 805 opak nokta: `**kwargs` aktarımı 1 072, `getattr` 491,
`setattr` 129, `hasattr` 59, dinamik import 26, `eval` 11, `exec` 9,
`delattr` 8. Korpus medyanı 1000 fonksiyon başına **34.5**; tipik projede
fonksiyonların %3.1'inde en az bir nokta var. 13 738 sınıfın 55'inde attribute
kancası (`__getattr__` vb.).

### Ön kayıtlı koşullar

- (a) Elle kesinlik **27/30** (%90) ≥ 24: **gerçekleşmedi.** Çözülebilir
  bulunan üçü ön kaydın 6. maddesindeki tür: ad, aynı fonksiyonda yazılmış
  sabit bir liste/demet üzerinde dönen döngü değişkeni (awscli
  `paging_params`, netbox bileşen listesi, healthchecks `update_fields`).
  Opak sayılanlardan biri (requests `status_codes._init`) modül düzeyi bir
  tablodan besleniyor: fonksiyonun kendi kodundan görünmüyor, modülün
  tamamından görünüyor; ön kayıttaki kurala göre opak.
- (b) Üç metaprogramlama kütüphanesinin **üçü** de medyanın üstünde (attrs
  111, sqlalchemy 75, pydantic 58): **gerçekleşmedi.**
- (c) Satırında belirteci bulunmayan nokta **0**.

**Sonuç: çürütülmedi.** Ön kayda göre iki alan araca eklendi (K13).

### Bulgular

1. **Noktaların %59'u `**kwargs` aktarımı.** Opaklığın en yaygın biçimi
   `getattr` değil, çağıranın anahtarlarını olduğu gibi başka bir çağrıya
   geçirmek (saleor mutasyonları, pandas sarmalayıcıları, yt-dlp çıkarıcıları).
   Hangi parametrenin nereye aktığı imzadan okunamıyor.
2. **Tür bazında (betimsel):** library 67.5, ml_research 49.9, web_app 31.4,
   cli 21.6 (1000 fonksiyon başına, projelerin medyanı). v2.2'nin "proje tipiyle
   ilişki" sorusuna kısmi cevap: kütüphaneler belirgin biçimde üstte; ama aynı
   türün içinde fark büyük (library: requests 182, rich 5).
3. **Uçlar:** requests (182), flask (141), attrs (111) üstte; nanoGPT ve
   segment-anything 0, rich 5, httpx 6.
4. **Bilinen yanlış negatifler** (ön kayıtta yazılı, ölçülmedi):
   `obj.__dict__[name]`, `vars(obj)[name]`, `operator.attrgetter`, `type(...)`
   ile sınıf üretimi.
