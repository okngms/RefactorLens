# Tanım kararları — scan şeması 3

> **Durum:** karara bağlandı (2026-09-16). Uygulama: aynı tarihli commit.
> Kaynak veri: `experiments/hardening/metric-accuracy.md` §2, §3, §4, §6 ve
> `experiments/hardening/corpus.md`.

Sertleştirme Blok 1 ölçümleri, uygulama hatası olmayan ama tanımın
cevaplamadığı beş soru bıraktı (K1-K5). K6, Blok 1b madde 4'ün koku kuralı
kararıdır; alan eklediği için şema sürümü değiştirmez (`04` §1). Blok 1b'nin dağılım tablosu metrik değerlerini
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
