# RefactorLens — Ortak Spesifikasyon (SPEC)

> **Amaç:** Sürümler ve (ileride) diller arasında sabit kalan sözleşmeler. Bir analizör bu şemayı üretiyorsa çekirdek onu kullanabilir; bir FINDINGS bu tanımlara dayanıyorsa başka bir FINDINGS ile karşılaştırılabilir.
> **Kural:** Bu dosya değişirse `schema_version` artar ve eski sürüm raporları okunmaya devam eder (okuyucu tarafı geriye uyumlu).

---

## 1. Sürümleme
- `schema_version`: 1 (v1.0), 2 (v2.0), 3 (v3.0), 4 (v4.0). Her raporun kökünde bulunur.
- Yeni alan eklemek sürüm artırmaz; alan anlamı değiştirmek ya da alan kaldırmak artırır.
- Rapor okuyucu, bilmediği alanları yok sayar; eksik alanları `null` kabul eder.

**v2.0.0'da yayınlanan sürümler:**

| Rapor | Sabit | Sürüm | v2'de değişen |
|---|---|---|---|
| scan | `SCHEMA_VERSION` | 2 | sınıfa `layer`/`smells`/`public_interface`, modüle `ca`/`ce`/`instability`, rapora `violations` |
| arch | `ARCH_SCHEMA_VERSION` | 1 | v2'de doğdu |
| advice | `ADVICE_SCHEMA_VERSION` | 2 | `target_layer`, `addresses_smells`, `confidence`, `status: rejected` |
| verify | `SCHEMA_VERSION` (scan ile ortak) | 2 | gövdesi scan deltalarından oluşur; ayrı sayaç yok |

advice sürümünün artması salt alan eklemekten değil, **tüketim tarafından**
gelir: kalibrasyon `confidence` alanına dayanır, v1 raporlarında bu alan yoktur
ve sürüm etiketi olmadan "güven verilmemiş" ile "eski format" ayırt edilemez.
`experiments/v2/` altındaki ham advise raporları, sürüm artırılmadan önce
toplandıkları için 1 taşır; format v2'nindir, etiket geçmişe dönük düzeltilmez.

## 2. Metrik tanımları

### 2.1 Ortak kural: hangi metotlar sayılır
Sınıf gövdesinde doğrudan tanımlı metotlar; dunder'lar hariç; `@property/@staticmethod/@classmethod` dahil; iç içe fonksiyon/sınıflar hariç; `__init__` hariç (LCOM4 için kritik: kurucu her attribute'a dokunur).

### 2.2 Sınıf düzeyi
| Metrik | Tanım | Değer aralığı | Python uyarlaması | Hesaplanamama koşulu |
|---|---|---|---|---|
| NOM | Sayılan metot adedi | ≥0 | — | — |
| WMC | Sayılan metotların CC toplamı | ≥0 | — | — |
| LCOM4 | Metot–attribute paylaşım grafiğinde bağlı bileşen sayısı | ≥1 (metot yoksa null) | attribute kümesi: sınıf düzeyi atama/annotation, herhangi metotta `self.x = …`, `__slots__` | metot yok |
| DAM | private attribute / tüm attribute | 0-1 | `dam`: `_x` ve `__x`; `dam_strict`: yalnız `__x` | attribute yok |
| DCC | Referans verilen farklı proje-içi sınıf sayısı | ≥0 | isim tabanlı (`resolution: inferred`); tip çıkarımıyla `typed` | — |
| CAM | Metot parametre tiplerinin sınıf-genel tip kümesine oranının ortalaması | 0-1 | yalnız annotation kapsamı ≥ `cam_min_annotation_coverage` | kapsam yetersiz → null, nedeni raporda |
| PUBLIC_IF | Public arayüz kümesi (v2+) | küme | dunder hariç, `_` öneksiz metot ve attribute'lar | — |

### 2.3 Fonksiyon düzeyi
| Metrik | Tanım |
|---|---|
| CC | 1 + `if/elif`, döngüler, `except`, ternary, ek `and/or` operandı, comprehension koşulu, `match` case. `else/with/try` eklemez. İç içe fonksiyon girilmez. |
| LOC | Gövde satır sayısı (boş/yorum hariç) |
| PARAMS | Parametre sayısı (`self/cls` hariç) |
| NESTING | Maksimum blok derinliği; `elif` zinciri düz |

### 2.4 Modül düzeyi (v2+)
| Metrik | Tanım |
|---|---|
| Ca | Bu modülü import eden proje-içi modül sayısı |
| Ce | Bu modülün import ettiği proje-içi modül sayısı |
| I | instability = Ce / (Ca + Ce); Ca+Ce=0 → null |

### 2.5 Metrik sınıfları (deney analizinde kullanılır)
- **Aritmetik:** CC, WMC, PARAMS, LOC, NOM — ölçülen varlık üzerinde sayma/toplama.
- **Yapısal:** LCOM4, DCC, CAM, DAM, Ca/Ce — varlıklar arası ilişki gerektirir.
v1 bulgusu bu ayrıma dayanır; tüm FINDINGS'ler tahmin doğruluğunu bu iki sınıf için ayrı raporlar.

## 3. Eşikler (varsayılan)
`cyclomatic_complexity {warn:10, critical:20}`, `max_params {warn:5}`, `max_nesting {warn:4}`, `lcom4 {warn:2, critical:4}`, `dcc {warn:7}`, `wmc {warn:50}`, `nom {warn:20}`. v2+: `by_layer` geçersiz kılma.

## 4. Koku kuralları (v2+, varsayılan)
`god_class`: NOM≥20 ∧ WMC≥50 ∧ LCOM4≥3. `data_class`: NOM≤5 ∧ WMC≤NOM+2 ∧ DAM≥0.5 ∧ erişimci oranı≥0.7. `feature_envy_candidate` (metot): dış tek sınıfa erişim / kendi erişimi ≥ 2. `long_method`: CC≥warn ∧ LOC≥40. `too_many_params`: PARAMS≥warn. `layer_misfit`: katman güveni ≥0.7 ve katman-koku uyumsuzluğu. Her etiket `evidence` ile.

## 5. Katman konvansiyonları (v2+, varsayılan)
| Katman | Dizin adları | Sınıf sonekleri |
|---|---|---|
| presentation | api, controllers, handlers, views, routers, endpoints | Controller, Handler, View, Router |
| application | services, application, usecases, use_cases, workflows | Service, UseCase, Workflow, Orchestrator |
| domain | domain, models, entities, core, business | Entity, ValueObject, Aggregate, Policy |
| infrastructure | infra, infrastructure, repositories, adapters, db, clients, persistence, gateways | Repository, Client, Gateway, Adapter, Dao |
Varsayılan izin: presentation→{application, domain}; application→{domain}; infrastructure→{domain}; domain→{}.

## 6. Öneri (advice) şeması
```json
{
  "schema_version": 3,
  "target": "orders:OrderManager",
  "target_layer": {"name": "application", "source": "inferred", "confidence": 0.82},
  "diagnosis": "…",
  "suggestions": [{
    "id": 1,
    "title": "Extract repository access into OrderRepository",
    "rationale_metric_link": ["DCC", "LCOM4"],
    "addresses_smells": ["god_class"],
    "expected_refactoring_type": "extract_class",
    "predictions": [
      {"metric": "LCOM4", "direction": "down", "confidence": 0.7},
      {"metric": "DCC", "direction": "same", "confidence": 0.5}
    ],
    "target_layer_after": "application",
    "constraints_respected": true,
    "sketch": "…",
    "status": "linked"
  }],
  "risk_notes": "…"
}
```
- `direction ∈ {up, down, same}`; `confidence` v3+ zorunlu (v2'de opsiyonel).
- `status ∈ {linked, unlinked, rejected}`; hiçbir öneri silinmez, oranlar raporlanır.

## 7. Rapor şemaları (özet)
- **scan:** `{schema_version, project, generated_at, classes: [{qualname, module, layer?, layer_confidence?, metrics{…}, smells[]?, public_interface[]?, violations[]?}], functions: […], modules: [{path, layer?, ca, ce, instability}]?, summary{…}}`
- **arch (v2+):** `{schema_version, scheme, modules[], classes[], graph{edges:[[from,to,weak]]}, violations:[{code, from, to, layers, confidence, tentative}]}`
- **verify:** `{schema_version, before_ref, after_ref, classes:[{qualname, deltas{metric:{before,after,dir}}, outcome}], predictions:[{metric, predicted, actual, correct|unverifiable}], accuracy{arithmetic, structural, overall}, calibration{brier, buckets[]}?, behavior_gate{level, passed}?, interface_delta?, violation_deltas?, smell_deltas?, refactoring_type?}`
- **history (v4):** `{schema_version, points:[{ref, date, summary{…}, classes{…}}], lineage:{…}}`
- Dil eklentileri (v4) `scan` ve `arch` şemasını üretir; `capabilities{metrics[], arch, interface, adaptations{metric: note}}` ekler.

## 8. Prompt sözleşmesi
- Sistem talimatı sabit ve sürümlü (`prompts/advise_vN.txt`), hash'i raporda (`prompt_hash`).
- Kullanıcı bloğu sırası: hedef kod → bağımlı sınıf imzaları → metrik tablosu → eşik ihlalleri → (v2) mimari bağlam + kokular → (v2, opsiyonel) metrik kuralları → (v3, loop) geri besleme → çıktı şeması talimatı.
- Model adı config'ten; koda gömülmez. `--dry-run` tam prompt'u basar.

## 9. Deney kayıt standardı
Her deney koşusu: `experiments/vN/<run-id>/` altında `config.yaml`, `models.json` (ad, sürüm, sağlayıcı, tarih, sıcaklık), `prompt_hash`, ham advise/verify raporları, `analysis.ipynb|.py`, `summary.md`. FINDINGS-N bu dizinlere atıf verir. Bulgular literatür referanslarıyla bağlanır (`00 §3`).

## 10. Sözlük
- **Tahmin (prediction):** Modelin bir metriğin yönü hakkındaki beyanı.
- **Doğrulanabilir tahmin:** Öncesi ve sonrası hesaplanabilen metrik için yapılan tahmin; aksi `unverifiable`, orandan dışlanır.
- **Goodhart / suspicious:** Metrikler iyileşirken public arayüzün gerekçesiz küçülmesi.
- **Davranış kapısı:** Testlerin geçmesi şartı; geçmeden hiçbir delta `improved` olamaz.
- **Tentative:** Düşük güvenli katman atamasından türeyen, CI'ı kırmayan ihlal.
