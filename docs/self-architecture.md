# RefactorLens kendi üzerinde (sertleştirme Blok 3)

`docs/v2-sertlestirme.md` Blok 3. Araç kendi deposunda, kökten
`rlens scan .` ile koşturuldu. Ham çıktılar `experiments/hardening/self/`
altında: `scan-20260924-172837.json` (önce), `arch-20260924-172641.json`,
`advice-20260924-172854.{json,md}`, `verify-20260924-173102.{json,md}`.
Kullanımda çıkan pürüzler: `experiments/hardening/friction.md`.

## 1. Katman beyanı

Kök `rlens.yaml`:

| Katman | Yollar |
|---|---|
| presentation | `cli.py`, `report/` |
| application | `advise/`, `verify/`, `explain/` |
| domain | `analysis/` |
| infrastructure | `llm/`, `integrations/`, `providers/` |

Şema varsayılan (`presentation → application, domain`; `application →
domain`; `infrastructure → domain`; atlama yok). `config.py` ve paket kökü
`rlens/__init__.py` beyan dışı: her katman config okur, onu bir katmana koymak
her içe aktarmayı ihlal ya da istisna yapardı. İkisi `unknown` kalır ve
ihlal raporuna girmez (arch notu bunu söylüyor).

**Tartışma: `report/` nerede?** Sertleştirme planı `report/`'u altyapıya
koyuyordu (A). İkisi ölçüldü, aynı kod ve aynı şemayla:

| Beyan | İhlal |
|---|---:|
| A: `report/` infrastructure | 25 |
| B: `report/` presentation | 12 |

A'daki fark tamamen `report/`'tan gelir: `cli → report.*` (6) ve
`report.* → advise/explain/verify` (7) atlama çağrısı sayılıyor. `report/`
kullanıcının gördüğü her şeyi üretir ve uygulama katmanının sonuçlarını okur;
bu sunumun tanımıdır. B seçildi. Seçim ihlal sayısını düşürdüğü için değil,
A'daki 13 ek ihlalin hiçbiri bir tasarım sorununa işaret etmediği için:
hepsi "sunum kodu altyapı diye etiketlenmiş" demek.

## 2. İhlaller (B, 12)

| Tür | Adet | Örnek | Karar |
|---|---:|---|---|
| Uygulama → sunum geri çağrısı | 1 | `advise.selector → report.terminal` | Gerçek bulgu, aşağıda |
| Domain → altyapı | 2 | `analysis.scanner`, `analysis.architecture → integrations.importlinter` | Gerçek bulgu, aşağıda |
| Uygulama/sunum → altyapı | 9 | `advise.advisor → providers.base`, `cli → llm.cache` | Şema uyumsuzluğu |

- **`selector → report.terminal`.** `class_violations` ve
  `function_violations` eşik mantığıdır ama terminal modülünde duruyor;
  hedef seçimi onları oradan alıyor. Doğru yer eşiklerin yanı (`config` ya
  da `analysis`). Bu oturumda taşınmadı: `src/` ve `tests/`'te 22 satırda
  geçiyor ve Blok 3'ün döngüsü sınıf/fonksiyon hedefleriyle çalışır, modül yerleşimini hedef
  alamaz. Açık iş olarak STATUS'ta.
- **`analysis → integrations.importlinter`.** Domain, başka bir aracın
  config dosyasını okuyan adaptörü doğrudan çağırıyor (iki yerde, fonksiyon
  içi import). Doğru biçim, beyanın `cli`/`scanner` sınırında okunup
  analize veri olarak geçmesi. Aynı gerekçeyle ertelendi.
- **Dokuz uygulama/sunum → altyapı ihlali.** Varsayılan şema bağımlılığın
  tersine çevrildiği (port/adaptör) bir mimari varsayar: altyapı domain'e
  bağlanır, tersi değil. RefactorLens klasik katmanlıdır: `advisor`,
  `providers.base`'deki sözleşmeyi doğrudan çağırır. Bu ihlaller şemanın bir
  özelliğidir, koddaki bir hata değil; `arch.scheme.allowed` içinde
  `application: [domain, infrastructure]` yazılırsa kaybolurlar. Beyan bu
  satırı **eklemedi**: ihlallerin görünür kalması, aracın varsayılanıyla
  kendi kodu arasındaki farkı kayıtta tutar.

## 3. Kokular

45 modül, 68 sınıf, 414 fonksiyon ve metot. Kokular (önce): 23
`long_method`, 16 `too_many_params`, 2 `feature_envy_candidate`. Sınıf
düzeyinde koku yok (`god_class`, `data_class` 0). Listenin tamamı tarama
raporunda.

- 23 `long_method`'un 10'u sunum katmanında: `cli` komutları (3) ve
  `report/*` render/markdown fonksiyonları (7).
- `too_many_params`'ın ikisi sağlayıcıların `generate` metodu (5 parametre,
  eşikte). `cli` komutları K6 giriş noktası kuralıyla artık koku almıyor;
  ilk dogfooding'de (STATUS) 19 vakanın çoğu onlardı.
- Bu oturumda yazılan `explain.template.translate` da listedeydi (CC 23, LOC
  71). Aracın kendi yeni kodunu yakalaması döngünün hedeflerinden birini
  verdi.
- `advisor.validate_constraints` `long_method` alıyor ama deney protokolü
  gereği donmuş; hedef alınmadı.

## 4. Döngü: `advise` → uygulama → `verify`

`rlens advise .` (varsayılan seçim, `top_n` 3), Groq
`openai/gpt-oss-120b`, sıcaklık 0.2, önbelleksiz. Tek koşu, hedef başına bir
öneri. Seçilen üç hedef de fonksiyon:

| Hedef | Önce | Öneri |
|---|---|---|
| `analysis.interface:public_interface` | CC 33, NESTING 5 | iki yardımcı çıkar |
| `explain.template:translate` | CC 23, NESTING 4, LOC 71 | üç yardımcı çıkar |
| `report.verify:render_verify` | CC 21, LOC 87, PARAMS 5 | beş render yardımcısı çıkar |

**Uygulama en dar yorumla.** Modelin verdiği kod ve adlar kullanıldı. İki
sapma kayıtlı: `translate` önerisinin yeni gövdesi `modules` değişkenini
tanımlamadan kullanıyordu; çalışması için gereken tek satır
(`modules = payload.get("modules", [])`) eklendi. `render_verify` önerisi
yalnızca beş yardımcıyı adlandırdı; adı geçmeyen bloklar (karşılaştırılamazlık
uyarısı, eklenen/silinen listesi, küme tablosu) ana fonksiyonda kaldı.
Modelin İngilizce yorumları, ölçümden sonra Türkçe docstring'e çevrildi; LOC
yorumları ve docstring'leri saymadığı için metrikler değişmedi (yeniden
tarandı, aynı).

**Davranış kapısı:** 1542 paket testi (10 atlandı) ve 91 fikstür testi geçti.

**Sonuç:** tahmin doğruluğu 9/9, doğrulanamayan 1 (bir fonksiyon için DCC).

| Hedef | CC | LOC | NESTING |
|---|---|---|---|
| `public_interface` | 33→1 | 50→8 | 5→0 |
| `translate` | 23→3 | 71→11 | 4→0 |
| `render_verify` | 21→7 | 87→31 | 2→1 |

9/9, FINDINGS-1'in ayrımıyla tutarlı: tahminlerin hepsi eksiltici
(subtractive) metriklerde (CC, LOC, NESTING, PARAMS `same`). Kalıntı bırakan bir değişiklik
yoktu; fonksiyon çıkarmak hedefte hiçbir şey bırakmaz.

## 5. Bulgu: karmaşıklık taşındı, azalmadı

Hedeflerin sayıları çöktü, `verify` üçüne de "improved" dedi. Modül düzeyinde
toplam:

| Modül | Önce: hedef CC / LOC | Sonra: hedef + yardımcılar CC / LOC |
|---|---|---|
| `analysis.interface` | 33 / 50 | 36 / 58 |
| `explain.template` | 23 / 71 | 26 / 82 |
| `report.verify` | 21 / 87 | 26 / 99 |

Toplam CC her üç durumda **arttı** (her yeni fonksiyon CC'ye 1 ekler). Daha
önemlisi: `_collect_class_attributes` CC 27, NESTING 5, yani eşiğin kritik
seviyesinin üstünde. `public_interface`'in karmaşıklığı neredeyse olduğu gibi
yeni bir fonksiyona taşındı. `long_method` vermiyor (LOC 37 < 40);
`verify`'ın tablosunda yalnızca "added" satırı olarak görünüyor, metrikleri
yok. Kokular tarafında `_collect_sentences` yeni `long_method`,
`_build_summary` yeni `too_many_params` (6) aldı; `verify` bunları gösterdi.

Bu, FINDINGS'teki "kalıntı" gözleminin fonksiyon düzeyindeki karşılığı
değil, farklı bir şey: tahmin doğru, hedef iyileşti, sorun başka bir birime
geçti. Model bunu öngörmedi ve kontratta öngörebileceği bir alan yok
(`expected_effect` yalnız hedefin metriklerini sorar). `verify` taşınmayı
kısmen gösteriyor (kokular), eşik aşan yeni birimi göstermiyor. Pürüz F5.

**Sınırlılık:** tek model, tek koşu, üç hedef, üçü de aynı öneri türü
(fonksiyon çıkarma). Önerileri uygulayan, aracı geliştiren oturumun
kendisi (asistan). Bu bir bulgu değil, bir örnek: FINDINGS'e girmez.
