# LensBench v1 — ön kayıt

> **Durum: TASLAK, model listesi ve bütçe kullanıcı onayı bekliyor.** Bu belge
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

**H1 — Geri besleme doğruluğu artırır.** `loop3` koşulunda, model başına:
son iterasyonun doğruluğu − ilk iterasyonun doğruluğu (her iki uçta ≥ 10
doğrulanabilir tahmin olan modeller).
- Destekleniyor: modellerin ortalama artışı ≥ 10 puan **ve** modellerin en
  az dörtte üçünde artış > 0.
- Çürütüldü: ortalama artış ≤ 0 **ve** modellerin en az dörtte üçünde ≤ 0.
- Yetersiz: koşulu sağlayan model sayısı < 4.

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

## 5. Modeller ve bütçe — kullanıcı kararı

Plan: en az 4 model; ≥ 3 ücretsiz ya da lokal, 1 pahalı kontrol. Model
adları koda gömülmez (kilitli karar); bu bölüm ilk çağrıdan önce
doldurulur ve sonra değişmez.

| # | Sağlayıcı | Model | Tür |
|---|---|---|---|
| 1 | _ | _ | _ |
| 2 | _ | _ | _ |
| 3 | _ | _ | _ |
| 4 | _ | _ | kontrol |

Çağrı sayısı, model başına (`rlens bench run --dry-run`): **108 ile 306
arası** (48 birim; en az: onarımsız, `loop3` erken durur; en çok: her çağrı
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
`bench/lensbench-v1/suite.yaml`.

Bu taslak yazıldığında: `prompt_hash` `b4e04b5ebd198adb`, `suite_hash`
`05a5c58a0239ffc6`.
