# RefactorLens — Sürümlere Göre Kod İşlev Haritası (v2 → v4)
### Doküman setini (`00`–`04`) güncelleyen özet — 2026-09-03

> **Amaç:** Araştırma sentezi ve repo'nun gerçek durumu sonrasında kodun **her sürümde ne yapacağını** tek yerde, komut ve işlev düzeyinde tanımlamak. Bu dosya `00`–`04`'ün sürüm bölümlerini geçersiz kılar; §6'da o dosyalara uygulanacak somut değişiklikler listelenir. Kilitli ilkeler (kod çalıştırılmaz*, `—`≠0, bilinmeyen anahtar hatadır, model adı koda gömülmez, davranış kapısı) her sürümde korunur. (*v3 `apply` bilinçli istisnadır — kullanıcının kendi test komutu çalıştırılır.)

---

## 0. Proje tek cümleyle (her sürümde geçerli)

RefactorLens, Python kodunun tasarım ve mimari kalitesini ölçer, ölçümleri bir LLM'e **kanıt** olarak verir, modelden her öneri için **ölçülebilir tahmin** ister ve değişiklik sonrası hem kodun iyileşip iyileşmediğini hem de **modelin tahmininin ve güveninin doğru olup olmadığını** puanlar.

**Araştırma sorusu (sabit):** LLM'ler kendi refactoring önerilerinin yapısal etkisini ne kadar doğru tahmin ediyor ve neyden etkileniyor?
Sürümler bu soruya eklenen **değişkenler**dir: v1 = hiçbir bağlam; v2 = mimari bağlam + kalibrasyon; v3 = kapalı döngü + geri besleme + benchmark; v4 = zaman + Python'a özgü kalite modeli + platform.

---

## 1. v1.0 (yayında) — kodun bugün yaptığı

| Komut | İşlev |
|---|---|
| `rlens scan <path>` | AST ile fonksiyon metrikleri (CC, LOC, PARAMS, NESTING) ve sınıf metrikleri (NOM, WMC, LCOM4, DAM/`dam_strict`, DCC isim-tabanlı, CAM koşullu) → terminal tabloları + `scan-*.json`; eşik ihlalleri; `--fail-on-violation` |
| `rlens advise <path>` | Eşik ihlaline göre en kötü N hedefi seçer; hedef kod + bağımlı sınıf imzaları + metrik tablosu + `[WARN]/[CRITICAL]` bayrakları (ham eşik yok) ile prompt; JSON şemalı yanıt; her öneri metriğe bağlı + `expected_effect[{metric,direction}]`; `unlinked`/`unstructured` etiketleri; `--dry-run`; Groq/Ollama; bütçe + önbellek (v2 Aşama 0'dan) |
| `rlens verify <path>` | İki scan raporu arasında sınıf/fonksiyon deltaları; `--advice` ile tahmin puanlama (doğrulanamayanlar hariç); `--applied` ile yalnız uygulanan öneri; `outcome: improved/regressed/mixed`; `--fail-on-regression` |
| (dahili) | `analysis/imports.py`, `graph.py`, `architecture.py`: import grafiği, SCC, Ca/Ce/instability, beyanlı katman ataması, 4 ihlal türü — **CLI'dan henüz erişilmiyor** |

Bulgu: FINDINGS-1 (13 tahmin; subtractive metrikler 6/6, residue-dependent 0/7; arayüz-silme vakası).

---

## 2. v2.0 — "Mimari bağlam ve kalibrasyon"

**Değişken:** Model mimari bağlamı ve metrik hesaplama kuralını bildiğinde tahmin doğruluğu, kısıt uyumu ve kalibrasyon değişiyor mu?

### 2.1 Komutlar ve işlevler
| Komut | v2'de ne yapar |
|---|---|
| **`rlens arch <path>`** (yeni) | Katman haritası (modül → katman; kaynak `declared` ya da import-linter; güven), import grafiği özeti, modül Ca/Ce/instability, ihlaller (`LV-DIR`=back-call, `LV-SKIP`=skip-call, `LV-CYCLE`=cyclic, `LV-LEAK`=leak; her biri literatür alias'ıyla) → `arch-*.json`; `--fail-on-violation` (tentative hariç) |
| `rlens scan` | + `Layer` ve `Smells` sütunları; katmana göre eşik (`thresholds.by_layer`); koku etiketleri (`god_class`, `data_class`, `feature_envy_candidate`, `long_method`, `too_many_params`, `layer_misfit`; kural tabanlı, `evidence`'lı); public arayüz kümesi rapora; modül tablosu; `--no-arch` ile v1 davranışı; `schema_version: 2` |
| `rlens advise` | + "Architectural context" bloğu (katman, izin matrisi, açık ihlaller, kokular); `--no-arch-context` (A/B); `--metric-rules` (hesaplama kuralları, A/B); çıktı şemasına `target_layer_after`, `constraints_respected`, `addresses_smells`, **`expected_effect[i].confidence`**; kısıt ihlal eden öneri `rejected` (silinmez); beyan/araç kısıt uyuşmazlığı sayılır |
| `rlens verify` | + ihlal deltaları (opened/closed), koku deltaları, public arayüz deltası; **Goodhart koruması** (`suspicious`: metrik iyileşti ama public üyeler kayıp ve taşınmamış); **kalibrasyon** (Brier, ECE, güven kovaları) |
| Config | `arch.{scheme, layers, allow_skip, min_confidence}`, `smells.*`, `thresholds.by_layer`, `budget`, `cache`, `verify.treat_suspicious_as_regression`; import-linter sözleşmesi okunur |

### 2.2 v2.0'da olmayanlar
Katman **çıkarımı** (v2.1), tip çıkarımı, `apply`, Action, history.

### 2.3 v2.1 — Katman çıkarımı
Konvansiyon + framework tanıma + bağımlılık yönü → katman + güven; `unknown`; `tentative` ihlaller. Kabul: 3 gerçek projede elle doğrulanmış doğruluk ≥%80; altında "weak signal".

### 2.4 Bulgu
FINDINGS-2: 5a (108 öneri-düzeyi çalıştırma: kısıt uyumu, `rejected`, `data_class` etkisi, tutarlılık, güven dağılımı) + 5b (12 uygulanmış vaka: metrik başına tahmin doğruluğu, Sınıf A/B, Brier/ECE). Literatür: SATT/Dósea/Ernst, Canedo 2026, Spiess ICSE'25, Cordeiro TOSEM 2025, DataRef, Gnoyke, SpecBench.

---

## 3. v3.0 — "Kapalı döngü, geri besleme, LensBench"

**Değişken:** Döngü otomatik kapanıp modele kendi hatası geri verildiğinde tahmin doğruluğu ve kalibrasyon iterasyonla iyileşiyor mu? Hangi metrikler oynanabilir (Gameability), hangileri tahmin edilemez (Structural Opacity)?

### 3.1 Komutlar ve işlevler
| Komut | v3'te ne yapar |
|---|---|
| **`rlens apply <path>`** (yeni) | Seçili öneri için modelden unified diff ister; **git worktree + ayrı branch**'te uygular; dosya kısıtı (hedef + `--allow-files`); davranış kapısı (kullanıcının `tests.command`'ı, timeout); geçmezse worktree silinir; geçerse `verify` koşar; **asla merge etmez**. Güvenlik invariant'ları `02 §2` |
| **`rlens loop <path>`** (yeni) | advise → apply → verify → geri besleme bloğu ("LCOM4 için down dedin, same çıktı") → advise; `--max-iter`; iterasyon başına doğruluk/kalibrasyon/kapı/maliyet |
| **`rlens chartests <path>`** (yeni) | Testsiz hedefler için LLM'e karakterizasyon testi ürettirir; refactoring **öncesi** mevcut kodda geçmek zorunda; kapı seviye 2 |
| **`rlens diff <base>..<head>`** (yeni) | İki git ref'i arasında metrik/ihlal/koku deltası; `--format=pr-comment`; **ratchet** (`.rlens-baseline.json`, yalnız yeni ihlal/regresyon kırar); LLM gerektirmez |
| **`rlens bench run/report`** (yeni) | **LensBench**: dondurulmuş hedef seti + prompt sürümü + koşullar (arch-context, metric-rules, loop 1/3) × modeller; ölçtükleri: tahmin doğruluğu (metrik ve Sınıf A/B başına), kalibrasyon, kısıt uyumu, `suspicious` oranı, kapı geçme, refactoring türü kırılımı; sonuç tablosu README'de |
| `rlens advise` | + ensemble (`--providers a,b`, uyuşma raporu); `expected_refactoring_type`; opsiyonel `[typed]` extra ile jedi/pyright tip çıkarımı → DCC/CAM `resolution: typed` |
| `rlens verify` | + refactoring türü tespiti (AST diff: Extract Method/Class, Move Method, Inline, Rename); `behavior_gate{level, passed}`; kalibrasyon model başına |
| **Meta-metrikler** (rapor alanı) | **Structural Opacity**: metrik × model başına tahmin edilemezlik (1 − doğruluk, Sınıf A/B ile ilişkilendirilir); **Gameability Index**: metrik başına (iyileşme ∩ {suspicious ∪ kapı hatası}) / iyileşme. İkisi de yalnız benchmark raporunda, doğrulama bölümüyle (Weyuker/Briand özellikleri tartışması, boyut kontrolü, mutasyon kapsamı raporu) |
| GitHub Action | `action/`: `rlens diff` + PR yorumu + ratchet |

### 3.2 Bulgu
FINDINGS-3 + LensBench tablosu: H1 geri besleme etkisi; H2 karakterizasyon testleri tutarsızlık yakalıyor mu; H3 aşırı güven ve model büyüklüğü; H4 tür bazında doğruluk; Structural Opacity ve Gameability'nin ilk ölçümleri. Literatür: SWE-Refactor, RefactorBench (Python), EMSE DataRef, Spiess, Krakovna/Helff, Manheim-Garrabrant.

---

## 4. v4.0 — "Zaman, Python'a özgü kalite modeli, platform"

**Değişken:** Mimari borç zaman içinde nasıl birikiyor; Python'a özgü çok düzeyli bir kalite modeli metrik→kalite bağını Java'dan taşınan modelden daha iyi kuruyor mu; hangi birimler (modül/sınıf/fonksiyon) LLM için daha "opak"?

### 4.1 Komutlar ve işlevler
| Komut | v4'te ne yapar |
|---|---|
| **`rlens history <path> --since <ref>`** (yeni) | Git geçmişinde örneklenen commit/tag'lerde `scan`+`arch`; zaman serisi; sınıf soy eşleme (`lineage: unknown` dürüstlüğü); erozyon göstergeleri (ihlal eğimi, god_class eğimi, domain Ce eğimi). *AGENTS.md'deki "no history" kilidi bu sürümde bilinçli açılır: `reports/` yerine git geçmişi kaynak olduğu için eski itiraz geçersizdir* |
| **`rlens hotspots <path>`** (yeni) | churn × karmaşıklık × koku; sıralı liste; "dormant debt" ayrı; `advise --by hotspot` |
| **`rlens report <path>`** (yeni) | Tek dosya HTML: özet, zaman serileri, katman haritası, ihlaller, hotspot'lar, son verify'lar; LLM yok |
| **`rlens policy check`** (yeni) | `rlens-policy.yaml` kuralları (yeni LV-DIR yasak, hotspot'ta WMC artamaz, god_class bütçesi) → CI exit kodu |
| **Python'a özgü kalite modeli** (`scan` genişlemesi) | Üç düzey: **fonksiyon** (mevcut + cognitive complexity, dönüş tipi çeşitliliği, mutable default), **sınıf** (mevcut + miras derinliği, mixin sayısı, dataclass ayrımı), **modül** (boyut, fan-in/out, public yüzey, anotasyon kapsamı, modül-düzeyi mutable durum, import-anı yan etkisi, modül-LCOM "çöplük modül"), **paket** (instability, soyutluk = Protocol/ABC oranı, katman uyumu). Tasarım özellikleri: modülerlik, kohezyon, kuplaj, kapsülleme (konvansiyonel), **açıklık** (Python'a özgü), sadelik. QMOOD ile örtüşen metrikler "uyumluluk alt kümesi"; NOP/MFA Python'da hesaplanmaz, gerekçesi belgelenir. Doğrulama: git vekilleri (churn, hata düzeltme yoğunluğu), küçük uzman değerlendirmesi, verify döngüsü korelasyonu (yeni yöntem) |
| Dil eklenti protokolü | `LanguageAnalyzer` arayüzü; Python analizörü ilk eklenti; süreç-dışı eklenti (C#, ayrı repo) aynı JSON şemasını üretir; `capabilities.adaptations` dil başına uyarlama notları |
| `advise` | + zaman bağlamı ("son 6 ayda 23 kez değişti, WMC 31→49"); model düzeyi (modül/sınıf/fonksiyon) öz-tahmin kırılımı |
| Ekip katmanı (koşullu) | `report --multi`, politika şablonları; barındırılan servis yok |

### 4.2 Bulgu
FINDINGS-4: hotspot sıralamasının öneri kabulüne etkisi; erozyon göstergelerinin bilinen büyük refactoring olaylarıyla örtüşmesi; Python kalite modelinin vekillerle doğrulanması; (iki dil varsa) statik tipli dilde tahmin doğruluğu farkı; modül düzeyi Structural Opacity.

---

## 5. Sürümler arası taşınan ve değişen kararlar (özet)

| Konu | Eski plan | Yeni |
|---|---|---|
| Katman çıkarımı | v2 Aşama 2 | **v2.1**; kabul ≥%80 doğruluk |
| Kalibrasyon (`confidence`, Brier/ECE) | v3 | **v2** |
| v2 yenilik iddiası | "katmana göre eşik" | SATT/Canedo etkisinin **öz-tahmine** taşınması |
| İhlal adları | yalnız `LV-*` | `LV-*` + literatür alias'ı |
| Boyut karıştırıcısı | yok | v2'den itibaren kaydedilir, v3'te kontrol değişkeni |
| Benchmark adı | RefactorBench | **LensBench** |
| Meta-metrikler | üç öneri | **Structural Opacity** birincil, **Gameability** ikincil (v3); role-conditioned rate SATT uygulaması olarak sunulur, yeni metrik değil |
| `history` | AGENTS.md'de kilitli "yok" | v4'te git geçmişi kaynaklı olarak açılır |
| Python'a özgü kalite modeli | yok | v4 çekirdek katkı; tohum v2 modül tablosu |
| Metrik sınıfları | aritmetik/yapısal | **subtractive / residue-dependent** (docs/SPEC-duzeltme-2.5) |

---

## 6. `00`–`04` dosyalarına uygulanacak değişiklikler

**`00-genel-bakis-ve-literatur.md`**
- §2 sürüm tablosu: bu dosyanın §1–4 başlıkları ve "değişken" satırlarıyla değiştir; v2.1 satırı ekle.
- §3 literatür: **SATT, Dósea, Ernst, Alves, Oliveira, Gil & Lalouche** (rol/eşik); **Arcan, Sharma 2020, Gnoyke 2021, Sas ATDI** (mimari koku); **Sarkar/Pruijt** (ihlal adları); **Canedo 2026, arXiv 2512.04273** (mimari bağlam→LLM); **Spiess ICSE'25, Lin 2026** (kalibrasyon); **Cordeiro TOSEM 2025, DataRef EMSE 2026, Liu ASE 2025** (LLM refactoring); **RefactorBench ICLR'25 (Python!), SWE-Refactor** (benchmark); **Helff 2026, CoreRHB, Manheim-Garrabrant** (reward hacking); **Weyuker/Briand/Kitchenham** (metrik doğrulama); **Vavrová & Zaytsev, PySmell, Alexandru** (Python kokuları — v4 modeli için). Yenilik iddiasını §7-sentez formülasyonuyla yeniden yaz.
- §4 fikir tablosu: "katman çıkarımı → v2.1", "kalibrasyon → v2", "Python kalite modeli → v4 (kabul, yeni)", "role-conditioned rate → SATT uygulaması" satırları.

**`01-v2-katman-farkinda-yorumlama.md`**
- Başlık altına not: "`v2-kalan-kapsam.md` ile birlikte okunur; Aşama 2 v2.1'e taşındı; kalibrasyon Aşama 4'e eklendi."
- §1.2 `advise/verify` satırlarına `confidence`, Brier/ECE, alias; §2.4 tabloya alias sütunu; §10 Aşama 5 → `docs/v2-duzeltme-asama5.md`.

**`02-v3-kapali-dongu-ve-benchmark.md`**
- Kalibrasyon bölümü (§6) "v2'de var; v3 model başına ve iterasyon başına genişletir" olarak kısalır.
- §7 LensBench'e Structural Opacity ve Gameability tanımları + doğrulama bölümü eklenir (bu dosya §3.1).
- Aşama 6 hipotezlerine H5: "Structural Opacity, Sınıf A/B ayrımıyla açıklanıyor mu?"

**`03-v4-zaman-ve-platform.md`**
- Yeni §: "Python'a özgü çok düzeyli kalite modeli" (bu dosya §4.1 satırı + ayrı `05-python-kalite-modeli.md`'ye referans).
- `history` için AGENTS.md kilidinin açılma gerekçesi.

**`04-ortak-spesifikasyon.md`**
- §2.5 → `docs/SPEC-duzeltme-2.5.md` (subtractive/residue-dependent).
- §6 öneri şeması: `predictions[i].confidence` v2'den itibaren opsiyonel; `status` değerlerine `rejected` v2'de.
- §7 rapor şemaları: `arch` ihlal nesnesine `alias`; `verify`'a `calibration`, `interface_delta`, `violation_deltas`, `smell_deltas`; `scan` özetine `baseline_size`.
- Yeni §11: meta-metrik tanımları (Structural Opacity, Gameability) — formül, kapsam, doğrulama gereksinimleri.

**Yeni dosya:** `05-python-kalite-modeli.md` — v4 modelinin tanımı: her metrik için tanım, hesaplama, hangi tasarım özelliğine bağlandığı, QMOOD karşılığı/uyumsuzluğu, doğrulama yöntemi. (Henüz yazılmadı; v3 sonunda yazılır.)
