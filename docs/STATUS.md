# STATUS — 2026-09-09

## Sürüm
**v2.0.0 PyPI'da.** `v2.0.0` tag'i ile GitHub Actions üzerinden, Trusted
Publishing (OIDC) ile yayınlandı; API token kullanılmadı. CI matrisi
(3.11/3.12/3.13) ilk kez bu sürümde koştu.

## Bitenler
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
- Durum: 1059 paket testi, 91 fikstür testi, ruff temiz.

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
**`docs/v2.1-explain.md` Blok 2** (şablon katmanı). Blok 1 bitti ve
sonucu olumsuz: yukarıdaki iki koşuya bak.

Sertleştirme (`docs/v2-sertlestirme.md`) bunun arkasına alındı — sıra bilerek
değiştirildi, riski aşağıda ve o dokümanın §6'sında yazılı.

## Okunacak dokümanlar (sırayla)
AGENTS.md → bu dosya → docs/v2.1-explain.md → docs/v2-sertlestirme.md
Deney protokolü: docs/v2-duzeltme-asama5.md. Metrik sınıfları:
docs/SPEC-duzeltme-2.5.md ve SPEC-duzeltme-2.5-v2.md.

## Açık kararlar / bilinen sorunlar
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
