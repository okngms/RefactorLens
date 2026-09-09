# RefactorLens v2 — Kalan Kapsam ve Şekillendirme
### `okngms/RefactorLens` main @ 2026-09-02 durumuna göre

> Bu doküman `01-v2-katman-farkinda-yorumlama.md`'nin yerine geçmez; onu **repo'nun gerçek durumuna** ve literatür sentezinin sonuçlarına göre günceller. Çelişen yerde bu doküman geçerlidir. `docs/SPEC-duzeltme-2.5.md` ve `docs/v2-duzeltme-asama5.md` aynen geçerlidir.

---

## 1. Mevcut durum (repo'dan ölçüldü)

| Aşama (01 §10) | Durum | Kanıt |
|---|---|---|
| **0 — Fikstür ve altyapı** | **Bitti** | `examples/layered_project` (4 katman, 6 ihlal, 3 koku, `ARCH_SMELLS.md` envanteri, davranış testleri); `config.py`'da `arch/smells/budget/cache/by_layer` şeması; `llm/budget.py`, `llm/cache.py` advise akışına bağlı |
| **1 — Bağımlılık grafiği ve beyanlı `arch`** | **Analiz katmanı bitti, CLI yok** | `analysis/imports.py` (weak import dahil), `analysis/graph.py` (SCC, condensation depth, Ca/Ce/instability), `analysis/architecture.py` (beyanlı atama, LV-DIR/SKIP/CYCLE/LEAK, `tentative` alanı hazır). **Eksik:** `rlens arch` komutu, `arch-*.json` raporu, import-linter okuma |
| 2 — Katman çıkarımı | Yapılmadı | `INFERRED`/`UNKNOWN` sabitleri ve güven alanı var; algoritma yok |
| 3 — Koku etiketleri, `scan` entegrasyonu | Yapılmadı | `SmellsConfig` var; `smells.py`, `interface.py` yok; `scan` mimariyi çağırmıyor |
| 4 — Katman-farkında `advise`, korumalı `verify` | Yapılmadı | `advise/context.py` mimari bloğu üretmiyor; `verify` ihlal/arayüz deltası bilmiyor |
| 5 — Deney ve FINDINGS-2 | Yapılmadı | 5a/5b tasarımı `docs/v2-duzeltme-asama5.md`'de kilitli |

670 test, ruff temiz, v1.0.0 PyPI'da. Kod tabanı ~5.000 satır.

---

## 2. Literatür sentezinden gelen kararlar (v2'ye işlenir)

| # | Karar | Nereye |
|---|---|---|
| K1 | **Yenilik iddiası değişir.** v2 "katmana göre eşik" yeniliği iddia etmez; SATT (Aniche 2016), Dósea (2018), Ernst (2018) doğrudan öncül olarak alıntılanır. v2'nin sorusu: *"rol/katman etkisi (SATT) ve mimari bağlam etkisi (Canedo 2026) LLM'in refactoring akıl yürütmesine ve **kendi metrik tahminine** taşınıyor mu?"* | FINDINGS-2 çerçevesi, README "Why" bölümü |
| K2 | **Kalibrasyon v3'ten v2'ye çekilir.** `expected_effect` girdilerine `confidence ∈ [0,1]` eklenir (yapı korunur — invariant bozulmaz); `verify` Brier ve ECE hesaplar (Spiess et al. ICSE'25 metodolojisi). Projenin ana iddiası öz-tahmin; kalibrasyonu bir sürüm erken ölçmek ucuz ve kritik | Aşama 4 |
| K3 | **İhlal kodları literatür adlarıyla eşlenir.** Kodlar kalır, rapora `alias` alanı gelir: `LV-DIR`=back-call, `LV-SKIP`=skip-call, `LV-CYCLE`=cyclic, `LV-LEAK`=leak (Sarkar et al.; Pruijt/HUSACCT). Arcan'ın cyclic/unstable/hub-like kokularıyla ilişki README'de belirtilir | Aşama 3 (rapor), README |
| K4 | **Boyut karıştırıcısı kaydedilir.** Her hedef için LOC/NOM baseline'ı deney verisine yazılır (Gnoyke 2021). v2'de 3 hedefle istatistik yapılmaz; alan v3 için şimdiden tutulur | Aşama 5 veri şeması |
| K5 | **Çıkarım (Aşama 2) v2.0'dan v2.1'e alınır.** Gerekçe: 5a/5b deneyi beyanlı fikstürde koşar, çıkarım gerektirmez; sentez raporuna göre rol çıkarımı doğruluğu ≥%80 olmadan katman bulguları savunulamaz — bu doğrulama tek başına bir iş paketi. v2.0 "beyan + import-linter" ile gerçek projelerde de kullanılabilir (import-linter kullanan projeler katmanlarını zaten yazmıştır) | Sıralama §4 |
| K6 | **Python'a özgü çok düzeyli kalite modeli v2 kapsamı değildir.** Tohumu v2'de atılır (modül düzeyi Ca/Ce/instability `scan` çıktısına girer — zaten `graph.py`'de hesaplanıyor); modelin tanımı ve doğrulaması ayrı doküman (`05-python-kalite-modeli.md`) ve v3 araştırma çerçevesidir | Aşama 3 (modül tablosu), FUTURE |

---

## 3. Kalan kapsam — aşama aşama

### Aşama 1b — `rlens arch` komutu ve rapor (Aşama 1'in tamamlanması)
- `cli.py`: `arch` komutu; `--no-report`, `--fail-on-violation` (yalnız `blocking()` ihlaller, `tentative` hariç).
- `report/terminal.py`: katman tablosu (modül, katman, kaynak, güven), ihlal tablosu (kod, alias, from→to, katmanlar, tentative), modül metrik tablosu (Ca, Ce, I).
- `report/files.py`: `arch-<ts>.json` (`schema_version` ayrı sayaç; `04 §7` şeması + `alias`).
- `integrations/importlinter.py` (yeni): `pyproject.toml [tool.importlinter]` / `.importlinter` içindeki `layers` sözleşmesini `arch.layers` beyanına çevirir; `rlens.yaml`'da beyan varsa o kazanır.
- **Bitti ⇔** `rlens arch examples/layered_project` `ARCH_SMELLS.md`'deki 6 ihlali kodlarıyla basar, fazlasını basmaz (altın test); import-linter'lı gerçek bir açık kaynak projede (örn. import-linter'ın kendi örnekleri ya da `layers` sözleşmesi kullanan bir proje) çökmeden çalışır ve beyanı okuduğunu raporlar.

### Aşama 3 — Kokular, public arayüz, `scan` entegrasyonu
- `analysis/smells.py`: `god_class`, `data_class`, `feature_envy_candidate`, `long_method`, `too_many_params`, `layer_misfit` (kurallar `01 §3`; `SmellsConfig` zaten var). Her etiket `evidence` ile.
- `analysis/interface.py`: sınıf public arayüz kümesi (dunder hariç, `_`-siz metot+attribute); `ClassReport.public_interface`.
- `scanner.py`: `arch.enabled` ise `analyse()` çağrılır; sınıflara `layer`, `layer_confidence`; `by_layer` eşik uygulaması (`Config` zaten çözüyor); `--no-arch` ile v1 davranışı.
- `report/terminal.py`: `Layer` ve `Smells` sütunları; ihlal özeti satırı; modül tablosu (Ca/Ce/I).
- `model.py`: scan `SCHEMA_VERSION` → 2; `verify` v1↔v2 raporlarını reddeder (mevcut kural).
- **Bitti ⇔** fikstürdeki 3 koku altın değerle eşleşir; `Customer` `data_class` etiketiyle basılır ve terminal footnote'u LCOM4'ü bu bağlamda açıklar; aynı sınıf `by_layer` eşiğiyle farklı işaretlenir (test); `--no-arch` çıktısı v1 ile bit-bit aynı (snapshot test).

### Aşama 4 — Katman-farkında `advise`, kalibrasyonlu ve korumalı `verify`
**advise**
- `advise/context.py`: "Architectural context" bloğu (`01 §5` şablonu): hedef katmanı+kaynak+güven, izin matrisi, hedefle ilgili açık ihlaller (alias'la), koku etiketleri. `--no-arch-context` bloğu düşürür (5a A/B).
- `--metric-rules`: `04 §2` hesaplama kurallarının kısa biçimi (5b A/B). **Raw eşik sayıları yine girmez** (invariant).
- `advise/prompts.py`: çıktı şemasına `target_layer_after`, `constraints_respected`, `addresses_smells`; `expected_effect[i].confidence` (**K2**). Eksik `confidence` → `null`, öneri düşmez.
- `advise/advisor.py`: kısıt doğrulaması araç tarafında bağımsız yapılır (öneri metnindeki "move to X layer" beyanı izin matrisine karşı); ihlal → `status: rejected` (silinmez; `unlinked` mantığı). Beyan/araç uyuşmazlığı ayrı sayılır (5a ölçütü).

**verify**
- `verify/diff.py`: ihlal deltaları (`opened/closed`), koku deltaları (`added/removed`), public arayüz deltası.
- Goodhart koruması: hedefin public kümesi küçüldü **ve** kaybolan üyeler başka sınıfa taşınmadıysa → `outcome: suspicious`; `--fail-on-regression` yakalar (`verify.treat_suspicious_as_regression`, varsayılan true).
- `verify/prediction.py`: `confidence` varsa Brier = mean((c − o)²), ECE (5 kova), kova başına doğruluk; rapora `calibration{brier, ece, buckets[]}` (**K2**). Doğrulanamayan tahminler kalibrasyona da girmez.
- **Bitti ⇔** `--dry-run` bağlam bloğunu gösterir; kısıt ihlal eden sahte öneri `rejected` (test); public üye silen sahte diff `suspicious` (test — v1'deki `OrderManager` arayüz-silme vakası regresyon testine dönüştürülür); Brier/ECE altın değerle test edilir.

### Aşama 5 — Deney ve FINDINGS-2 (`docs/v2-duzeltme-asama5.md` aynen)
- **5a** öneri düzeyi: 2×2 × 3 model × 3 hedef × n=3 = 108 çalıştırma; ölçütler oradaki tablo **+** `confidence` dağılımı ve beyan/araç kısıt uyuşmazlığı.
- **5b** uygulanmış: `metric-rules` açık/kapalı × 3 model × 2 hedef × n=1 = 12 vaka; ölçüt tahmin doğruluğu (metrik başına önce, Sınıf A/B sonra) **+** Brier/ECE.
- Veri şemasına her hedef için `baseline_size {loc, nom}` (**K4**).
- FINDINGS-2 literatür bölümü (**K1**): SATT/Dósea/Ernst (rol etkisi), Canedo 2026 ve arXiv 2512.04273 (mimari bağlam→LLM), Spiess ICSE'25 (kalibrasyon), Cordeiro TOSEM 2025 ve DataRef EMSE 2026 (davranış-metrik ayrışması), Gnoyke 2021 (boyut), SpecBench (proxy/gerçek hedef).
- **Bitti ⇔** `experiments/v2/` ham veri; `analysis-advice-v2.md`, `analysis-verify-v2.md`; `FINDINGS-2.md`; Limitations'ta n=1, koşul başına ~13, tek fikstür, çıkarımın v2.1'e ertelendiği.

### Aşama 2 → **v2.1** — Katman çıkarımı (ertelendi, **K5**)
- Konvansiyon + framework + yön → katman + güven (`01 §2.2`); `unknown`; `evidence`.
- **Bitti ⇔** fikstürde beyan kaldırılınca ≥0.7 güven; `shared/` `unknown`; **3 gerçek projede elle inceleme, doğruluk ≥%80** — altında kalırsa çıkarım "weak signal" olarak işaretlenir ve `tentative` eşiği yükseltilir. Bu kriter sentez raporundan gelir ve pazarlık konusu değildir.

---

## 4. Sıralama ve gerekçe

```
1b (arch CLI + import-linter)  →  3 (kokular, scan)  →  4 (advise/verify + kalibrasyon)
        →  5a (108 çalıştırma, günlere yayılır)  →  5b (12 vaka)  →  FINDINGS-2  →  v2.0.0
        →  [v2.1] 2 (çıkarım)
```
- 1b önce: `arch`'ın CLI'dan görünmesi hem deneyin hem README'nin önkoşulu; kod hazır, iş küçük.
- 3 ve 4 deneyin araçları; 5a API çağrısı ağırlıklı olduğu için 4 biter bitmez başlatılıp arka planda koşabilir, 5b elle iş.
- 2 en sona: deney için gereksiz, doğrulaması pahalı, yenilik değeri düşük (SATT). v2.0 çıkarımsız çıkar; README bunu açıkça yazar ("layers are declared or read from import-linter; inference is v2.1").

**Zaman tahmini (yan zamanlı):** 1b ~1 oturum; 3 ~2; 4 ~3; 5a kurulum 1 + koşu günlere yayılı; 5b ~2 (elle refactoring 12 vaka); FINDINGS-2 ~2. v2.0.0 için toplam ~11-12 çalışma oturumu.

---

## 5. v2.0.0 yayın kontrol listesi
- [ ] README: `<user>` placeholder → `okngms`; PyPI'da kırılan göreli linkler (FINDINGS/FUTURE/STRUCTURE/SMELLS) → mutlak GitHub URL'leri
- [ ] README "Why": K1 çerçevesi; "Metric definitions": ihlal alias tablosu ve Arcan ilişkisi; "Roadmap": v2 satırları, çıkarımın v2.1 olduğu
- [ ] AGENTS.md: kilitli kararlara ekle — "çıkarım beyanı asla ezmez", "confidence opsiyonel, yokluğu öneriyi düşürmez", "suspicious davranış kapısını ikame etmez"
- [ ] STRUCTURE.md: yeni dosyalar (`smells.py`, `interface.py`, `integrations/importlinter.py`, `verify/calibration` alanları)
- [ ] FUTURE.md: "Modül/paket düzeyi coupling" maddesi çıkar (yapıldı); "Python'a özgü çok düzeyli kalite modeli" maddesi girer (K6)
- [ ] `schema_version`: scan 2, arch 1, advice 2, verify 2; `04` güncellenir
- [ ] Trusted Publishing (GitHub Actions → PyPI)
- [ ] `experiments/v2/` ham veri commit'li; FINDINGS-2 README'den linkli

## 6. v2'ye girmeyenler (yeniden teyit)
`apply`/`loop`, tip çıkarımı, GitHub Action, SARIF/HTML, `history`, LensBench, C#, Python-özgü kalite modelinin tanımı/doğrulaması (v3 çerçevesi), Gemini/Anthropic adapter'ları (opsiyonel, ~30 satır — isteyen ekler, sürüm hedefi değil).
