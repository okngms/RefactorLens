# STATUS — 2026-09-15

## Sürüm
**v2.0.0 PyPI'da.** `v2.0.0` tag'i ile GitHub Actions üzerinden, Trusted
Publishing (OIDC) ile yayınlandı; API token kullanılmadı. CI matrisi
(3.11/3.12/3.13) ilk kez bu sürümde koştu.

## Bitenler
- **Sertleştirme Blok 1, 1. oturum** (bu oturum). Ayrıntı ve tüm sayılar:
  `experiments/hardening/metric-accuracy.md`.
  - **Madde 1 — referans seti:** `experiments/hardening/projects.txt`, 12
    proje, commit hash'iyle dondurulmuş, seçim gerekçesiyle. Kapsam: 673
    dosya, 16 128 fonksiyon, 1 678 sınıf; ayrıştırılamayan dosya 0.
  - **Madde 2, CC kısmı — radon çapraz doğrulaması:** `compare_radon.py`.
    14 935 fonksiyonda (%92.6) değer birebir aynı; 1 193 farkın tamamı
    belgelenmiş tanım farkı, **sınıflandırılmamış fark 0 — CC kabul kriteri
    sağlandı.** Farkların %90'ı radon'un `assert`'e +1 vermesi. Yöntemin
    tespit gücü sınandı: düzeltilen dekoratör hatası geri konunca 2
    sınıflandırılmamış fark çıkıyor. Sınıflandırıcı
    `tests/test_hardening_compare.py` ile sınanıyor (radon kurulu değilse
    mutabakat testleri atlanır; CI radon kurmaz).
  - **Madde 3 — uç nokta testleri:** `tests/test_metric_edges.py`, 51 test.
    Dokuz uygulama hatası önce kırmızı testle yakalanıp düzeltildi: CC
    dekoratör/varsayılan/annotation ifadelerini sayıyordu; `except*`
    iç içelik düğümü değildi; `@overload` taslakları NOM'a giriyordu
    (`pandas.DataFrame` NOM −43); `@staticmethod`'un ilk parametresi `self`
    sanılıyordu; iç içe sınıfın `self`'i dıştakine yazılıyordu; DCC string
    annotation ve `import as` takma adlarını görmüyordu; arayüz
    getter/setter ve taslakları tekrar listeliyordu. Hiçbiri `docs/04`
    tanımını değiştirmez; fikstürler bu deyimleri içermediği için altın
    değerler ve FINDINGS verisi değişmedi.
  - **Düzeltmenin ürettiği yanlış pozitif referans setinde yakalandı:** ilk
    takma ad kuralı `from urllib3.exceptions import HTTPError as
    BaseHTTPError`'ı projedeki `HTTPError` saydı. Takma adlar artık import
    grafiğinin proje-içi modül çözücüsüne bağlı
    (`imports.project_module_predicate`). DCC'si değişen sınıflardan
    örneklem elle doğrulandı; `Literal[...]` ve `Annotated` meta verisi de
    ayrıca dışlandı.
  - Hijyen: `tests/test_cli.py` format hatası (başlangıçta
    `ruff format --check` kırmızıydı); `.cache/` git, ruff ve sdist dışında
    (sdist 337 KB doğrulandı); STRUCTURE.md yeni dosyalarla güncellendi.
  - Durum: 1187 paket testi, 91 fikstür testi, ruff temiz.
- v2 Aşama 0, 1, 1b, 3, 4; 5a toplama, 5b (12 vaka), FINDINGS-2.
- v2 düzeltme listesi ve `docs/SPEC-duzeltme-2.5*`; metrik sınıflandırması
  kendi koşuluyla çürütüldü, gruplama "kalıntı bırakıyor mu"ya çevrildi.
- **v2.0.0 yayın hazırlığı** (bu oturum, `docs/v2-kalan-kapsam.md §5`):
  - `__version__` 2.0.0; classifier Beta; proje URL'leri kanonik yazıma çekildi.
  - `ADVICE_SCHEMA_VERSION` 1 → 2. Gerekçe `04 §1`'de: alan eklemek sürüm
    artırmaz, ama kalibrasyon `confidence`'a dayanıyor ve v1 raporlarında bu
    alan yok — sürüm etiketi olmadan "güven verilmemiş" ile "eski format"
    ayırt edilemiyor. `experiments/v2/` ham verisi 1 taşımaya devam eder.
  - README: `<user>` → `okngms`, sekiz göreli link mutlak URL'ye (PyPI'da
    depo ağacı yok), durum satırı ve Roadmap v2, "future versions will
    suggest" bayat cümlesi düzeltildi.
  - AGENTS.md: üç kilitli karar (çıkarım beyanı ezmez; `confidence`
    opsiyoneldir ve yokluğu öneriyi düşürmez; `suspicious` davranış kapısını
    ikame etmez). STRUCTURE.md v2 dosyalarıyla, FUTURE.md K6 maddesiyle
    güncellendi.
  - `.github/workflows/publish.yml`: 3.11/3.12/3.13 matrisi, ruff + iki test
    suite'i; tag'de OIDC ile yayın, `needs: test`.
  - `tests/test_packaging.py` (7 test): placeholder yok, her link mutlak,
    sürüm tek kaynaktan, entry point ve `readme` alanı yerinde.
  - Hijyen: `ruff format` iki dosyada; ham deney verisi ruff dışına ve
    sdist dışına (387 → 143 girdi). Açılmış sdist'te iki suite de yeşil.
- Durum (v2.0.0 yayını): 1059 paket testi, 91 fikstür testi, ruff temiz.

## İlk dogfooding verisi (kendi deposu, 66 sınıf, 361 fonksiyon)

`docs/v2-sertlestirme.md` Blok 1'in sorusu — metrikler gerçek Python kodunda
nerede sapıyor — kısmen cevaplandı. Sonuç tek cümleyle: **sınıf metrikleri bu
kod tabanında sessiz, fonksiyon metrikleri gürültülü, gürültünün çoğu bir
framework deyiminden geliyor.**

- **Sınıf düzeyi hiçbir şey bulmadı.** `god_class` yok, `data_class` yok, LCOM4
  tamamı 1-3. Eşiği aşan 60 öğenin 51'i fonksiyon düzeyi (32 `long_method`,
  19 `too_many_params`).
- **DAM ölü.** 66 sınıfın neredeyse hepsinde 0.00 — dataclass'lar public
  attribute kullanır. Metrik Java'nın `private` alan geleneğini varsayıyor;
  Python'da ölçtüğü şey yok.
- **CAM 53 sınıfta (%80) hesaplanamadı.** Bilinen sınırlılık ama oran, metriğin
  pratikte kullanılamaz olduğunu gösteriyor.
- **`too_many_params` sistematik yanlış pozitif üretiyor.** 19 vakanın büyük
  kısmı typer komutları: `cli.advise` 11, `cli.explain` 10, `cli.verify` 8
  parametre. Bunlar CLI seçenekleri, kötü tasarım değil. `GroqProvider.generate`
  ve `OllamaProvider.generate` de 5 ile tam sınırda etiketleniyor.
  Blok 1'de eşik kalibre edilirken **dekoratörle tanımlanan giriş noktaları**
  ayrı ele alınmalı, yoksa metrik her CLI projesinde aynı gürültüyü üretir.
- **Araç kendi hakkında haklı olduğu yer:** `report.verify.verify_markdown`
  CC=30 / LOC=124, `cli.advise` CC=23 / LOC=195, `analysis.interface.public_interface`
  CC=27 / NESTING=5. Bunlar gerçekten büyük ve bilerek ertelenmiş değil.
- `rlens.cli` I=1.00 (Ce=25, Ca=0) — beklenen, giriş noktası.
  `analysis.scanner` I=0.86 ve `explain.explainer` I=0.80 de ağırlıklı olarak
  orkestrasyon modülleri.

## Sıradaki iş
**`docs/v2-sertlestirme.md` Blok 1'in kalanı** (metrik doğruluğu). CC ve uç
nokta testleri bitti; kabul kriterinin kalan üç parçası:

1. **DCC elle sayım** — her projeden 3-4 sınıf, toplam 30-50; yanlış
   pozitif/negatif kategorileri ve oranı. Kabul kriteri bunun **README
   "Limitations"a işlenmesini** de istiyor. Önce bu: DCC bu oturumda en çok
   değişen metrik oldu (91 sınıf) ve düz ad eşleşmesinin üçüncü parti
   sınıflarla çakışma oranı henüz bilinmiyor.
2. **Kohezyon** — `cohesion` aracı ile sınıf bazında Spearman; büyük sapmalar
   elle. `cohesion` farklı bir LCOM tanımı kullanır; mutlak değer değil sıra
   karşılaştırılır.
3. **CAM annotation kapsamı** — projelerin yüzde kaçında hesaplanabiliyor.
   Ölçüm altyapısı hazır: `compare_radon.py`'nin proje yükleyicisi ve
   önbelleği yeniden kullanılabilir.

Referans projeleri yerelde yoksa: `python experiments/hardening/compare_radon.py
fetch` (~250 MB, `.cache/`).

Kararlaştırılan sıra:

```
sertleştirme Blok 1  → metrik gerçekten doğru mu (radon/cohesion çapraz doğrulama)
sertleştirme Blok 1b → eşikler ne olmalı (persentil), hangi metrik ölü
v2.2 python metrikleri → PySmell'in altısı + tasarlanacak dördü
v2.1-explain Blok 2   → şablon katmanı, yeni girdi şekli üzerine
```

`explain` Blok 2 bilerek en sona alındı. İki koşuda başarısız olma sebebi
söyleyecek bir şeyinin olmamasıydı: girdi "NOM=26, WMC=56" idi ve bundan
çıkarılabilecek tek cümle tablonun kendisiydi. Python'a özgü kokular yapısal
olgu verir ve kalibrasyon gerektirmeyen cümleler kurulabilir hale gelir.
Önce yazılırsa cümle kalıpları ve testleri iki kez yazılır.

Sertleştirme (`docs/v2-sertlestirme.md`) bunun arkasına alındı — sıra bilerek
değiştirildi, riski aşağıda ve o dokümanın §6'sında yazılı.

## Okunacak dokümanlar (sırayla)
AGENTS.md → bu dosya → docs/v2-sertlestirme.md (Blok 1, 1b) →
experiments/hardening/metric-accuracy.md (§3 kalanlar)
Sonraki fazlar: docs/v2.2-python-metrikleri.md → docs/v2.1-explain.md
Deney protokolü: docs/v2-duzeltme-asama5.md. Metrik sınıfları:
docs/SPEC-duzeltme-2.5.md ve SPEC-duzeltme-2.5-v2.md.

## Açık kararlar / bilinen sorunlar
- **LOC tanımı uygulamayla çelişiyor.** `docs/04 §2.3` "gövde satır sayısı
  (boş/yorum hariç)" diyor; uygulama `def` satırından son satıra boş ve yorum
  dahil sayar. FINDINGS-1/2'nin LOC verisi uygulamanın tanımıyla toplandı.
  Hangi tarafın düzeltileceği tanım kararıdır (`schema_version`). Mevcut
  davranış `test_metric_edges.py`'de sabit.
- **Metotsuz sınıfta LCOM4: doküman `null`, uygulama `0`.** "Hesaplanamayan
  metrik `null`" invariant'ı dokümanın tarafında; ama `null`'a geçmek koku
  eşiklerinin ve delta mantığının `None` karşılaştırmasını gerektirir.
  Deney protokolü açısından `smells.py` kanıt alanlarına dokunmadan
  yapılabilir mi, önce o incelenmeli. Mevcut davranış testte sabit.
- **Bazı sınıflar hiç ölçülmüyor.** Modül düzeyinde `if TYPE_CHECKING:` /
  `try: ... except ImportError:` altında tanımlı sınıflar ve iç içe sınıflar
  rapora girmez. Referans setinde 135 fonksiyon — küçük ama sessiz. Tanımda
  yazılı değil; ya tanıma yazılmalı ya kapsama alınmalı.
- **Metrik değerleri `schema_version` artmadan değişti.** Bu oturumun
  düzeltmeleri tanımı değil uygulamayı düzeltir, bu yüzden sürüm artmadı.
  Sonucu: v2.0.0 ile üretilmiş bir raporla bu kodla üretilen rapor arasında
  `verify`, kod değişmemiş olsa da `@overload`, string annotation veya
  `@staticmethod` içeren sınıflarda fark gösterebilir. Raporlar
  `rlens_version` taşıdığı için ayırt edilebilir; bir sonraki yayında
  CHANGELOG/README'de yazılmalı, `verify`'ın farklı `rlens_version`'da uyarı
  vermesi FUTURE.md'ye yazıldı (uygulanmadı).
- **`match` ve `except*` CC farkları yalnızca sentetik testle doğrulandı.**
  Referans setinin tag'leri 3.8/3.9 destekliyor, iki deyim de sette yok.
  Blok 1b korpusu en az bir 3.10+ proje içermeli.
- **Düz ad eşleşmesinde üçüncü parti çakışması kalıyor.** Takma adda
  kapatıldı; `from urllib3.exceptions import HTTPError` sonrası düz
  `HTTPError` kullanımı hâlâ proje sınıfı sayılır. Oranı DCC elle sayımında
  ölçülecek.
- STRUCTURE.md'deki test sayıları (488, 1052) bayat; AGENTS.md "Before every
  commit" bloğundaki `# 488` de öyle. Blok 5'e bırakıldı.
- **`explain`, sertleştirmenin önüne alındı.** Bilinen bedeli: metriklerin
  gerçek Python kodunda nerede saptığı henüz ölçülmedi, sapan bir ölçümün
  üstüne yorum katmanı koymak hatayı görünmez yapar. Azaltma olarak şablon
  katmanı yalnızca raporda yazan sayıyı aktarır; "iyi/kötü/yüksek" gibi
  kalibrasyona dayalı sıfatlar sertleştirme Blok 1 bitmeden kullanılmaz
  (sertleştirme Blok 1, explain Blok 1 değil).
  Ayrıntı: `docs/v2.1-explain.md` §6.
- **Sertleştirme yayından sonraya kaldı.** `docs/v2-sertlestirme.md` v2.0.0'ı
  beş bloğun sonrasına koyuyordu; sıra bilerek değiştirildi. Sonucu: Blok 1'in
  "metrikler gerçek projelerde nerede sapıyor" tablosu olmadan çıkıyoruz,
  README'nin Limitations bölümü hâlâ yalnızca fikstüre dayanıyor. Bloklar
  v2.1'e taşındı; kabul kriterleri değişmedi.
- Katman çıkarımı v2.1'de (beyan + import-linter ile çıkıyoruz).
- ~~Terminal genişliğine bağımlı testler.~~ Çözüldü: çıktı `flat()` ile
  düzleniyor (`tests/test_cli.py` ve `tests/test_explain_cli.py`), proje yolunu
  basan bölüm karşılaştırmaya girmiyor. 60-200 sütun arasında doğrulandı.
  `tmp_path` dizin adına testin kendi adını koyduğu için `..._thresholds_...`
  adlı bir testin kendi adı yüzünden düştüğünü unutma.
- **`explain` iki koşu sonucu: LLM katmanı sentez üretmedi.**

  1\. koşu (7 tespit): hepsi tabloyu cümleye çevirdi, dördü talimatta birebir
  yasak sıfat kullandı, `DAM=0.0` "all attributes are private" diye **ters
  okundu** (0.0 hiçbiri private değil demek).

  Şema `findings` şekline geçirildi, talimata karşı örnek eklendi,
  derecelendirme `graded_terms` ile etiketlenir oldu, kesme kokulu sınıfları
  öncelemeye başladı, DAM sözlüğüne yön eklendi.

  2\. koşu (4 tespit): **4/4 yine derecelendirdi** ("high", "low", "moderate").
  `single_metric_count` 7→0 düştü ama bu bir kazanım değil, **oyunlandı**:
  model "iki özne" şartını, aynı sınıfın on kopyasını listeleyerek karşıladı.
  Cümleler hâlâ tablo + sıfat.

  İki sonuç ayrılmalı:
  - **Derecelendirme talimatı tutmuyor.** 11 tespitin 11'i sıfat kullandı.
    Girdi kalitesinden bağımsız, sağlam bir bulgu.
  - **Sentez ölçülemiyor.** Özne/metrik saymak sentezi ölçmez; şeklin kendisi
    oyunlanabilir. Mekanik bir sentez ölçüsü tasarlanamadı, bu da bir bulgu.

  Karar: Blok 2 (deterministik şablon). LLM katmanı, şablona üstünlüğünü
  gösteremedi.
- **Depoya `rlens.yaml` eklendi (dogfooding).** Araç kendi deposunda
  koşturulduğunda fikstürleri ve `experiments/*/cases/*/project/` altındaki
  deney kopyalarını ölçüyordu. O kopyalar git'e girmez ama diskte durur; 2.
  koşudaki sahte gruplamanın sebebi buydu. `include: ["src/"]` ile temiz tarama
  66 sınıf veriyor, üçünde koku var: `ImportGraph`, `GroqProvider`,
  `OllamaProvider`. Bunlar Blok 3'ün ilk gerçek dogfooding verisi.
- CI matrisi hiç koşmadı; ilk push'ta 3.11 ve 3.13'te sürpriz çıkabilir.
  Yerelde yalnızca 3.12 denendi.
- `pyproject.toml` 3.14 classifier'ı taşıyor ama matriste 3.14 yok — ya matrise
  eklenmeli ya classifier düşmeli (Blok 4).
