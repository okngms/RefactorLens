# RefactorLens v2 — Katman-Farkında Metrik Yorumlama

> **Önkoşul:** `00-genel-bakis-ve-literatur.md` ve `04-ortak-spesifikasyon.md` okunmuş olmalı. v1.0 yayında ve çalışıyor olmalı.
> **Tez:** v1'de yapısal metrik tahminlerinin 0/7 başarısız olmasının olası bir nedeni modelin mimari niyeti bilmemesidir. Aynı DCC=8, application-service sınıfında tasarım gereği, domain modelinde kokudur. v2 katman yapısını tespit eder ve metrikleri bu bağlamda yorumlar; etkisini A/B ile ölçer.

---

## 1. Kapsam (kilitli)

### 1.1 Yeni komut
| Komut | Ne yapar |
|---|---|
| `rlens arch <path>` | Katman haritası (modül/sınıf → katman, kaynak, güven), bağımlılık grafiği özeti, modül Ca/Ce/instability, katman ihlalleri. `reports/arch-*.json` yazar. |

### 1.2 Değişen komutlar
| Komut | v2 eklemesi |
|---|---|
| `scan` | `Layer` ve `Smells` sütunları; katmana göre eşik; ihlal özeti; `--no-arch` ile v1 davranışı; public arayüz kümesi rapora yazılır |
| `advise` | Prompt'a katman rolü + mimari kısıtlar + ihlaller + koku etiketleri; `--no-arch-context` (A/B); `--metric-rules` (H2 A/B: hesaplama kuralları prompt'a eklenir); kısıt ihlal eden öneri `rejected`; bütçe/önbellek |
| `verify` | Katman ihlali deltaları; **Goodhart koruması** (`suspicious`); koku deltaları |

### 1.3 Yeni yatay özellikler
- **Koku etiketleri:** metriklerden türetilen, literatür kurallarına dayalı adaylar (bkz. §3).
- **Bütçe ve önbellek:** `budget` ve `cache` config blokları; prompt-hash tabanlı yanıt önbelleği.
- **import-linter uyumu:** `.importlinter` / `[tool.importlinter]` varsa sözleşmeler katman beyanı olarak okunur.

### 1.4 Kapsam dışı (v2'de yapılmaz)
`apply`, geri besleme, tip çıkarımı, GitHub Action, SARIF/HTML, git geçmişi, ek dil. Hepsi `02`/`03` dokümanlarında.

---

## 2. Katman tespiti

### 2.1 Sinyaller (öncelik sırası)
1. **Beyan (kesin):** `rlens.yaml → arch.layers` veya import-linter sözleşmesi. Beyan varsa çıkarım çalışmaz; `source: declared`.
2. **Konvansiyon:** dizin adları ve sınıf sonekleri (tablo `04 §5`). Framework tanıma (Django `models.py/views.py`, FastAPI router modülleri, Flask blueprint'leri) tabloyu genişletir.
3. **Bağımlılık yönü:** proje-içi import grafiği (modül düzeyi, `ast`; fonksiyon-içi/koşullu importlar `weak`). SCC'ler tek düğüme yoğunlaştırılır; topolojik derinlik hesaplanır. Derinlik konvansiyonla çelişirse güven düşer.

### 2.2 Güven skoru
`confidence = 0.5·conv + 0.3·dir + 0.2·neighbor`
- `conv`: konvansiyon eşleşmesi (dizin 1.0, sonek 0.7, framework 0.8, yok 0).
- `dir`: atanan katmanın topolojik derinlikle uyumu (0-1).
- `neighbor`: doğrudan bağımlılıkların katman dağılımının beklenen yönle uyumu (0-1).
`confidence < arch.min_confidence` (varsayılan 0.5) → `layer: unknown`. Tahmin zorlanmaz.

### 2.3 Şema ve izin matrisi
Varsayılan katmanlar (bağımlılık yönü üst → alt): `presentation → application → domain`; `infrastructure → domain`. Config ile tamamen değiştirilebilir (`arch.scheme`). Şemada olmayan katman adı config hatasıdır.

### 2.4 İhlal türleri
| Kod | Tanım | Tentative koşulu |
|---|---|---|
| `LV-DIR` | Ters yön (domain → infrastructure) | iki uçtan biri inferred ve güven < 0.7 |
| `LV-SKIP` | Katman atlama (presentation → infrastructure); `arch.allow_skip` ile kapatılabilir | aynı |
| `LV-CYCLE` | Import döngüsü (SCC boyutu > 1) | hiçbir zaman (yapısal gerçek) |
| `LV-LEAK` | Alt katman tipinin üst katmanın public imzasında görünmesi; yalnızca annotation varsa | aynı |
`tentative` ihlaller `--fail-on-violation` kapsamına girmez.

---

## 3. Koku etiketleri (yeni)

Metriklerden **kural tabanlı** türetilir; LLM kullanılmaz. Amaç: modele ve kullanıcıya "sayı" yerine "durum" vermek. Kurallar literatür eşiklerinden uyarlanmıştır ve config ile değiştirilebilir (`smells` bloğu).

| Etiket | Kural (varsayılan) | Not |
|---|---|---|
| `god_class` | NOM ≥ 20 **ve** WMC ≥ 50 **ve** LCOM4 ≥ 3 | Üç koşul birlikte; tek metrik yetmez |
| `data_class` | NOM ≤ 5 **ve** WMC ≤ NOM+2 **ve** DAM ≥ 0.5 **ve** public metotların ≥ %70'i erişimci desenli | v1'de belgelenen LCOM4 yanlış pozitifini etiketle nötrler |
| `feature_envy_candidate` | Bir metot, kendi sınıfının attribute'larından çok başka tek bir sınıfın attribute/metotlarına erişiyor (oran ≥ 2) | Sınıf değil **metot** düzeyi; isim tabanlı, her zaman `candidate` |
| `long_method` | CC ≥ warn **ve** LOC ≥ 40 | fonksiyon düzeyi |
| `too_many_params` | params ≥ warn | fonksiyon düzeyi |
| `layer_misfit` | Sınıfın koku/metrik profili katmanıyla uyumsuz (örn. domain sınıfında `LV-DIR` + yüksek DCC) | yalnızca katman güveni ≥ 0.7 ise |

Her etiket `evidence` alanıyla raporlanır (hangi metrik, hangi eşik). Etiketler `advise` prompt'una ve `verify` deltasına (`smells_added/removed`) girer.

---

## 4. Katmana göre yorumlama
- `thresholds.by_layer` ile katman bazlı eşik geçersiz kılma. `unknown` katman genel eşiği kullanır.
- Modül düzeyi Ca (afferent), Ce (efferent), instability = Ce/(Ca+Ce). Beklenti: domain düşük Ce, infrastructure yüksek Ce, presentation yüksek Ce/düşük Ca. Beklenti dışı yalnızca bilgi olarak işaretlenir (eşik yok).

## 5. `advise` prompt değişikliği
Eklenen blok (sabit şablon, `--dry-run` ile görülebilir):
```
## Architectural context
Target: orders.OrderManager — layer: application (inferred, confidence 0.82)
Layer rules: application may import [domain]; must NOT import [infrastructure, presentation].
Open violations involving target: LV-DIR orders → infra.db (tentative: no)
Smell labels: god_class (NOM=25, WMC=49, LCOM4=4)
## Instruction
Suggestions must respect layer rules. If a responsibility moves, name the destination layer.
```
`--metric-rules` verilirse ayrıca `04 §2`'deki hesaplama kuralları (kısa biçim) eklenir.

Çıktı şemasına eklenen alanlar: `target_layer_after`, `constraints_respected` (bool), `addresses_smells` (liste). `constraints_respected: false` ya da kural ihlali tespit edilen öneri `status: rejected` (silinmez; oran raporlanır — v1'deki `unlinked` mantığı).

## 6. Goodhart koruması (`verify`)
- Public arayüz kümesi: dunder hariç, `_` öneksiz metot ve attribute'lar; `scan` raporuna yazılır.
- Hedefin public kümesi küçüldüyse ve kaybolan üyeler projede başka sınıfa taşınmadıysa (aynı ad + benzer imza araması) → `outcome: suspicious`; rapor "metrikler iyileşti ancak N public üye kayboldu" der.
- `--fail-on-regression`, `suspicious`'ı yakalar (`verify.treat_suspicious_as_regression: true` varsayılan).

## 7. Bütçe ve önbellek
- `budget.max_calls_per_run` (vars. 10), `budget.max_tokens_per_call` (vars. 4000). Aşımda advise durur, rapor kısmi olduğunu belirtir.
- Önbellek anahtarı: `sha256(provider, model, prompt_text)`. Dizin `.rlens-cache/` (gitignore önerilir). `--no-cache` ile atlanır. Rapor özeti: `calls`, `cache_hits`, `tokens_in/out` (sağlayıcı veriyorsa).

---

## 8. Config eklemeleri
```yaml
arch:
  enabled: true
  scheme:
    layers: [presentation, application, domain, infrastructure]
    allowed:
      presentation: [application, domain]
      application: [domain]
      infrastructure: [domain]
      domain: []
    allow_skip: false
  layers:                          # beyan (opsiyonel)
    presentation: ["src/api/"]
    application: ["src/services/"]
    domain: ["src/domain/"]
    infrastructure: ["src/infra/"]
  conventions:
    extra_dirs: {application: ["usecases"]}
    extra_suffixes: {infrastructure: ["Gateway"]}
  min_confidence: 0.5
smells:
  god_class: {nom: 20, wmc: 50, lcom4: 3}
  data_class: {max_nom: 5, min_dam: 0.5, accessor_ratio: 0.7}
thresholds:
  by_layer:
    domain: {dcc: {warn: 4}}
    application: {dcc: {warn: 12}}
budget: {max_calls_per_run: 10, max_tokens_per_call: 4000}
cache: {enabled: true, dir: .rlens-cache/}
verify:
  treat_suspicious_as_regression: true
```
Bilinmeyen anahtar = hata.

## 9. Depo değişiklikleri
```
src/rlens/
├── analysis/
│   ├── imports.py        # import grafiği, weak importlar
│   ├── graph.py          # SCC, topolojik derinlik, Ca/Ce
│   ├── architecture.py   # katman atama (beyan/konvansiyon/yön), güven, ihlaller
│   ├── smells.py         # kural tabanlı koku etiketleri
│   └── interface.py      # public arayüz kümesi
├── advise/context.py     # mimari bağlam bloğu üretimi
├── llm/
│   ├── budget.py
│   └── cache.py
└── integrations/importlinter.py
examples/layered_project/          # 4 katmanlı fikstür, kasıtlı ihlaller
examples/layered_project/ARCH_SMELLS.md
```

---

## 10. Aşama planı ve kabul kriterleri

### Aşama 0 — Fikstür ve altyapı
- `examples/layered_project`: 4 katman; kasıtlı en az bir `LV-DIR`, bir `LV-SKIP`, bir `LV-CYCLE`, bir `LV-LEAK`; bir `god_class`, bir `data_class`, bir `feature_envy_candidate`; 1-2 muğlak modül (çıkarımın `unknown` demesi beklenir). Envanter `ARCH_SMELLS.md`. Davranış testleri.
- Config şeması genişletmesi + doğrulama testleri. Bütçe sayacı ve önbellek (sağlayıcıdan bağımsız katman).
- **Bitti ⇔** fikstür testleri geçer; `advise --dry-run` bütçe/önbellek özetini basar; aynı prompt ikinci koşuda cache'ten döner (test).

### Aşama 1 — Bağımlılık grafiği ve beyanlı `arch`
- import grafiği → SCC → derinlik → Ca/Ce; beyan edilmiş katmanlarla dört ihlal türü; import-linter okuma.
- **Bitti ⇔** beyanla `rlens arch examples/layered_project` `ARCH_SMELLS.md`'deki tüm ihlalleri bulur, fazlasını bulmaz (altın testler); 1 gerçek açık kaynak projede çökmeden çalışır.

### Aşama 2 — Katman çıkarımı
- Konvansiyon + framework + yön → katman + güven; `unknown`; `evidence`.
- **Bitti ⇔** beyan kaldırılınca fikstürde katmanlar ≥0.7 güvenle bulunur; muğlak modüller `unknown` (zorlamama testi); 3 gerçek projede elle inceleme → `experiments/arch_inference_review.md` (doğru/yanlış/unknown sayıları, hata örnekleri).

### Aşama 3 — Koku etiketleri ve `scan` entegrasyonu
- `smells.py`, `interface.py`; `Layer`/`Smells` sütunları; `by_layer` eşikleri; `--no-arch`; rapor `schema_version: 2`.
- **Bitti ⇔** fikstürdeki koku etiketleri altın değerlerle eşleşir; aynı sınıf farklı katman eşiğiyle farklı işaretlenir (test); v1 raporları okunur (uyumluluk testi).

### Aşama 4 — Katman-farkında `advise`, korumalı `verify`
- Bağlam bloğu, `--no-arch-context`, `--metric-rules`, `rejected` mantığı; `verify`'da ihlal/koku deltaları ve Goodhart koruması.
- **Bitti ⇔** `--dry-run` bağlam bloğunu gösterir; kısıt ihlal eden sahte öneri `rejected` (test); public üye silen sahte değişiklik `suspicious` (test); `smells_removed` doğru hesaplanır (test).

### Aşama 5 — Deney ve FINDINGS-2
**H1:** Katman bağlamı (a) kısıt uyumunu, (b) davranış testi geçme oranını, (c) yapısal metrik tahmin doğruluğunu artırır.
**H2:** Hesaplama kurallarının prompt'a eklenmesi yapısal tahmin doğruluğunu artırır.
**Tasarım:** 2×2 (arch-context × metric-rules); hedef seti = layered_project + 2-3 gerçek Python projesi (katman beyanı elle yapılır); en az 3 ücretsiz/lokal model (adları belgelenir) + 1 pahalı model 15-20 vakalık kontrol; koşul başına ≥50 doğrulanabilir tahmin. Öneriler elle uygulanır; davranış testleri kapı; `verify --applied` ile puanlama.
**Rapor:** `FINDINGS-2.md` — Setup → Results (H1/H2 tabloları, koşul başına tahmin doğruluğu aritmetik/yapısal ayrımıyla, `rejected` ve `suspicious` oranları) → vaka analizleri (en az 4) → literatürle bağ (arXiv 2509.07763, SLR, SpecBox paraleli) → Limitations.
**Bitti ⇔** FINDINGS-2 yayınlandı; ham veri `experiments/v2/`; **v2.0.0** PyPI'da; README güncel.

---

## 11. Riskler
| Risk | Savunma |
|---|---|
| Çıkarım yanlış pozitifleri | güven eşiği, `tentative`, beyan önceliği, gerçek projede elle inceleme |
| Koku kurallarının tartışmalılığı | kurallar config'te; `candidate` etiketi; literatür atıfı README'de |
| Config karmaşıklığı | config'siz çalışma korunur; varsayılanlar makul |
| Deney maliyeti/oran limiti | önbellek, bütçe, günlere yayma, model adları belgeli |
| Kapsam şişmesi (`apply` cazibesi) | v3 dokümanı yazılmadan başlanmaz |

## 12. Asistan/geliştirici için devam talimatı
Uygulama Aşama 0'dan başlar. Sıra: fikstür + envanter → config/bütçe/önbellek → grafik → beyanlı ihlal → çıkarım → kokular → scan → advise/verify → deney. Her aşamada önce altın değer + test, sonra implementasyon. Şema değişiklikleri `04`'e işlenir.
