# Duck typing yapısal kuplajı — ön kayıt

v2.2 §3'ün dört yeni ölçüsünden biri (`docs/v2.2-python-metrikleri.md`):
"bir fonksiyonun parametreleri üzerinde eriştiği farklı attribute adı sayısı;
tip çözümü gerektirmeden bağımlılığın genişliğini ölçer". **Bu bölüm
ölçümden önce yazıldı** (2026-09-22) ve sonuçlar görüldükten sonra
değiştirilmez; sonuçlar "Ölçüm" bölümüne eklenir.

## Dokuz madde

1. **Neyi sayıyor.** Fonksiyonun kendi kapsamında (iç içe tanımlara girilmez)
   alıcısı bir **parametre adı** olan her `p.a` erişimi (okuma, yazma, `p.a()`
   çağrısı). Değer: farklı `(parametre, attribute)` çifti sayısı.
   - Parametre: `param_count`'un yuvaları (alıcı `self`/`cls` hariç;
     `*args`, `**kwargs` dahil).
   - Fonksiyon içinde **yeniden atanan** parametre (`p = ...`, `for p in`,
     `with ... as p`, `p += ...`) tümüyle dışarıda: erişimleri artık argümana
     ait değil.
   - **Plandan sapma:** plan "farklı attribute adı" diyor; burada çift
     sayılır, çünkü iki parametrenin `.name`'i iki ayrı işbirlikçiye iki ayrı
     bağımlılıktır. Tek parametreli fonksiyonda ikisi aynıdır.
2. **Birim.** Fonksiyon (`duck_coupling`). Sınıf değeri yok (metotların
   toplamı anlamsız: aynı işbirlikçi farklı metotlarda tekrar sayılır).
3. **Aralık, yön.** ≥ 0 tam sayı. Yüksek: fonksiyon argümanlarının geniş bir
   arayüzüne dayanıyor. Kalite yönü iddia edilmez.
4. **Hesaplanamaz.** Parametre yuvası yoksa `null`; parametre var ama erişim
   yoksa `0`.
5. **Altın değerler.** `tests/test_duck_coupling.py`, elle, koddan önce.
6. **Bilinen yanlış pozitif / negatifler.** Modül ya da sınıf nesnesi
   parametre olarak geçirilirse (`def f(np): np.array`) sayılır; sözlük ve
   liste protokolü (`d.get`, `items.append`) işbirlikçi bağımlılığı gibi
   sayılır; `**kwargs.get(...)` sayılır. Yanlış negatif: parametre yerel bir
   ada kopyalanıp o ad üzerinden kullanılırsa (`o = p; o.a`) görülmez.
7. **Kanıt alanları.** Koku yok. Kabul edilirse rapor alanı
   `functions[].duck_coupling` (alan ekleme, şema artışı yok); prompt'a girmez.
8. **Eşik.** Tanımlanmaz (K11, K13 gibi betimsel). Dağılım raporlanır.
9. **Geçerlilik iddiası ve çürütme — ölçümden önce.** İddia: değer, fonksiyonun
   argümanlarından beklediği arayüzün genişliğidir. Aday şu koşullardan
   **herhangi biri** gerçekleşirse reddedilir ve araca eklenmez:
   - (a) **Elle kesinlik:** sabit tohumla çekilen 30 sayılmış
     `(parametre, attribute)` çiftinin **24'ünden azında** erişim gerçekten
     çağıranın verdiği argüman nesnesi üzerindeyse (yeniden bağlama,
     gölgeleme ya da modül nesnesi değil). Kararlar `duck-verdicts.json`'a
     dosya:satır ve gerekçeyle.
   - (b) **Tip tutarlılığı:** parametresi tek bir **proje sınıfı** adıyla
     annotation'lı olan çiftlerde (annotation `ast.Name` ya da string, adı
     projede tek bir sınıfa ait), erişilen adın o sınıfın üyesi olma payı
     (attribute kümesi ∪ metot adları, **kalıtım hariç**) — en az 30 böyle
     çifti olan projelerin medyanında **%60'ın altındaysa** (ölçü
     işbirlikçinin arayüzü dışında bir şey sayıyordur). Kalıtım hariç
     tutulduğu için payın 1.0 olması beklenmez; %60 bu yüzden seçildi.
   - (c) **Ayrım:** parametreli fonksiyonları arasında en az 30'unda değer
     olan projelerin **yarısından azında** p10 < p90 ise.

   Ek (ret koşulu değil): DCC'nin görmediği birimlerdeki kapsam — modül düzeyi
   fonksiyonların kaçında değer > 0.

**Kabulün tavanı.** (a)-(c) geçerse alan betimsel olarak rapora eklenir.

---

## Ölçüm

*Bu bölüm ölçümden sonra eklendi; yukarısı değiştirilmedi.*

```bash
python experiments/hardening/duck_coupling.py measure   # ~2 dk
python experiments/hardening/duck_coupling.py summary   # (a)
```

Çıktılar `results/duck-coupling.json`, `results/duck-coupling-tables.md`
(proje başına tablo orada); elle kesinlik örneklemi `duck-sample.json`,
kararlar `duck-verdicts.json`. Birlikte yeniden koşulduğunda birebir aynı.
Ölçü araca taşındıktan sonra yeniden koşuldu; aynı hash.

### Karardan önce düzeltilen uygulama hatası

İlk koşudan sonra, örneklemi okurken yeniden bağlama kuralının bir kör noktası
fark edildi: `except E as p`, `import x as p` ve `match` yakalamaları adı
`ast.Name` olarak değil düz metin olarak saklar; ilk uygulama bunları
görmüyordu. Ön kaydın 1. maddesi "yeniden atanan parametre dışarıda" dediği
için bu, kuralın değil uygulamanın eksiğiydi ve karardan önce düzeltildi.
Etkisi: 24 406 çiftin 5'i (hepsi mealie'de `match` kalıpları); örneklemdeki
30 çiftin hiçbiri etkilenmedi.

### Ön kayıtlı koşullar

- (a) Elle kesinlik **30/30**: gerçekleşmedi. **Zayıf kanıt olarak
  okunmalı:** alıcının parametre olup olmadığı sözdiziminden belli ve yeniden
  bağlama dışarıda tutulduğu için bu koşul büyük ölçüde uygulamanın doğru
  yazılıp yazılmadığını sınıyor. Bir çift (`site`) parametreye dekoratör
  tarafından veriliyor; yine argüman.
- (b) Tipli çiftlerde erişilen adın annotation'daki sınıfın üyesi olma payı,
  en az 30 tipli çifti olan 16 projenin medyanında **%90.0** (≥ %60):
  gerçekleşmedi. Asıl bağımsız kanıt bu: değer, işbirlikçinin gerçek
  arayüzünü sayıyor. En düşükler flask %37.2, healthchecks %63.1, mealie
  %65.6; ön kayıt kalıtımı bilerek dışarıda bıraktı ve bu projelerde
  kalıtılan üyeler (Django `Model`, flask `Scaffold`) olası neden, ama
  **incelenmedi**.
- (c) En az 30 parametreli fonksiyonu olan **25/25** projede yayılım:
  gerçekleşmedi.

**Sonuç: çürütülmedi.** Alan araca eklendi (K14).

### Bulgular

1. **Tipik projede parametreli fonksiyonların %31'i argümanları üzerinden en
   az bir attribute'a erişiyor;** medyan 0-1, p90 tür bazında 2-2.5. En büyük
   değerler ölçülmedi.
2. **Modül düzeyi fonksiyonlarda da çalışıyor:** tipik projede modül
   fonksiyonlarının %40'ında değer > 0. DCC sınıf düzeyinde; bu fonksiyonlar
   için daha önce hiçbir kuplaj ölçüsü yoktu.
3. **Tip çözümü gerektirmiyor ve annotation'sız projelerde de çalışıyor**
   (yt-dlp, awscli, redash); (b) yalnızca annotation'lı projelerde sınanabildi.
