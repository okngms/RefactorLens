# LensBench v1 — ön kayıt

> **Durum: DONDU (2026-10-03), ilk model çağrısından önce.** Bu belge
> sonuçlardan **önce** yazıldı. İlk gerçek model çağrısı yapıldığı anda
> donar: hipotezler, ölçüler, eşikler, hedef seti, koşullar ve tekrar sayısı
> değişmez. Değişiklik gerekirse yeni bir suite sürümü (`lensbench-v2`) ve
> yeni bir ön kayıt yazılır; v1 sonuçları onunla birleştirilmez. Bu kural
> Faz 5 protokolünün kuralıdır (AGENTS.md, "protocol is fixed in advance").

Plan: `docs/02` §7, Aşama 6. Kod: `src/rlens/bench/`. Suite:
`bench/lensbench-v1/suite.yaml`.

## 1. Soru

LLM'ler kendi refactoring önerilerinin yapısal etkisini ne kadar doğru tahmin
ediyor, ve bu doğruluk geri beslemeyle, refactoring türüyle ve değişikliğin
geride bıraktığı kalıntıyla nasıl değişiyor? LensBench refactoring başarısını
ölçmez: tahmin doğruluğunu, kalibrasyonu, kısıt uyumunu ve metrik oyunlamayı
ölçer.

## 2. Hipotezler ve karar kuralları

Her hipotez için üç sonuç vardır: **destekleniyor**, **çürütüldü**,
**sonuçsuz**; veri yetmezse **yetersiz veri**. Kurallar
`src/rlens/bench/report.py`'de kodludur ve buradaki sayılarla aynıdır.
Doğruluk = isabet / (isabet + ıska); doğrulanamayan tahmin hiçbir orana girmez,
ayrıca sayılır (invariant).

Hükümler yalnızca **birincil setle** verilir (§5). "Modellerin en az dörtte
üçü" yukarı yuvarlanır: üç modelde üçte üç, yani hepsi.

**H1 — Geri besleme doğruluğu artırır.** `loop3` koşulunda, model başına:
son iterasyonun doğruluğu − ilk iterasyonun doğruluğu (her iki uçta ≥ 10
doğrulanabilir tahmin olan modeller).
- Destekleniyor: modellerin ortalama artışı ≥ 10 puan **ve** modellerin en
  az dörtte üçünde artış > 0.
- Çürütüldü: ortalama artış ≤ 0 **ve** modellerin en az dörtte üçünde ≤ 0.
- Yetersiz: koşulu sağlayan model sayısı < 3.

**H2 — Karakterizasyon testleri davranış tutarsızlığını daha çok yakalar.**
Ertelendi. Aynı patch'e iki kapının da uygulanmasını ister; v1 bunu yapmaz.
Ölçülmeden "desteklenmedi" denmez.

**H3 — Modeller aşırı güvenlidir.** Model başına, güven beyan edilmiş
doğrulanabilir tahminlerde (≥ 10): ortalama güven − doğruluk.
- Destekleniyor: modellerin en az dörtte üçünde fark > 0.10.
- Çürütüldü: modellerin en az dörtte üçünde fark ≤ 0.
- Model büyüklüğüyle ilişki yalnızca betimlenir; 4 modelle iddia kurulmaz.
- `confidence` opsiyoneldir (kilitli karar); güvensiz tahmin dışarıda kalır
  ve kapsama olarak raporlanır.

**H4 — Doğruluk refactoring türüne göre değişir.** Bütün modeller birlikte;
her tahmin, iterasyonunda tespit edilen birincil türe atanır (`unknown`
dışındaki en sık tür; yalnızca `unknown` varsa `unknown`). ≥ 20 doğrulanabilir
tahmini olan türler.
- Destekleniyor: en yüksek ve en düşük tür doğruluğu arasındaki fark ≥ 20
  puan.
- Çürütüldü: fark ≤ 10 puan.
- Yetersiz: koşulu sağlayan tür < 2.

**H5 — Kalıntı (yeni, Aşama 4 ile ölçülebilir hale geldi).** NOM ve LCOM4
için "down" tahminleri, değişiklik delege eden sarmalayıcı bıraktığında daha
sık tutmaz. Iska oranı (sarmalayıcılı) − ıska oranı (sarmalayıcısız), her
grupta ≥ 10 doğrulanabilir tahmin.
- Destekleniyor: fark ≥ 30 puan.
- Çürütüldü: fark ≤ 10 puan.
- Bu, FINDINGS-1/2'deki "kalıntı" gözleminin (13 tahminden kurulmuş bir
  hipotez) bağımsız verideki sınamasıdır. Grupları "aritmetik/yapısal" diye
  adlandırmak yasaktır (AGENTS).

## 3. Hedef seti

`bench/lensbench-v1/suite.yaml`; projeler geçici git depolarına kopyalanıp
içerik özetiyle dondurulur (`project_hashes`).

| Proje | Hedef | Kapı |
|---|---|---|
| `examples/messy_project` | `god:OrderManager` | kendi testleri (91) |
| `examples/messy_project` | `utils:classify_order` | kendi testleri |
| `examples/layered_project` | `src.services.order_service:OrderService` | kendi testleri (71) |
| `examples/untested_project` | `inventory.stock:Stock` | karakterizasyon testleri |

**Bilinen sınır:** plan "seçilmiş açık kaynak projelerin dondurulmuş
commit'leri" diyordu. Korpus projeleri (`experiments/hardening/.cache`)
testleri için bağımlılık kurulumu ister; v1'e alınmadı. Hedef seti üç küçük
fikstürden oluşur ve sonuçlar bu kapsamla sınırlı raporlanır.

## 4. Koşullar ve tekrarlar

| Koşul | Mimari bağlam | Metrik kuralları | İterasyon |
|---|---|---|---|
| `base` | açık | kapalı | 1 |
| `no-arch` | kapalı | kapalı | 1 |
| `metric-rules` | açık | açık | 1 |
| `loop3` | açık | kapalı | 3 |

- Her (hedef × koşul) için **3 tekrar**; sıcaklık **0.2**. Önbellek kapalı:
  tekrarlar bağımsız örneklemlerdir.
- Her iterasyonda **1. öneri** uygulanır (Faz 5 kuralı).
- Uygulama otomatik ve en dar yorumla: patch istemi "önerinin söylemediği
  hiçbir şeyi değiştirme" der; tahmin (`expected_effect`) patch istemine
  girmez.
- Kapıyı geçmeyen değişikliğin metrik deltası sayılmaz; `broken` ayrı
  raporlanır.
- **Bütün tekrarlar raporlanır**; hiçbir koşu "kötü örnek" diye atılmaz.
  Sağlayıcı hatasıyla yarım kalan birim yeniden koşulur (kayıt dosyası).

## 5. Modeller ve bütçe

Kullanıcı kararı (2026-10-03): şimdilik ücretsiz modeller; liste düzenlenebilir
ve genişletilebilir (`bench/lensbench-v1/models.yaml`). Model adları koda
gömülmez (kilitli karar); dosyadadır.

**Birincil set** (`primary: true`) — hükümler yalnızca bununla verilir ve
ilk çağrıdan sonra değişmez:

| # | Sağlayıcı | Model |
|---|---|---|
| 1 | groq | `openai/gpt-oss-120b` |
| 2 | groq | `openai/gpt-oss-20b` |
| 3 | groq | `qwen/qwen3.8-27b` |

**Sonradan eklenen modeller** `primary: false` ile eklenir: raporda tablolarda
görünür, **hükmü değiştirmez**. Sonuçlar görüldükten sonra model eklemek, bir
hükmü istenen yöne çekmenin yoludur; bu kural onu kapatır.

**Taslaktan değişiklik (ilk çağrıdan önce):** taslak "en az 4 model, biri
pahalı kontrol" diyordu; kullanıcı ücretsiz modelleri seçti. Model eşiği
4 → 3 indi (`report.MIN_MODELS`); karar kurallarının eşikleri değişmedi.
Pahalı bir kontrol modelinin yokluğu bir sınırlılıktır (§7).

Çağrı sayısı, model başına (`rlens bench run --dry-run`): **108 ile 306
arası**; üç model için 324 ile 918. (48 birim; en az: onarımsız, `loop3` erken durur; en çok: her çağrı
bir onarım ister, `loop3` üç iterasyonun tamamını koşar). Groq ücretsiz
katmanındaki dakikalık token sınırı (8000) koşuyu yavaşlatır; sağlayıcı
hatasıyla kesilen koşu aynı komutla sürer.

## 6. Analiz sırası

1. Metrik bazında doğruluk (model × metrik), sonra koşul bazında.
2. Ön kayıtlı hipotezler, yukarıdaki kurallarla; rapor bunları otomatik
   verir (`rlens bench report`).
3. Ön kayıtta olmayan her analiz "sonradan" diye ayrı başlıkta raporlanır.

## 7. Sınırlılıklar (FINDINGS-3'te açıkça yazılacak)

- Hedef seti üç küçük fikstür; açık kaynak projeler yok.
- Üç model de ücretsiz katmandan; pahalı bir kontrol modeli yok. Model
  büyüklüğü ya da sağlayıcıyla ilgili genelleme yapılmaz.
- Fikstürleri ve aracı tasarlayan aynı kişi/oturum; ön kayıt bu yanlılığa
  karşı tek savunma.
- Metrikler Python'a uyarlanmıştır; metrik iyileşmesi tasarım iyileşmesi
  değildir.
- Tür tespiti kural tabanlıdır ve yanılabilir (`confidence` ile raporlanır).
- Token tahmini karakter/4.

## 8. Donan dosyalar

İlk çağrıdan sonra değişmez (değişirse `prompt_hash` değişir ve rapor
sonuçları ayırır): `src/rlens/advise/prompts.py`, `src/rlens/apply/prompts.py`,
`src/rlens/chartests/generator.py` (talimat), `src/rlens/loop/feedback.py`,
`bench/lensbench-v1/suite.yaml`, `bench/lensbench-v1/models.yaml`'ın birincil
satırları.

Donduğunda: `prompt_hash` `b4e04b5ebd198adb`, `suite_hash` `05a5c58a0239ffc6`,
`models.yaml` sha256 `95370c0ab9dbef65` (ilk 16 karakter).

## 9. İşletme notları (koşu sırasında)

Ön kayıttan sonra eklenen her kural burada, zamanı ve gerekçesiyle durur.
Hiçbiri prompt'ları, hedefleri, koşulları ya da karar eşiklerini değiştirmez
(`prompt_hash` ve `suite_hash` aynı kaldı).

**N1 — Sağlayıcının istek başına sınırı (2026-10-03).** İlk modelin 4.
biriminde Groq bir isteği HTTP 413 ile reddetti ("Request too large … Limit
8000, Requested 8007"). O ana kadar 3 birim tamamlanmıştı ve sonuçları
yalnızca kaydın doğru yazıldığını görmek için açılmıştı; hiçbir oran
hesaplanmadı.
- Kural: istek başına sınırı aşan istek **ölçüm boşluğudur**, modelin hatası
  değildir. Birim `provider_limit` durma nedeniyle kaydedilir (tamamlanmış
  iterasyonlar korunur), **yeniden denenmez** ve raporda model başına sayılır.
- Neden yeniden denenmez: model sıcaklık 0.2 ile örneklenir; "sığana kadar
  denemek" yalnızca kısa yanıtları seçer. 5a'daki 429 kayıpları tam olarak
  bu yanlılığı üretmişti.
- Aynı nedenle iki yol düzeltildi: `apply`'ın onarım çağrısı 413 alırsa
  sonuç artık `rejected` (modelin başarısızlığı) sayılmaz; `advise`'ın onarım
  çağrısı 413 alırsa öneri `unstructured` (sözleşme ihlali) sayılmaz.
- Hangi isteğin sınırı aştığı bilinmiyor (birim kaydedilmeden düştü);
  aday, modelin uzun yanıtını tekrarlayan `advise` onarım istemidir.

**N2 — Günlük kota (2026-10-03).** İlk modelin 15. biriminde Groq günlük
token sınırını bildirdi (HTTP 429, "tokens per day: Limit 200000"); birim
başına ~14 000 token harcanıyor, model başına 48 birim birkaç güne yayılır.
- Kural: 429 ile düşen birim **yeniden koşulur**. N1'den farkı: 429'da hiçbir
  yanıt gözlenmez; yeniden koşmak yanıtlar arasından seçim yapmaz, yalnızca
  zamanlamayı değiştirir. Yarım kalan birim (ör. `loop3`'ün 3. iterasyonu)
  baştan koşulur; yarım hali kaydedilmez.
- `rlens bench run --models` kotaya takılan modeli bırakıp sıradakine geçer;
  `--wait-minutes` ile hepsi takılınca bekleyip yeniden dener.

**N3 — Kesilen öneri yanıtı (2026-10-03).** `gpt-oss-20b`'nin 10. biriminde
Groq bir `advise` yanıtını çıktı sınırında kesti (`finish_reason: length`);
sınır sağlayıcının varsayılanıydı. Kesilme `loop` içinde yakalanmıyordu ve
koşuyu düşürdü.
- Bench'te öneri çağrıları artık patch çağrılarıyla aynı çıktı sınırını alır
  (`apply.max_output_tokens`, 16 384). Biten birimler etkilenmez: o ana kadar
  biten 24 birimin hiçbirinde kesilme olmadı (olsaydı koşu düşerdi); sınırı
  yükseltmek yalnızca kesilecek yanıtları değiştirir.
- Bu sınırı da aşan öneri yanıtı N1 gibi **ölçüm boşluğudur**: birim
  `output_limit` ile kaydedilir, yeniden denenmez, raporda sağlayıcı sınırı
  sütununda sayılır.
- Patch yanıtının kesilmesi `apply`'da zaten `rejected` (gerekçesiyle) olarak
  kaydediliyordu; ön kayıtlı hiçbir hipotez reddedilen patch sayısını
  kullanmaz.

**N4 — Kullanılamayan birincil model ve yerine geçen (2026-10-03).**
`qwen/qwen3.8-27b` Groq ücretsiz katmanında hiçbir isteği geçiremiyor: Groq
her isteği HTTP 429 "Request too large … output tokens per minute (OTPM):
Limit 1000, Requested 1069" ile reddetti; tek cümlelik bir deneme istemi de
aynı yanıtı aldı. Modelden **hiçbir birim tamamlanmadı**, hiçbir yanıt
gözlenmedi; diğer iki modelden o ana kadar biten birimlerin (16 + 16) hiçbir
oranı hesaplanmadı.
- Kod hatası: bu 429 kota sanılıp `--wait-minutes` ile sonsuza dek yeniden
  deneniyordu. Gövdesi "Request too large" diyen 429 artık N1'deki gibi
  `ProviderRequestTooLarge`'tır, yeniden denenmez.
- Birincil set değişikliği: qwen çıkar, yerine Gemini ücretsiz katmanından
  bir model girer (`providers/gemini.py`, AGENTS.md'de öngörülen opsiyonel
  adaptör). Kullanıcı kararı. Gerekçe: §5'in "ilk çağrıdan sonra değişmez"
  kuralı sonuca bakarak model seçmeyi engellemek içindir; burada değişen
  modelden hiç sonuç yok ve değiştirme kararı diğer modellerin sonuçları
  görülmeden verildi. Değiştirilmeseydi iki birincil modelle H1 ve H3 kural
  gereği "yetersiz veri" çıkardı.
- Eşikler, hedefler, koşullar ve prompt'lar değişmedi (`prompt_hash`,
  `suite_hash` aynı). Değişen yalnızca `models.yaml`'ın birincil satırı;
  yeni sha aşağıda.
- Yeni sınırlılık (§7): birincil set artık iki sağlayıcıdan; sağlayıcı ile
  model farkı ayrıştırılamaz.
