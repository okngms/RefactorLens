# RefactorLens v4 — Zaman Ekseni ve Platform

> **Önkoşul:** v3.0.0 yayında; LensBench ve FINDINGS-3 tamamlanmış; GitHub Action'ın gerçek kullanıcıları var. `00` ve `04` okunmuş.
> **Tez:** v1-v3 kodun *anlık* fotoğrafını ölçer. Mimari borç ise zaman içinde birikir ve her sınıf eşit önemde değildir: sürekli değişen ve kötüleşen sınıf, hiç dokunulmayan kötü sınıftan daha önemlidir. v4 zaman eksenini ekler, çekirdeği dilden bağımsızlaştırır ve ekip kullanımına uygun raporlama/politika katmanı getirir.
> **Uyarı:** v4'ün üçüncü bloğu (ekip katmanı) yalnızca v3'ün kullanıcı verisi "talep var" diyorsa yapılır. Talep yoksa v4 = zaman ekseni + eklenti protokolü.

---

## 1. Kapsam (kilitli)

### 1.1 Yeni komutlar
| Komut | Ne yapar |
|---|---|
| `rlens history <path> --since <ref>` | Git geçmişinde seçilen commit/tag'lerde `scan`+`arch` koşar; metrik, ihlal ve koku zaman serisi üretir (`reports/history-*.json`) |
| `rlens hotspots <path>` | Değişim sıklığı (churn) × karmaşıklık/koku ile öncelik listesi; `advise` hedef seçimi bu listeyi kullanabilir (`--by hotspot`) |
| `rlens report <path>` | Tek dosya HTML özet raporu (zaman serisi grafikleri, katman haritası, hotspot tablosu); LLM gerektirmez |
| `rlens policy check` | `rlens-policy.yaml`'daki kuralları (örn. "domain'de yeni LV-DIR yasak", "hotspot'ta WMC artamaz") CI'da denetler |

### 1.2 Değişen komutlar
| Komut | v4 eklemesi |
|---|---|
| `scan/arch/advise/verify/diff` | Dil eklenti protokolü üzerinden çalışır; Python analizörü ilk eklenti (`rlens-lang-python`, çekirdekle birlikte gelir) |
| `advise` | Hedef seçiminde zaman bağlamı: "bu sınıf son 6 ayda 23 kez değişti, WMC 31→49" |
| `bench` | Çok dilli suite desteği (ikinci dil eklendiğinde) |

### 1.3 Yeni yatay özellikler
- **Dil eklenti protokolü:** analizörler `04 §7`'deki JSON şemasını üreten ayrı süreçler/paketler; çekirdek dil bilmez.
- **İkinci dil (ayrı proje):** C# analizörü (`refactorlens-dotnet`, Roslyn tabanlı, NuGet `dotnet tool`), aynı şemayı üretir. Bu dokümanda yalnızca **protokol** tanımlanır; C# implementasyonu ayrı doküman ister.
- **Politika-as-code:** ekip kurallarının sürümlenebilir tanımı.

### 1.4 Kapsam dışı
Barındırılan (hosted) servis, kullanıcı hesabı, gerçek zamanlı IDE entegrasyonu, Java. FUTURE.

---

## 2. Zaman ekseni

### 2.1 `history`
- Örnekleme: `--every N` commit ya da `--tags` ya da `--monthly`. Her nokta için worktree'de checkout → `scan`/`arch` (LLM yok).
- Çıktı: nokta başına proje özeti (toplam WMC, ihlal sayısı, koku sayısı, katman başına instability ortalaması) ve sınıf bazlı seriler (sınıf yeniden adlandırmaları `git log --follow` + imza benzerliğiyle en-iyi-çaba eşlenir; eşlenemeyen `lineage: unknown`).
- **Erozyon göstergeleri:** ihlal sayısı eğimi, `god_class` sayısı eğimi, domain katmanı Ce eğimi.

### 2.2 `hotspots`
- Churn: seçilen pencerede dosya/sınıf değişiklik sayısı ve değiştiren geliştirici sayısı (git log).
- Skor (varsayılan): `hotspot = norm(churn) × norm(WMC) × (1 + 0.5·smell_count)`; config ile ağırlıklar değişir.
- Çıktı: sıralı liste + gerekçe; "yüksek karmaşıklık, düşük churn" olanlar ayrı "dormant debt" listesinde (öncelik düşük).
- Literatür bağı: churn × complexity (Tornhill); README'de atıf.

### 2.3 `report` (HTML)
Tek dosya, bağımlılıksız (inline SVG/CSS); bölümler: özet kartları, zaman serileri, katman haritası (modül grafiği), ihlal listesi, hotspot tablosu, son `verify` sonuçları. LLM gerektirmez; ekip paylaşımı için tasarlanır.

## 3. Dil eklenti protokolü
- Çekirdek (`rlens`) → eklenti keşfi: Python entry point `rlens.languages`; her eklenti `LanguageAnalyzer` arayüzünü uygular: `discover(path) → files`, `analyze(files, config) → Report(schema_version=4)`, `capabilities() → {metrics: [...], arch: bool, interface: bool}`.
- **Süreç dışı eklentiler:** Python olmayan analizörler (C#) ayrı yürütülebilir olarak çalışır ve stdout'a aynı JSON'u yazar; çekirdek `languages.external: [{name, command}]` ile bağlar.
- Metrik tanımları ve uyarlama notları dil başına `capabilities.adaptations` alanında raporlanır (Python'da CAM koşullu; C#'ta koşulsuz gibi).
- Çekirdek `advise/verify/diff/bench` dilden bağımsız çalışır; prompt şablonları dil adını ve uyarlama notlarını içerir.

## 4. Politika-as-code
```yaml
# rlens-policy.yaml
version: 1
rules:
  - id: no-new-lv-dir-in-domain
    when: {layer: domain}
    forbid: {violation: LV-DIR, new: true}
  - id: hotspot-wmc-ratchet
    when: {hotspot_rank: {lte: 10}}
    forbid: {metric: wmc, delta: {gt: 0}}
  - id: god-class-budget
    max: {smell: god_class, count: 3}
```
`rlens policy check --base origin/main` → ihlaller ve exit kodu; GitHub Action girdisi olarak kullanılabilir.

## 5. Ekip katmanı (koşullu)
Yalnızca v3 kullanıcı verisi talep gösteriyorsa: birden çok repo için `report` birleştirme (`rlens report --multi`), takım bazlı özetler, politika şablon kütüphanesi. Barındırılan servis **bu sürümde yok**; yapılacaksa ayrı ürün dokümanı ve ayrı karar.

---

## 6. Config eklemeleri
```yaml
history:
  sample: {every: 25}        # veya {tags: true} / {monthly: true}
  since: "v1.0.0"
hotspots:
  window_days: 180
  weights: {churn: 1.0, wmc: 1.0, smell: 0.5}
languages:
  external: []               # [{name: csharp, command: "refactorlens-dotnet analyze"}]
```

## 7. Depo değişiklikleri
```
src/rlens/
├── core/plugin.py            # LanguageAnalyzer arayüzü, keşif
├── languages/python/         # v1-v3 analiz kodu buraya taşınır
├── history/{sampler.py, lineage.py, series.py}
├── hotspots/{churn.py, score.py}
├── report/html.py
└── policy/{schema.py, engine.py}
```

---

## 8. Aşama planı ve kabul kriterleri

### Aşama 0 — Çekirdek/eklenti ayrımı (davranış değişmez)
Python analizörünü `languages/python`'a taşı; `LanguageAnalyzer` arayüzü; tüm v3 testleri geçmeli (refactoring'in refactoring'i — kendi aracıyla `diff` çalıştırılıp raporlanır).
**Bitti ⇔** v3 test seti değişmeden geçer; `rlens diff` çekirdek ayrımı öncesi/sonrası "no regression" der; süreç dışı sahte eklenti (JSON basan script) çekirdekle çalışır.

### Aşama 1 — `history`
**Bitti ⇔** repo'nun kendi geçmişinde (RefactorLens v0.1→v3) seri üretiliyor; yeniden adlandırılan sınıf eşleniyor (test); erozyon göstergeleri hesaplanıyor.

### Aşama 2 — `hotspots` ve `advise --by hotspot`
**Bitti ⇔** fikstürde bilinen churn ile altın sıralama; `advise` zaman bağlamını prompt'a koyuyor (`--dry-run`).

### Aşama 3 — `report` ve `policy`
**Bitti ⇔** HTML rapor tek dosya, çevrimdışı açılıyor; politika örnekleri CI'da doğru kırıyor/geçiriyor (test).

### Aşama 4 — Protokolün ikinci dille doğrulanması
C# analizörü **ayrı repo**da geliştirilir (ayrı doküman). Bu aşamanın kriteri protokoldür:
**Bitti ⇔** dış analizörün ürettiği JSON çekirdekte `scan/arch/advise/verify` ile çalışıyor; uyarlama notları raporda; LensBench suite çok dilli koşabiliyor.

### Aşama 5 — FINDINGS-4
**H1:** Hotspot sıralaması, `advise` hedef seçimini metrik-sıralamaya göre daha "kabul edilen" önerilere yönlendirir (kullanıcı kabulü ya da davranış kapısı+iyileşme oranı ile ölçülür).
**H2:** Mimari erozyon göstergeleri, örnek açık kaynak projelerde bilinen "büyük refactoring" olaylarıyla örtüşür (vaka çalışması).
**H3 (iki dil varsa):** Modellerin yapısal tahmin doğruluğu statik tipli dilde (C#) Python'dan farklı mı?
**Bitti ⇔** `FINDINGS-4.md`; ham veri `experiments/v4/`; **v4.0.0** PyPI'da.

---

## 9. Riskler
| Risk | Savunma |
|---|---|
| Geçmiş taramada performans | örnekleme, dosya-hash önbelleği, paralel parse |
| Sınıf soy eşlemesinde hata | `lineage: unknown` dürüstlüğü; eşleme güveni raporda |
| Protokolün ikinci dil olmadan doğrulanamaması | sahte eklenti + JSON şema testleri Aşama 0'da |
| Ekip katmanının erken yapılması | koşul: v3 kullanıcı talebi; aksi halde yapılmaz |
| İki proje (Python + C#) paralel yükü | C# ayrı repo, ayrı doküman, ayrı zaman; protokol donduktan sonra başlar |

## 10. Devam talimatı
Sıra: çekirdek/eklenti ayrımı (davranış sabit) → history → hotspots → report/policy → protokol doğrulaması → FINDINGS-4. `schema_version: 4`; `04` güncellenir.
