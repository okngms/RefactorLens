# Tanım kararları — scan şeması 3

> **Durum:** karara bağlandı (2026-09-16). Uygulama: aynı tarihli commit.
> Kaynak veri: `experiments/hardening/metric-accuracy.md` §2, §3, §4, §6 ve
> `experiments/hardening/corpus.md`.

Sertleştirme Blok 1 ölçümleri, uygulama hatası olmayan ama tanımın
cevaplamadığı beş soru bıraktı (K1-K5). K6, Blok 1b madde 4'ün koku kuralı
kararıdır; alan eklediği için şema sürümü değiştirmez (`04` §1). K7, madde 3'ün
(kapsama) kararıdır; hiçbir şey değiştirmez. K8 eşik kararıdır; eşik metrik
değildir, şema sürümü değişmez. K9 v2.2'nin ilk ölçümüdür; bir adayı
reddeder, hiçbir şey değiştirmez. K10 bir koku kuralıdır (K6 deseni); alan
ekler, şema sürümü değişmez. K11 v2.2'nin ilk yeni ölçüsüdür; alan ekler.
K12 bir adayı reddeder; hiçbir şey değiştirmez.
K13 v2.2'nin ikinci yeni ölçüsüdür; alan ekler.
K14 üçüncüsüdür; alan ekler. Blok 1b'nin dağılım tablosu metrik değerlerini
ölçeceği için bu sorular **tablodan önce** kapanmalıydı; yoksa tablo iki kez
üretilirdi. Beşi burada birlikte karara bağlandı ve metrik anlamını değiştiren
üçü tek bir `schema_version` artışıyla (2 → 3) uygulandı.

Değerlendirmede üç kural esas alındı:

1. **AGENTS.md invariant'ları tartışılmaz.** Bir karar invariant'ı ihlal eden
   davranışı sürdürüyorsa karar değil düzeltmedir.
2. **FINDINGS yeniden üretilebilir kalır.** Deney tamamlandı; sonuçlar o günkü
   kokuların kanıt alanlarıyla üretildi. `smells.py`'nin kanıt alanları bu
   yüzden değişmez.
3. **Yeni ölçü uydurulmaz.** Yeni bir ölçü `docs/v2.2-python-metrikleri.md`
   §3'ün dokuz maddesinden ve korpus kalibrasyonundan geçer. Bu belge mevcut
   ölçüleri netleştirir, yenisini eklemez.

---

## K1 — LOC: yorum, boş satır ve docstring sayılmaz

**Karar.** LOC, fonksiyonun `def` satırından son satırına kadar olan aralıkta
**en az bir kod token'ı içeren** satırların sayısıdır. Sayılmayanlar: boş
satırlar, yalnızca yorum içeren satırlar, fonksiyonun ve içindeki iç içe
fonksiyon/sınıfların docstring'leri (Goodhart gerekçesi onlar için de aynıdır).
Dekoratörler eskisi gibi hariç. İmza satırları (çok satırlı imza dahil) koddur
ve sayılır.

**Önceki durum.** `docs/04` "gövde satır sayısı (boş/yorum hariç)" diyordu;
uygulama fiziksel satır sayıyordu (boş ve yorum dahil) ve docstring'inde bunu
bilinçli tercih olarak gerekçelendiriyordu: "basit ve öngörülebilir". İki tarafın
da gerekçesi vardı.

**Gerekçe — Goodhart.** RefactorLens refactoring önerir ve `verify` metrik
iyileşmesini raporlar. Fiziksel satır sayımında bir fonksiyonun yorumlarını ve
docstring'ini silmek LOC'u "iyileştirir"; davranış testleri geçer, arayüz
değişmez, Goodhart kontrolü hiçbir şey görmez. Araç, belgelenmiş kodu
cezalandıran ve belgeyi silen öneriyi ödüllendiren bir sayı üretmemeli. Bu,
"basit" tanımın avantajından ağır basar.

Öngörülebilirlik korunur: kural token düzeyinde kesindir (bkz. uygulama) ve
AST tahmini değildir. Satır içi yorum taşıyan kod satırı (`x = 1  # not`)
koddur ve sayılır.

**Maliyet.**
- `long_method` eşiği (LOC ≥ 40) aynı fonksiyon için artık daha küçük bir
  sayıyla karşılaştırılır. Eşik Blok 1b'de korpustan yeniden kalibre
  edileceği için geçici bir durumdur.
- FINDINGS-1/2'nin LOC verileri şema 2'nin tanımıyla toplandı. Geçmişe dönük
  düzeltilmez; şema etiketi hangisi olduğunu söyler.

**Uygulama.** `func_metrics.code_lines(source)` modülü bir kez `tokenize`
ile tarar ve kod token'ı taşıyan satırların kümesini döndürür (çok satırlı
string'lerin tüm satırları dahil). `function_loc(node, code_lines)` bu kümeyi
fonksiyonun aralığıyla keser ve docstring satırlarını çıkarır. Kaynak metin
zorunlu parametredir: kaynaksız bir yedek tanım, iki farklı LOC'u sessizce aynı
alana yazardı.

## K2 — Metotsuz sınıfta LCOM4 `null`

**Karar.** Sınıfın metodu yoksa (dunder'lar hariç, `docs/04 §2.1`) LCOM4
`null`'dır.

**Gerekçe.** Bu bir karar değil düzeltmedir. AGENTS.md invariant'ı:
"hesaplanamayan metrik `null` döner, asla sıfır değil". `docs/04` de "metot
yoksa null" diyordu. Uygulama `0` döndürüyor ve bunu "veri sınıfları meşrudur,
eksiklik değil" diye gerekçelendiriyordu; bu `null`'ı "eksik" sanmaktır.
`null` "bu sınıf için kohezyon sorusu sorulamaz" demektir — tam olarak metotsuz
sınıfın durumu. `0` ise LCOM4'ün tanım aralığında (≥ 1) bile değildir.

**Etki.** Koku kuralları `None`'ı zaten "eşiği karşılamaz" sayar
(`smells._meets`). `data_class` kanıtındaki `lcom4` alanı adıyla kalır; metotsuz
sınıfta değeri `0` yerine `null` olur.

## K3 — DCC: sınıfın kendi iç içe sınıfları sayılmaz

**Karar.** Ölçülen sınıfın gövdesinde, herhangi bir derinlikte (metot içi dahil)
tanımlanan sınıfların adları DCC'den çıkarılır — sınıfın kendi adının çıkarıldığı
gibi.

**Gerekçe.** DCC başka birimlere bağımlılığı ölçer. İç içe sınıf aynı kaynak
biriminin parçasıdır; ondan bağımsız değiştirilemez ve taşınamaz. Elle sayımda
(metric-accuracy §4) 154 referansın 2'si bu yüzden yanlış pozitifti:
`SubqueryLoader._SubqCollections` ve `ValidatedFunction` metodu içinde tanımlı
`DecoratorBaseModel`.

**Sınır.** İç içe sınıf, projede başka bir yerde tanımlı bir sınıfla aynı adı
taşıyorsa o ad da çıkar. Sınıf içinde ad zaten iç içe olana çözülür; doğru olan
budur.

## K4 — `god_class` kapısı bu şemada değişmez

**Karar.** `god_class` = NOM ≥ 20 ∧ WMC ≥ 50 ∧ LCOM4 ≥ 3 aynen kalır. LCOM4'ün
çağrı kenarlarını bağ sayan tanımı (Hitz ve Montazeri) değişmez. Kapının yeniden
tasarımı `docs/v2.2-python-metrikleri.md`'ye taşınır.

**Sorun.** Ortak bir yardımcı metot sınıfı tek bileşene bağlar. Korpusta boyut
koşulunu geçen 107 sınıfın 34'ü yalnızca bu yüzden kokudan kaçıyor
(`mypy.TypeChecker`, NOM 217, LCOM4 1).

**Neden şimdi değiştirilmiyor.**
- **Kanıt alanları sabit.** Kapıyı başka bir ölçüye bağlamak `god_class`
  kanıtının alanlarını değiştirir; FINDINGS bu alanlarla üretildi.
- **Yerine konacak ölçü henüz yok.** Çağrısız bileşen sayısı ya da TCC gibi bir
  yoğunluk ölçüsü yeni bir metriktir. Dokuz maddesi (özellikle eşik ve çürütme
  koşulu) korpus olmadan yazılamaz. Bugün bir sayı seçmek, bu projenin Java
  eşiklerini kopyalayarak yaptığı hatayı tekrarlamak olur.
- **LCOM4'ü değiştirmek yanlış yer.** LCOM4 literatürdeki tanımıyla doğru
  ölçüyor; sorun ölçü değil, onun `god_class` için kapı olarak kullanılması.

**Bu arada.** Yanlış negatif README'de sınırlılık olarak yazılı. Blok 1b'nin
dağılım tablosu "boyut koşulunu geçen ama LCOM4'te elenen" sınıf sayısını ayrı
satır olarak raporlar. v2.2'deki "modül düzeyi kohezyon" çalışmasına sınıf içi
yoğunluk ölçüsü de aday olarak eklenir.

## K5 — `if`/`try` altındaki tanımlar bu şemada raporlanmaz

**Karar.** Modülün en üst düzeyinde değil de `if`/`try` bloğu altında
tanımlanan sınıf ve fonksiyonlar rapora girmez (mevcut davranış). Kapsama
genişletmesi v2.2'ye taşınır.

**Sorun.** Blok 1 referans setinde 135 fonksiyon; korpusta pydantic'in
ölçülmeyen kodunun %37'si (`if TYPE_CHECKING:` altındaki tanımlar).

**Neden şimdi değiştirilmiyor.** En yaygın deyim aynı adı iki kez üretir:
`if TYPE_CHECKING: class X: ...` / `else: X = ...`. `verify` sınıfları
`modül:ad` kimliğiyle eşleştirir (`ClassReport.qualified_name`); aynı modülde
iki `X` bu kimliği bozar ve deltaları sessizce yanlış eşleştirir. Önce kimlik
tasarımı gerekir (hangi dal raporlanır, kimlik neyi içerir). Bu, v2.2'nin
"modül düzeyi kod için birim" sorusuyla aynı sorudur ve orada birlikte
çözülmelidir.

---

## K6 — Framework giriş noktalarında `too_many_params` verilmez

> Karara bağlandı 2026-09-18. Şema 3 içinde: yalnızca alan ekler
> (`FunctionReport.entry_point`), alan anlamı değiştirmez.

**Karar.** Bir fonksiyon framework giriş noktasıysa (`cli`, `web_route`,
`signal_handler`, `fixture`) `too_many_params` kokusu verilmez ve `advise`
parametre eşiğini hedef gerekçesi saymaz. `param_count` ve terminaldeki eşik
rengi **değişmez**; terminal satıra türü yazar (`cli.scan [cli]`).

**Gerekçe.** Parametre listesi iki durumda yazarın tasarımı değildir: framework
imzayı dikte eder (Django sinyal alıcısı, pytest fixture'ı) ya da parametreler
framework'e bildirilen dış arayüzdür (CLI seçenekleri, HTTP parametreleri).
İkincisinde "parametre nesnesi çıkar" önerisi arayüzü değiştirmeyi önermektir.
İlke: **metrik gerçeği söyler, koku yorumlar.**

**Tanıma dar.** Yanlış pozitif gerçek bir kokuyu gizler. Planın "dekoratörle
tanımlanan fonksiyonlar ayrı ele alınır" ifadesi ölçümle daraltıldı: korpusta
5+ parametreli 2 238 fonksiyonun 542'si dekoratörlü ama yalnızca 17'si giriş
noktası; gerisi `@classmethod`, `@doc`, `@final` gibi. "Dekoratör varsa muaf"
kuralı pandas'ın API metotlarını gizlerdi. Celery görevi (`@app.task`) giriş
noktası sayılmaz: parametreleri yazarın seçtiği mesaj içeriğidir.

**Etki** (`experiments/hardening/entry-points.md`). Korpusta `too_many_params`
2 238 → 2 221 (%0.8). RefactorLens'in kendi kodunda 20 → 15: typer
komutlarının beşi. Dogfooding notu "vakaların büyük kısmı typer komutu"
diyordu; ölçüm çeyreği olduğunu gösterdi. Kural doğru ve yanlış tavsiyeyi
önlüyor, ama `too_many_params` gürültüsünün asıl kaynağı değil — o dekoratörsüz
API yüzeyinden geliyor ve eşik kararının konusu.

**Kanıt alanları** (`params`, `thresholds`) değişmez.

## K7 — CAM ve DAM tutulur; ayrım sorunu belgelenir

> Karara bağlandı 2026-09-21. Metrik, alan ve eşik değişmez; şema 3 aynen.
> Ölçüm: `experiments/hardening/coverage.md`.

**Soru.** Blok 1b planı: "ayrım yapmayan metrik düşürülür ya da gerekçesiyle
tutulur". Dağılım tablosu iki aday göstermişti: CAM (p75'ten itibaren 1.0) ve
DAM (p75 0).

**Ölçüm.** Kapsama tablosu birimleri `null` / tanım gereği belli / bilgi taşıyan
diye ayırdı (proje medyanları):

- **CAM** sınıfların %15.9'unda bilgi taşıyor; kapsam projenin annotation
  kültürüne bağlı (yt-dlp, awscli, netbox, redash < %0.5). Ama hesaplandığı her
  uygun projede (8/8) ayırıyor: p10 medyanı 0.14, p90 medyanı 0.84. Dağılım
  tablosundaki tavan, parametreli tek metodu olan sınıfların tanım gereği 1.0
  değerinden geliyordu. **Sorun ayrım değil kapsama.**
- **DAM** sınıfların %59.9'unda bilgi taşıyor ama tipik projede bu değerlerin
  %86.5'i tek değerde (19 projenin 17'sinde 0);
  19 uygun projenin 7'sinde (web_app'in 5'inden 4'ü) proje içinde hiç yayılım
  yok. Kütüphanelerde 7'nin 6'sında var. **Sorun ayrım ve türe bağlı.**

**Karar.** İkisi de tutulur. CAM için ek bir şey gerekmez: hesaplanamadığında
zaten `null` ve sebebi raporda. DAM'ın web uygulamalarında sınıfları
ayırmadığı README'ye sınırlılık olarak yazılır; yeniden tanımı v2.2'nin konusu.

**Gerekçe.**

1. **Düşürmenin bedeli ölçülen kazançtan büyük.** Alan kaldırmak alan anlamını
   değiştirir → şema artışı (`04` §1) ve `verify` eski raporları reddeder.
   DAM `data_class` kokusunun koşulu ve kanıt alanı; CAM ve DAM `advise`
   prompt'unun metrik listesinde. `smells.py` kanıt alanları ve `prompts.py`
   deney protokolü başladıktan sonra değişmez (CLAUDE.md; bu belgenin 2. kuralı).
   Düşürmek FINDINGS-1/2'nin girdisini yeniden üretilemez yapardı.
2. **CAM'i düşürmek yanlış metriği cezalandırırdı.** Ölçüm CAM'in hesaplandığı
   yerde ayırdığını gösterdi. Kapsamı artırmanın yolu annotation kapsamını ayrı
   bir ölçü yapmak; v2.2 §3 bunu zaten planlıyor.
3. **DAM'ın yerine konacak ölçü henüz yok.** Yeni ölçü uydurulmaz (bu belgenin
   3. kuralı); v2.2'nin dokuz maddesinden ve korpustan geçer. O zamana kadar
   DAM kütüphanelerde sınıfları ayıran bir sayı üretiyor; web
   uygulamalarında neredeyse her sınıfta 0 ve bu README'de yazılı.

**Maliyet.** Web uygulamalarında DAM prompt'a ve rapora bilgi taşımayan bir 0
olarak girmeye devam eder. `data_class`'ın web_app'te hiç ateşlememesinin
(koku oranı 0) DAM koşulundan mı geldiği sınıf sınıf incelenmedi.

**Çürütme koşulu.** v2.2 korpus koşusunda DAM, tanım gereği belli olmayan
sınıflarda da kütüphanelerin çoğunda yayılım göstermezse (bugün 7'de 6),
"kütüphanelerde anlamlı" iddiası düşer ve DAM v2.2'de kaldırılır ya da
yeniden tanımlanır.

## K8 — Varsayılan eşikler persentilden; LCOM4 5/10

> Karara bağlandı 2026-09-21. Şema 3 aynen. Ölçüm:
> `experiments/hardening/thresholds.md`; persentil kaynakları `docs/04` §3.

**Karar.** `thresholds.lcom4` `{warn: 2, critical: 4}` → `{warn: 5, critical: 10}`.
Diğer bütün eşikler aynı kalır; DCC için varsayılan `by_layer` eklenmez;
PARAMS tanımı (yalnızca-anahtar parametreler) değişmez. Deney fikstürleri
(`examples/messy_project`, `examples/layered_project`) `rlens.yaml`'larında
v2.0.0 LCOM4 eşiklerini sabitler.

**Kural.** Uyarı: proje medyanında birimlerin en fazla %6.9'unu işaretleyen en
küçük tamsayı. Kritik: en fazla %1.2. İki sayı da yeni seçilmedi; korunan
eşiklerden geliyor: %6.9 en gevşek korunan uyarının (CC ≥ 10), %1.2 tek
kritik referansın (CC ≥ 20) payı. Kural gürültüye üst sınır koyar: korunan
eşiklerden daha tutucu olanlar (NOM %1.3, NESTING %2.6, WMC %2.7) düşürülmez,
çünkü düşürmek yeni uyarı üretir ve işaretlenen birimlerin sorunlu olduğunu
gösteren doğruluk verisi yok.

**Ölçüm.** LCOM4 ≥ 4 %7.5 (üst sınırın üstünde), ≥ 5 %5.5; ≥ 9 %1.5, ≥ 10 %1.1.
Dağılım tablosunda p95 = 4.65, p99 = 9.35: yeni eşikler ≈ p95 ve ≈ p99. Tipik
projede en az bir eşiği aşan sınıf payı %21.7 → %11.0; yalnızca LCOM4 yüzünden
işaretlenen pay %11.0 → %1.1.

**Neden şema sürümü artmıyor.** v2 şema notu eşik değişimini sürüm gerekçesi
saymıştı, çünkü `verify`'ın koku deltası eşiğe bağlı kokulardan
(`too_many_params`, `long_method`, `layer_misfit`) oluşur. LCOM4 eşiği hiçbir
kokuya girmez: `god_class` kendi `smells.god_class.lcom4` kuralını (3) taşır,
K4 gereği değişmedi. LCOM4 eşiğini yalnızca `class_violations` okur (terminal
rengi, "over threshold" sayımı, `--fail-on-violation`, `advise` hedef seçimi ve
prompt'taki `[WARN]`/`[CRITICAL]`). Scan raporu eşik değişince birebir aynı
kalır; `tests/test_hardening_thresholds.py` bunu sınar.

**Deney fikstürleri neden sabitlendi.** `messy_project`'te `OrderManager`'ın
LCOM4'ü 4: yeni varsayılanla işaretlenmez ve hedefin önem derecesi
`critical`'dan `warn`'a iner (`test_selector.py::test_severity_property` bunu
yakaladı). Deney yeniden koşulduğunda model farklı bir prompt görürdü.
`prompts.py` donmuş olsa da girdisi değişirdi; FINDINGS-1/2'nin yeniden
üretilebilirliği bu yüzden fikstür config'inde korunur.

**Maliyet.**
- `god_class` LCOM4 ≥ 3 ile ateşleyebilirken aynı sınıfın LCOM4 hücresi
  renklenmeyebilir. Koku bir birleşimdir, tek koşulu uyarı eşiği değildir;
  ama okuyucuya tutarsız görünebilir.
- Kütüphanelerde pay hâlâ %10.9 (cli %2.9); tür farkı kapanmadı.
- Payda seçimi sonucu bir tamsayı oynatıyor: tek adlı metotlu sınıflar
  çıkarılsaydı kural 6'yı verirdi. Diğer metriklerle tutarlılık için
  hesaplanmış bütün değerler seçildi.
- `explain` talimatı ve terminal notu "eşikler başka bir dil için kalibre
  edildi" diyor; K8'den sonra bu cümle tam doğru değil. `explain`'in sıfat
  yasağını kaldırıp kaldırmamak explain Blok 2'nin kararı; metin değiştirilmedi.

**Değişmeyenler ve neden.**
- **DCC 7** proje medyanında %4.8 (≈ p95), kuralın içinde. Tür farkı gerçek
  (web_app p90 = 7, cli 3) ama araç projenin türünü bilmez; `by_layer` katmana
  göredir, türe göre değil. Varsayılan boş kalır.
- **PARAMS 5** %5.1. Yalnızca-anahtar parametreleri saymamak kokuların
  %24.9'unu kaldırırdı; bu tanım değişikliği (şema artışı) ve v2.2'nin girdisi.
- CC, NESTING, NOM, WMC, `long_method` LOC: kuralın içinde.

**Çürütme koşulu.** v2.2'nin genişleyen korpusunda LCOM4 ≥ 5 payı proje
medyanında %6.9'u aşarsa ya da K4'ün yeni yoğunluk ölçüsü LCOM4'ün yerini
alırsa eşik yeniden hesaplanır.

## K9 — `god_class` kapısının iki yoğunluk adayı reddedildi; kapı değişmez

> Karara bağlandı 2026-09-22. Kod, metrik, eşik ve şema değişmez. Ölçüm:
> `experiments/hardening/density-gate.md`. v2.2 §5b'nin ilk sorusu.

**Soru.** K4, LCOM4 kapısının çağrı kenarları yüzünden büyük sınıfların
üçte birini kaçırdığını kaydetmiş ve yerine konacak yoğunluk ölçüsünü v2.2'ye
bırakmıştı. İki literatür adayı dokuz maddeyle yazılıp korpusta ölçüldü:
LCOM3-HM (Hitz ve Montazeri: çağrı kenarsız bileşen sayısı) ve doğrudan TCC
(Lanza ve Marinescu'nun God Class stratejisindeki yoğunluk).

**Karar.** İkisi de kabul edilmedi; `god_class` = NOM ≥ 20 ∧ WMC ≥ 50 ∧
LCOM4 ≥ 3 aynen kalır.

**Gerekçe.**
- **LCOM3-HM kapıyı boyuta indiriyor:** `lcom3 >= 3` boyut koşulunu geçen 159
  sınıfın 157'sinde ateşliyor. `lcom3 >= 10` bile 115'inde ateşliyor ve bugünkü
  kapının 16 sınıfını kaybediyor.
- **TCC'nin persentil eşiği yok:** tipik projede sınıfların en az dörtte
  birinin TCC'si 0 (p25 = 0, medyan 0.059); 1/3 sınıfların %73.8'ini işaretliyor.
- **Sorun çağrı kenarı değil durumsuz metot.** Büyük sınıfların %41'inde
  metotların çoğu hiçbir `self.<attr>`'a dokunmuyor; en kalabalık tür kardeşine
  devreden metot (2 481). Durum paylaşımına bakan hiçbir ölçü "tek
  sorumluluğun uzun kataloğu" ile "ilgisiz sorumluluklar"ı ayıramaz; bu ayrım
  için etiketli veri gerekiyor.

**Kanıtın gücü.** Çürütme koşullarından biri (yeni ateşlenenlerin çoğunun
durumsuz olması) ölçümden önce yazılmıştı ve **karşılanmadı** (61'in 21'i).
Reddi taşıyan iki koşul (kapının ayırmaması, TCC'nin sabit bölgesi) sonuçlar
görüldükten sonra formüle edildi. Ret bu yüzden "kanıtlandı" değil "kabul için
yeterli gerekçe yok" diye okunmalı: kapı değiştirmek FINDINGS'in kanıt
alanlarına dokunan yeni bir koku sürümü demek ve bu gerekçe ona yetmiyor.

**Bulunan ek sorun.** Bugünkü kapı ateşlediği 96 sınıfın 44'ünde durumsuz sınıf
yakalıyor; sekizi açıkça şüpheli: metotlarının çoğu taslak olan soyut arayüzler
(`mypy.NodeVisitor`, 83 metodun 83'ü `pass`) ve metotlarının çoğu
`@staticmethod` olan graphene tipleri (saleor, beş sınıf). README'ye sınırlılık
olarak yazıldı.

**Maliyet.** K4'ün yanlış negatifi (61 sınıf) açık kalıyor; şimdi yanında
ölçülmüş bir yanlış pozitif ailesi de var.

**Sıradaki soru.** Durumsuz metotlar: taslakları düğüm kümesinden çıkarmak
(tanım değişikliği, şema artışı), kapıyı yalnızca durumlu metotlar üzerinde
kurmak ya da `god_class`'ı etiketli veriyle doğrulamak. PySmell'in etiketli
veri setinin Large Class için kullanılabilirliği incelenmedi; ilk bakılacak
kaynak o.

## K10 — Taslak arayüzlerde `god_class` verilmez

> Karara bağlandı 2026-09-22. Şema 3 içinde: `ClassReport.stub_methods` alanı
> eklendi (`04` §1: alan eklemek sürüm artırmaz). Ön kayıt ve ölçüm:
> `experiments/hardening/stateless-gate.md`.

**Karar.** Metot adlarının en az yarısının gövdesi taslaksa (`pass`, `...`,
`return` / `return None`, `raise NotImplementedError`; docstring hariç) sınıf
bir arayüzdür ve `god_class` verilmez. NOM, WMC, LCOM4 ve `god_class`'ın
kanıt alanları değişmez; eşik 0.5 config'te değil (K6 gibi tanım sınırı).

**Gerekçe.** Davranışı olmayan bir sınıf sorumluluk taşımaz; "bölünebilir
sınıf" iddiası ona uygulanamaz. LCOM4 her taslağı ayrı bileşen saydığı için
`mypy.NodeVisitor` (83 metodun 83'ü `pass`) LCOM4 = 83 ile god class
sayılıyordu. Bu bir etiket gerektirmeyen, tanım gereği yanlış pozitif.

**Ön kayıt.** Kural ve çürütme koşulları ölçümden önce yazıldı; R1 hiçbirini
tetiklemedi. K9'da reddi taşıyan koşullar sonradan formüle edilmişti; bu kez
değil.

**Etki.** Korpusta `god_class` 96 → 93 (`mypy.NodeVisitor`, `mypy._Hasher`,
`pandas.BaseStringArrayMethods`). Deney fikstürlerinde taslak metot yok;
`messy_project` ve `layered_project`'in kokuları aynı (ölçüldü). Kapının
metrik koşulunu sayan `god_class_gate` taslak arayüzleri ayrı sütunda sayar;
"ateşlendi − taslak arayüz = koku sayısı" dağılım tablosunda denetlenir.

**Maliyet.** Bir sınıf taslak payı sınırın hemen altındaysa koku alır, hemen
üstündeyse almaz; 0.5 bir tanım seçimi, kalibre edilmiş bir eşik değil.
Kısmen soyut bir sınıfın gerçek metotları bir god class oluşturuyorsa (taslak
payı ≥ 0.5 iken) kaçırılır; korpusta böyle bir durum incelenmedi.

**Aynı ölçümün diğer sonuçları.**
- **Etiketli veri:** PySmell'in elle incelenen 300 Large Class etiketi tek bir
  `CLOC >= 37` eşiğiyle 1 hatayla ayrılıyor; PeerJ 2023 veri seti aynı
  etiketleri kullanıyor; MLCQ Java. Kohezyon kapısını doğrulayacak Python
  etiketi yok.
- **R2** (alıcısız metotlu sınıflar) ön kayıtlı (b) ile reddedildi; **R3**
  (durumlu LCOM4) (c) ile. **R4** (durumlu LCOM3-HM) çürütmeleri geçti ama
  etiket olmadan kodlanmaz; kör etiketli örneklem hazırlandı
  (`god_class_sample.py`, 32 sınıf), etiketlenmedi.

## K11 — Anotasyon kapsamı rapora eklendi (betimsel, eşiksiz)

> Karara bağlandı 2026-09-22. Şema 3 içinde: üç alan eklendi (`04` §1). Ön
> kayıt ve ölçüm: `experiments/hardening/annotation-coverage.md`. v2.2 §3'ün
> ilk ölçüsü.

**Karar.** `functions[].annotation_coverage`, `functions[].returns_annotated`
ve `classes[].annotation_coverage` rapora girer. Yuvalar `param_count` ile
aynı (tek yardımcı: `func_metrics.parameter_slots`); sınıf değeri CAM'in iç
kapsamının aynısı ama yuva yoksa `null`. **Eşik yok, koku yok, yön yok.**
`advise` prompt'u donmuş olduğu için alanlar prompt'a girmez.

**Gerekçe.** K7, CAM'in sorununun kapsama olduğunu gösterdi; kapsamın kendisi
görünmüyordu. Ön kayıtlı bağımsız sınama geçti: `py.typed` taşıyan projelerin
medyanı %100, taşımayanların %59.6; py.typed projelerinin 9'unun 8'i genel
medyanın üstünde; sınıf değeri CAM ile her sınıfta aynı.

**Neden eşiksiz.** Ölçü "imzalarda ne kadar tip bilgisi yazılı" sorusuna
cevaptır; "düşük kapsam kötüdür" iddiası taşımıyor. Eşik bu iddiayı gizlice
sokardı. Dokuz maddenin 8'i bu yüzden "tanımlanmaz" diye doldu.

**Maliyet.** Ayrı `.pyi` dosyalarıyla tiplenen paketler annotation'sız görünür
(attrs %11.4); `Any` kapsamı artırır ama bilgi taşımaz; `# type:` yorumları
sayılmaz. Üçü ön kayıtta yazılıydı.

**Yan etki.** `param_count` artık `parameter_slots`'un uzunluğu; davranış
aynı (bütün testler, uç durum testleri dahil, değişmeden geçti).

## K12 — DAM kalır; fiili açıklık (EXP) adayı reddedildi

> Karara bağlandı 2026-09-22. Kod, metrik, alan ve şema değişmez. Ön kayıt ve
> ölçüm: `experiments/hardening/exposure.md`.

**Soru.** K7 DAM'ı tuttu ama iki şey bıraktı: bir çürütme koşulu ve yapılmamış
bir varyans ayrıştırması. v2.2 "DAM'ın yeniden tanımı"nı listeledi; DAM
donmuş iki dosyada (kanıt alanı, prompt) geçtiği için "yeniden tanım" DAM'ın
yanına yeni bir ölçü demekti.

**Karar.** DAM aynen kalır. Aday EXP (sınıfın attribute'larından kaçına
sınıf dışından `X.a` ile erişildiği; ad projede tek sınıfa aitse çözülür)
ön kayıtlı (a) koşuluyla reddedildi ve araca eklenmedi.

**Ölçüm.**
- K7'nin çürütme koşulu tetiklenmedi (kütüphanelerin 7'sinde 6 yayılım,
  `coverage.md`).
- DAM η²: 0.74 (sınıf ağırlıklı), 0.50 (proje başına en fazla 200 sınıf) —
  ön kayıtlı okumayla **kararsız**.
- EXP: çözülebilir pay medyanı %44.7 (< %50, ret); DAM'ın sessiz olduğu 7
  projenin 7'sinde yayılım, adlandırmayla tutarsız proje 2/15, elle kesinlik
  25/30 (%83) — diğer üç koşul geçti.

**Gerekçe.** Ön kayıt her koşulu eşit ağırlıkta yazdı ve biri tetiklendi.
Bir ölçünün attribute'ların yarısından fazlasında tanımsız olması, en çok
ihtiyaç duyulan projelerde (netbox %11.5, saleor %23.6) daha da kötü olması,
raporda bir alan olarak taşınmasını haklı çıkarmaz.

**Maliyet.** DAM'ın web uygulamalarında sınıfları ayırmaması (K7) açık
kalıyor. EXP'nin çözülebildiği yerde işe yaradığı görüldü; darboğaz isim
çözümü. Annotation'lı projelerde alıcının türünü imzadan okumak bu darboğazı
gevşetebilir (FUTURE.md); `ast`-yalnız kararını zorlamaz.

## K13 — Dinamik opaklık rapora eklendi (betimsel, eşiksiz)

> Karara bağlandı 2026-09-22. Şema 3 içinde: iki alan eklendi (`04` §1). Ön
> kayıt ve ölçüm: `experiments/hardening/dynamic-opacity.md`. v2.2 §3'ün
> ikinci ölçüsü.

**Karar.** `functions[].dynamic_sites` (statik analizin hedefini göremediği
nokta sayısı) ve `classes[].dynamic_attribute_hooks` (`__getattr__` /
`__getattribute__` / `__setattr__` tanımlı mı) rapora girer. Sayılanlar:
sabit olmayan adlı `getattr`/`setattr`/`delattr`/`hasattr`, `eval`/`exec`,
sabit olmayan dinamik import, fonksiyonun kendi `**kwargs`'ının aktarılması.
Eşik, koku, yön yok; prompt'a girmez.

**Gerekçe.** Ön kayıtlı üç koşul geçti: elle kesinlik 27/30 (%90), üç
metaprogramlama kütüphanesinin üçü korpus medyanının üstünde, uygulama
tutarlılığı tam. v2.2'nin kendi çürütme koşulunun ikinci yarısı (bakımlı ve
ihmal edilmiş projelerin ayrımı) bu korpusta ölçülemediği için yeniden yazıldı;
bu, ön kayıtta açıkça belirtildi.

**Neden eşiksiz.** İddia "burada statik analiz kör"; "burası kötü" değil.
`**kwargs` aktarımı çoğu yerde doğru tasarımdır (sarmalayıcı, `super()`
çağrısı). Eşik ikinci iddiayı gizlice sokardı.

**Maliyet.** Aynı fonksiyonda sabit bir liste üzerinde dönen ad opak sayılıyor
(örneklemde 3/30). `obj.__dict__[name]`, `vars()`, `attrgetter`, `type()` ile
üretim sayılmıyor. (b) koşulunun kütüphane listesi bir önsel yargıydı.

## K14 — Duck typing yapısal kuplajı rapora eklendi (betimsel, eşiksiz)

> Karara bağlandı 2026-09-23. Şema 3 içinde: bir alan eklendi (`04` §1). Ön
> kayıt ve ölçüm: `experiments/hardening/duck-coupling.md`. v2.2 §3'ün
> üçüncü ölçüsü.

**Karar.** `functions[].duck_coupling`: fonksiyonun parametreleri üzerinden
eriştiği farklı `(parametre, attribute)` çifti sayısı; parametre yoksa `null`.
Yeniden bağlanan parametre (atama, `for`/`with`, `except as`, `import as`,
`match` yakalaması) sayılmaz. Eşik, koku, yön yok; prompt'a girmez.

**Plandan sapma.** v2.2 "farklı attribute adı" diyordu; çift sayılıyor, çünkü
iki parametrenin `.name`'i iki ayrı işbirlikçiye iki bağımlılıktır. Ön kayıtta
yazılıydı.

**Gerekçe.** Ön kayıtlı üç koşul geçti. Asıl kanıt (b): annotation'lı
parametrelerde erişilen adların %90'ı (16 projenin medyanı) annotation'daki
sınıfın kalıtım hariç üyesi. (a) 30/30 zayıf bir kanıt, çünkü büyük ölçüde
uygulamayı sınıyor; öyle kaydedildi.

**Maliyet.** Modül ya da sınıf nesnesi parametre olarak geçirilirse sayılır;
`dict`/`list` protokolü (`d.get`, `xs.append`) işbirlikçi bağımlılığı gibi
sayılır; yerel bir ada kopyalanan parametre (`o = p; o.a`) görülmez; kavrama
içinde parametreyi gölgeleyen ad üzerinden erişim yanlışlıkla sayılır.

## Korpustaki etki

26 projelik kalibrasyon korpusunda (13 738 sınıf, 39 485 fonksiyon+metot) şema
2 ile şema 3 aynı kod üzerinde karşılaştırıldı:

| Karar | Etki |
|---|---|
| K1 LOC | Fiziksel uzunluğu ≥ 5 olan fonksiyonların medyanında yeni LOC eskisinin %84.6'sı; en alt %10'da %40 veya daha az. `long_method` 2 054 → 1 550 (−%24.5): kaybolan 504 uyarının 40 satırı docstring, yorum ve boş satırlarla aşılıyordu. Tür bazında kayıp: ml_research −%29.0 (93 → 66), library −%28.7 (609 → 434), web_app −%25.8, cli −%20.9 — belge yoğun kod en çok cezalandırılıyordu. |
| K2 LCOM4 | 6 294 sınıf (%46) `0` → `null`. Başka hiçbir LCOM4 değeri değişmedi. |
| K3 DCC | 318 sınıfta (%2.3) toplam 345 referans eksildi; 239'u netbox'ta Django'nun `class Meta(BaseForm.Meta)` deyimi. DCC elle sayımında kesinlik %96.1 → %97.4 (152 referans, 31/36 sınıf birebir). |

## Şema 2 → 3 özeti

| Alan | Şema 2 | Şema 3 |
|---|---|---|
| `functions[].loc`, `methods[].loc` | fiziksel satır, boş/yorum/docstring dahil | kod token'ı içeren satır; boş, yorum, docstring hariç |
| `classes[].lcom4` (metotsuz sınıf) | `0` | `null` |
| `classes[].dcc` | kendi iç içe sınıflarını sayar | saymaz |

`verify`, şema 2 ve 3 raporlarını karşılaştırmayı reddeder (invariant). Bir
projeyi yeni sürüme geçiren kullanıcı `before` raporunu yeni sürümle yeniden
üretmelidir.
