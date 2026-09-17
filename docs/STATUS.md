# STATUS — 2026-09-15

## Sürüm
**v2.0.0 PyPI'da.** `v2.0.0` tag'i ile GitHub Actions üzerinden, Trusted
Publishing (OIDC) ile yayınlandı; API token kullanılmadı. CI matrisi
(3.11/3.12/3.13) ilk kez bu sürümde koştu.

## Bitenler
- **Sertleştirme Blok 1b, 2. oturum — tanım kararları, scan şeması 3** (bu
  oturum). Kararlar ve gerekçeler: `docs/v2-tanim-kararlari.md`. Kararları
  kullanıcının yetkisiyle asistan verdi; her birinin gerekçesi, maliyeti ve
  korpustaki etkisi kayıtta.
  - **K1 LOC:** kod token'ı içeren satır; boş, yorum ve docstring (iç içe
    tanımlarınkiler dahil) hariç. Gerekçe Goodhart: fiziksel satırda belgeyi
    silmek LOC'u "iyileştirir" ve hiçbir kontrol görmez. `func_metrics.code_lines`
    `tokenize` ile kesin; kaynak metin zorunlu parametre. Korpusta medyan
    fonksiyon %15 kısaldı, `long_method` 2 054 → 1 550.
  - **K2 LCOM4:** metotsuz sınıfta `null` (invariant düzeltmesi). 6 294 sınıf
    (%46) `0` → `null`; başka hiçbir LCOM4 değişmedi.
  - **K3 DCC:** sınıfın kendi iç içe sınıfları sayılmaz. 318 sınıf, 345 referans;
    239'u netbox'ta Django `class Meta(Base.Meta)` sahte bağımlılığıydı. DCC
    elle sayımı kesinlik %96.1 → %97.4.
  - **K4 `god_class` kapısı** değişmez (kanıt alanları FINDINGS için sabit; yeni
    yoğunluk ölçüsü v2.2'de dokuz maddeyle). **K5 `if`/`try` tanımları**
    raporlanmaz (aynı ad iki kez → `verify` kimliği; v2.2). İkisi
    `docs/v2.2-python-metrikleri.md` §5b'ye ve AGENTS.md kilitli kararlarına
    işlendi.
  - `SCHEMA_VERSION` 2 → 3. `docs/04` §1: sayaç ürün sürümü değildir; v3/v4
    plan dokümanlarındaki "şema 3/4" ifadeleri düzeltildi. README'ye LOC tanımı,
    şema 3 DCC oranları ve `verify` şema uyarısı eklendi.
  - **Yakalanan tutarsızlık:** DCC elle sayım çalışma kâğıdı DCC'yi kendi başına
    hesaplıyordu; K3 ona girmediği için özet şema 3'te sessizce eski sonucu
    üretti. Artık çalışma kâğıdı sayısı `dcc()`'ye eşit olmak zorunda.
  - Diğer tüm sertleştirme sonuçları (CC, CAM, kohezyon) şema 3 ile yeniden
    üretildi, değişmedi. `corpus-inventory.json`'da yalnız koku sayıları değişti.
  - Durum: 1277 paket testi, 91 fikstür testi, ruff temiz.
- **Sertleştirme Blok 1b, 1. oturum — korpus.** Ayrıntı:
  `experiments/hardening/corpus.md`. Aracın koduna dokunulmadı.
  - **Korpus** (`corpus.txt`): 26 proje, dört tür — library 10, cli 6
    (black, mypy, httpie, yt-dlp, aws-cli, pipx), web_app 5 (healthchecks,
    netbox, saleor, redash, mealie), ml_research 5 (nanoGPT, yolov5,
    detectron2, whisper, segment-anything). Commit hash'iyle dondurulmuş.
    Blok 1'in `projects.txt`'i değişmedi ve korpusun birebir alt kümesi
    (testle). Stability-AI/stablediffusion erişilemez olduğu için
    segment-anything alındı.
  - **Kapsam = kullanıcının varsayılan taraması.** Varsayılan config zaten
    `migrations/` dışlıyor (saleor 1452, netbox 309 dosya); ek dışlama yalnızca
    mealie `alembic/`, pydantic `v1/`, mypy `test/ typeshed/`. "generated"
    başlıklı dosyalar okundu; çoğu elle yazılmış, dışlanmadı.
  - **Envanter** (`corpus.py inventory`): 5 237 modül, 13 738 sınıf, 39 485
    fonksiyon+metot, 1.12 milyon mantık satırı; ayrıştırılamayan dosya 0; tam
    tarama tek çekirdekte 60 s.
  - **Bulgu — ağırlıklandırma:** sınıfların %47'si iki projede (netbox 4 116,
    yt-dlp 2 323), ikisi de tek deyimin binlerce tekrarı. Havuzlanmış persentil
    eşiği bu deyime kalibre eder. Öneri: persentil proje başına, tür/genel
    değer projelerin medyanı.
  - **Bulgu — ölçülmeyen kod:** raporun birimleri mantık satırlarının genelde
    %87-99'unu kapsıyor; nanoGPT %44 (betik tarzı eğitim döngüsü), httpie %83
    (modül düzeyinde CLI tanımı). Tür öngörmüyor, deyim öngörüyor. README "What
    RefactorLens does not do"a yazıldı.
  - **Config tuzağı** yakalandı: `.cache/` depo içinde olduğu için config araması
    RefactorLens'in `rlens.yaml`'ını (`include: ["src/"]`) bulup taramayı
    boşaltırdı; betik config'i proje başına açıkça yazıyor, testli.
  - Ölçü tanımı iki kez düzeltildi (veri tabloları ve attribute docstring'leri
    mantık sayılıyordu; netbox yanlışlıkla %48 görünüyordu), testle sabit.
  - `tests/test_hardening_corpus.py`, 19 test. Durum (o oturum sonu): 1260
    paket testi, 91 fikstür testi, ruff temiz.
- **Sertleştirme Blok 1, 3. oturum — Blok 1 kapandı.** Ayrıntı:
  `experiments/hardening/metric-accuracy.md` §5-§6. Kod değişikliği yok;
  yalnızca ölçüm, doküman ve test.
  - **CAM kapsamı** (`cam_coverage.py`): 1 678 sınıfın %47'sinde hesaplanıyor
    ama yalnızca %27'sinde ayırt edici (parametreli ≥ 2 metot; tek metotta CAM
    tanım gereği 1.0). %43'ünde hiç parametre yok. Kapsam iki kutuplu
    (proje ya tam annotation'lı ya hiç), bu yüzden eşik etkisiz: 0.5/0.7/0.9 →
    837/786/761 sınıf. Kendi deposunda hesaplanamayan 53 sınıfın 53'ü
    parametresiz, annotation eksikliği 0 — dogfooding gözleminin sebebi bu.
  - **Kohezyon** (`compare_cohesion.py`): LCOM4 ile `cohesion` 1.2.0 arasında
    **Spearman ρ = −0.62** (675 sınıf, beklenen yön). En çok ayrışan 25 sınıfın
    25'i tanım farkıyla açıklandı: 20 çağrı kenarı, 5 attribute'suz izole metot.
  - **Önemli bulgu — `god_class` kapısı:** LCOM4 çağrıyı bağ saydığı için ortak
    yardımcı metodu olan büyük sınıflar LCOM4 = 1-2 alıyor. Boyut koşulunu geçen
    107 sınıfın 36'sı LCOM4 koşulunda eleniyor, **34'ü yalnızca çağrı
    kenarları yüzünden** (`mypy.TypeChecker`, NOM 217). Uygulama hatası değil,
    tanım sonucu; README'ye sınırlılık olarak yazıldı.
  - İki ölçüm hatası ölçülerek yakalandı ve belgelendi: sınıflandırıcının ilk
    sürümü 18 sınıfı ölçmeden "ortak attribute" diye etiketledi (hepsi çağrı
    kenarıydı); karşılaştırma filtresi property getter/setter'ı iki metot sayıp
    sahte sapma üretti.
  - CAM'de şüphelenilen "yanlış sebep etiketi" hata değil: `no_annotated_parameters`
    iki durum için de doğru ve fikstürde belgeli. Kod değişmedi.
  - `docs/v2-sertlestirme.md` sıra satırı `docs/v2.2-python-metrikleri.md` ile
    hizalandı: Blok 1 → 1b → v2.2 → explain Blok 2 → Blok 3/2/4/5.
  - `tests/test_hardening_cohesion_cam.py`, 22 test. Durum (o oturum sonu):
    1241 paket testi, 91 fikstür testi, ruff temiz.
- **Sertleştirme Blok 1, 2. oturum.** Ayrıntı:
  `experiments/hardening/metric-accuracy.md` §4.
  - **DCC elle sayım — kabul kriteri sağlandı.** 36 sınıf (12 proje × düşük/
    orta/yüksek DCC bandı, sabit tohum), 154 referans. **Kesinlik %96.1,
    duyarlılık %96.1**, 30/36 sınıf birebir doğru. Hatalar yüksek bantta
    (8/12 birebir) ama örneklemde hiçbir sınıf `dcc` eşiğini (7) geçmedi ya
    da altına inmedi. FP: kendi iç içe sınıfı 2, harici aynı ad 2, yerel ad
    1, modül aynı ad 1. FN: tip takma adı 5 (tek sınıf), aynı adlı iki sınıf
    1. README "DCC resolution" bölümü ölçülen oranlarla yeniden yazıldı —
    eski "third-party classes are not counted" iddiası ölçümle çelişiyordu.
  - Yöntem: `dcc_sample.py` ipucu üretir, karar vermez. Şüpheli her referans
    ve her FN adayı `dcc-verdicts.json`'a satır numarasıyla yazıldı;
    `summary` kararı eksik ya da bayat girdi görürse sonuç üretmez. Örneklem
    `--force` olmadan yeniden yazılamaz (bu oturumda yanlışlıkla yeniden
    üretildi; tohum sayesinde birebir aynı çıktığı doğrulandı, koruma sonra
    eklendi). `tests/test_hardening_dcc.py`, 26 test.
  - **Elle sayımın yakaladığı hata — ayrı commit:** tarama kökü alt paket
    olduğunda (`pandas/core`) import çözücüsü `pandas.core.` önekini
    kırpamıyordu; `pandas/core` import grafiği **0 kenar** veriyordu (1182
    mutlak importun 1179'u kayıp), Ca/Ce/instability/döngüler sessizce boştu.
    `root_package_name` artık `__init__.py` taşıyan dizin zincirini kullanıyor.
    pandas/core 0 → 1189 kenar; diğer 11 projede kenar sayısı aynı.
  - Durum (o oturum sonu): 1219 paket testi, 91 fikstür testi, ruff temiz.
- **Sertleştirme Blok 1, 1. oturum.** Ayrıntı ve tüm sayılar:
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
  - Durum (o oturum sonu): 1187 paket testi, 91 fikstür testi, ruff temiz.
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
**Blok 1b, madde 2: dağılım tablosu** (`experiments/hardening/metric-distribution.md`).
Tanım kararları verildi ve şema 3 uygulandı; tablonun önünde engel yok.

- **Kapsam:** korpusun 26 projesi, şema 3 metrikleri, kullanıcının varsayılan
  taraması (`corpus.py`'nin config'i).
- **Metrikler:** fonksiyon (CC, LOC, PARAMS, NESTING), sınıf (NOM, WMC, LCOM4,
  DCC, DAM, CAM), modül (Ca, Ce, instability).
- **Ağırlıklandırma (corpus.md Bulgu 1):** persentil (medyan, 75/90/95/99)
  proje başına; tür ve genel değer projelerin medyanı; havuzlanmış persentil
  yalnızca karşılaştırma için yanında. `null` değerler dağılıma girmez, oranı
  ayrı sütunda (LCOM4 %46, CAM).
- **Mevcut eşiklerle karşılaştırma:** her varsayılan eşiğin korpusun hangi
  persentiline düştüğü (ör. `cyclomatic_complexity.warn = 10` → proje medyanı
  kaçıncı persentil). Eşiği **değiştirmek** tablodan sonraki ayrı karardır;
  tablo önce ne olduğunu gösterir.
- **K4 satırı:** boyut koşulunu geçip LCOM4'te elenen sınıflar ayrı raporlanır.

Sonra madde 3 (kapsama tablosu; CAM ve ölçülen mantık payı hazır) ve madde 4
(framework giriş noktaları, `too_many_params`).

Projeler yerelde yoksa: `python experiments/hardening/corpus.py fetch`
(~850 MB). Kohezyon betiği ayrıca `pip install cohesion==1.2.0` ister.

## Okunacak dokümanlar (sırayla)
AGENTS.md → bu dosya → docs/v2-sertlestirme.md (Blok 1, 1b) →
docs/v2-tanim-kararlari.md → experiments/hardening/corpus.md
Sonraki fazlar: docs/v2.2-python-metrikleri.md → docs/v2.1-explain.md
Deney protokolü: docs/v2-duzeltme-asama5.md. Metrik sınıfları:
docs/SPEC-duzeltme-2.5.md ve SPEC-duzeltme-2.5-v2.md.

## Açık kararlar / bilinen sorunlar
- **`examples/sample_reports/` şema 1'de ve v0.2.0'dan kalma.** v2.0.0'dan beri
  bayat, hiçbir test onlara bağlı değil; şema 3'le yeniden üretilmeli. Blok 5
  (dokümantasyon) işi.
- ~~**LOC tanımı uygulamayla çelişiyor.**~~ Şema 3 K1 ile karara bağlandı. `docs/04 §2.3` "gövde satır sayısı
  (boş/yorum hariç)" diyor; uygulama `def` satırından son satıra boş ve yorum
  dahil sayar. FINDINGS-1/2'nin LOC verisi uygulamanın tanımıyla toplandı.
  Hangi tarafın düzeltileceği tanım kararıdır (`schema_version`). Mevcut
  davranış `test_metric_edges.py`'de sabit.
- ~~**Metotsuz sınıfta LCOM4: doküman `null`, uygulama `0`.**~~ Şema 3 K2 ile düzeltildi. "Hesaplanamayan
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
- **Betik tarzı ve modül düzeyi kod ölçülmüyor.** nanoGPT'nin mantığının %56'sı,
  httpie'nin %18'i hiçbir metriğe görünmüyor (corpus.md Bulgu 2). README'de
  yazılı. Kapsam genişletmesi (modül düzeyi kod için bir birim) v2.2'nin
  "modül düzeyi kohezyon" ölçüsüyle birlikte düşünülmeli.
- **`god_class` LCOM4 kapısı büyük sınıfların üçte birini kaçırıyor** (K4:
  v2.2'ye kadar bilinçli olarak açık). Ortak
  yardımcı metodu olan sınıflarda çağrı kenarları LCOM4'ü 1-2'ye indiriyor;
  boyut koşulunu geçen 107 sınıfın 34'ü yalnızca bu yüzden elenir. Tanım
  kararı; sıradaki işte 2. madde. README'de sınırlılık olarak yazılı.
- ~~**DCC: sınıfın kendi iç içe sınıfı referans sayılıyor**~~ Şema 3 K3 ile düzeltildi. (elle sayımda 2/154
  yanlış pozitif). `docs/04 §2.2` "farklı proje-içi sınıf" diyor; kendi iç
  içe sınıfının "farklı" olup olmadığı tanımda belirsiz. `node.name` gibi
  dışlamak doğal görünüyor ama tanım kararıdır (`schema_version`).
- **DCC: harici aynı ad yanlış pozitifi bilinçli olarak kalıyor** (2/154).
  Adın modülde yalnızca harici importa bağlandığı durumda saymamak bunu
  kapatır ama DCC'yi import çözücüsünün doğruluğuna bağlar; çözücü
  düzeltmesinden önce aynı kural örneklemde 11 doğru pozitifi düşürürdü.
  Blok 1b korpusu genişleyince yeniden tartılacak. Gerekçe: metric-accuracy §4.
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
