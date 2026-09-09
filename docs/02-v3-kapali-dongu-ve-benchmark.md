# RefactorLens v3 — Kapalı Döngü ve LensBench

> **Önkoşul:** v2.0.0 yayında; FINDINGS-2 tamamlanmış. `00` ve `04` okunmuş.
> **Tez:** v1-v2'de döngü elle kapanıyordu; bu, deney ölçeğini sınırlıyor ve aracın günlük kullanımını engelliyor. v3 döngüyü güvenli biçimde otomatik kapatır (`apply`), modele kendi hatasını geri besler ve ortaya çıkan veriyi tekrarlanabilir bir benchmark'a (**LensBench**) dönüştürür. Sonuç: RefactorLens "analizör"den "denetimli refactoring ajanı + ölçüm standardı"na geçer.

---

## 1. Kapsam (kilitli)

### 1.1 Yeni komutlar
| Komut | Ne yapar |
|---|---|
| `rlens apply <path>` | Seçili öneri için modelden **patch** ister, izole git worktree'de uygular, davranış kapısını koşar, geçerse `verify` eder; sonuç branch olarak bırakılır. Çalışma ağacına dokunmaz. |
| `rlens loop <path>` | `advise → apply → verify → geri besleme → advise` döngüsünü `--max-iter` (vars. 3) kadar koşar; her iterasyon kaydedilir. |
| `rlens diff <base>..<head>` | İki git ref'i arasında metrik/ihlal/koku deltası; PR yorumu için markdown çıktı; ratchet modu. |
| `rlens bench run/report` | LensBench prosedürünü koşar ve sonuç tablosunu üretir. |
| `rlens chartests <path>` | Testsiz hedefler için **karakterizasyon testi** üretir (LLM), mevcut davranışı sabitler; davranış kapısı için önkoşul. |

### 1.2 Değişen komutlar
| Komut | v3 eklemesi |
|---|---|
| `advise` | Öneri şemasına `confidence` (0-1) ve `expected_refactoring_type` alanları; ensemble modu (`--providers a,b,c` → uyuşma raporu); tip çıkarımı opsiyonel (`[typed]` extra) |
| `verify` | Refactoring türü tespiti (AST diff), kalibrasyon puanı, davranış kapısı sonucu |

### 1.3 Yeni yatay özellikler
- **Davranış kapısı 2.0:** kullanıcı test komutu + karakterizasyon testleri + opsiyonel property-based eşdeğerlik kontrolü.
- **Refactoring türü tespiti:** Extract Method, Move Method, Extract Class, Inline, Rename (AST/imza diff ile).
- **Kalibrasyon:** model güven beyanı vs gerçekleşen doğruluk; Brier skoru ve güvenilirlik diyagramı verisi.
- **Tip çıkarımı (opsiyonel):** `pip install refactorlens[typed]` → jedi/pyright ile DCC/CAM kesinleşir; rapor `resolution: inferred|typed` belirtir.
- **GitHub Action:** `rlens diff` + PR yorumu + ratchet.

### 1.4 Kapsam dışı
Otomatik merge, insansız uygulama, IDE, web UI, git geçmişi trendi, hotspot, ek dil → `03` / FUTURE.

---

## 2. `apply` — güvenlik invariant'ları (ihlal edilemez)
1. **Yalnızca git repo'da çalışır;** temiz olmayan çalışma ağacında reddeder (`--allow-dirty` yok).
2. Her uygulama **ayrı worktree** (`.rlens-work/<run-id>/`) ve **ayrı branch** (`rlens/<run-id>/<target>`). Kullanıcının branch'ine/çalışma ağacına asla yazmaz.
3. Patch **unified diff** olarak istenir; şemaya uymayan/çakışan patch reddedilir, model tek kez onarım şansı alır.
4. Patch yalnızca hedef sınıfın dosyası + `--allow-files` ile açıkça izin verilen dosyalara dokunabilir; başka dosya değişikliği reddedilir.
5. Davranış kapısı geçmezse worktree silinir, branch bırakılmaz (`--keep-failed` ile inceleme için tutulabilir).
6. Testler kullanıcının komutuyla (`tests.command`) ve **zaman/kaynak limitiyle** (`tests.timeout`) subprocess'te koşar; RefactorLens hedef kodu kendisi çalıştırmaz, kullanıcının test komutunu çalıştırır. README'de açık uyarı: bu, v1-v2'nin "kod çalıştırmaz" garantisinden bilinçli bir sapmadır ve yalnızca `apply/loop/chartests` için geçerlidir.
7. Sonuç raporu: patch, test çıktısı özeti, verify sonucu, Goodhart durumu, maliyet. Kullanıcı branch'i inceler ve merge eder — **araç asla merge etmez.**

## 3. Davranış kapısı 2.0
- **Seviye 1:** `tests.command` (örn. `pytest -q`) — zorunlu.
- **Seviye 2:** `chartests` — hedef sınıfın public metotları için LLM'e karakterizasyon testleri yazdırılır (girdi → gözlenen çıktı). Testler **refactoring'den önce** üretilir ve mevcut kodda geçmek zorundadır; geçmeyenler atılır. Testsiz projelerde `apply` bu seviyeyi zorunlu tutar. Bu, EMSE 2026'da raporlanan yüksek davranışsal tutarsızlık oranına karşı savunmadır.
- **Seviye 3 (opsiyonel):** `hypothesis` ile öncesi/sonrası fonksiyon eşdeğerlik testi (`[equiv]` extra); yalnızca saf fonksiyonlar için.
- Kapı sonucu rapora `behavior_gate: {level, passed, details}` olarak yazılır; kapı geçmeden hiçbir delta `improved` olamaz.

## 4. Geri besleme döngüsü (`loop`)
Her iterasyonda modele verilen ek blok:
```
## Feedback from previous attempt
Prediction LCOM4: down — actual: same (✗). Prediction DCC: up — actual: down (✗).
Behavior gate: passed. Public interface: unchanged.
Explain why the structural predictions missed, then propose a revised change.
```
Ölçülen: iterasyon başına tahmin doğruluğu, kapı geçme oranı, `suspicious` oranı, maliyet. Durma koşulları: tüm tahminler doğru **ve** kapı geçti; ya da `--max-iter`; ya da bütçe.

## 5. Refactoring türü tespiti
AST ve imza diff'inden kural tabanlı sınıflandırma (RefactoringMiner'ın Python için hafif karşılığı):
| Tür | Sinyal |
|---|---|
| Extract Method | yeni fonksiyon/metot + kaynak metotta çağrı + kaynak LOC düşüşü |
| Move Method | metot bir sınıftan kayboldu, başka sınıfta benzer gövdeyle belirdi |
| Extract Class | yeni sınıf + attribute/metot alt kümesinin taşınması |
| Inline | fonksiyon kayboldu, gövdesi çağrı yerine yerleşti |
| Rename | aynı gövde, farklı ad |
| Unknown | eşleşme yok |
Her tespit `confidence` ile; deney ve benchmark raporları **tür bazında** kırılım verir (SWE-Refactor/TOSEM ile karşılaştırılabilirlik).

## 6. Kalibrasyon
- Öneri şemasında her tahmin için `confidence ∈ [0,1]` zorunlu.
- `verify`: doğrulanabilir tahminler için Brier = mean((confidence − outcome)²); güvenilirlik kovaları (0-0.2, …, 0.8-1) ve kova başına gerçek doğruluk.
- Rapor: model başına Brier, aşırı/yetersiz güven yönü. Bu, "self-prediction" açısını benchmark boyutuna çevirir.

## 7. LensBench
**Ne ölçer (refactoring başarısı değil):**
1. Metrik tahmin doğruluğu (aritmetik / yapısal ayrı).
2. Kalibrasyon (Brier).
3. Kısıt uyumu (`rejected` oranı) — katman bağlamlı koşulda.
4. Metrik oyunlama oranı (`suspicious`) ve davranış kapısı geçme oranı.
5. Tür bazında kırılım.

**Prosedür:** sabit hedef seti (`layered_project` + `messy_project` + seçilmiş açık kaynak Python projelerinin dondurulmuş commit'leri; katman beyanları paketle gelir), sabit prompt sürümü (hash'li), sabit koşullar (arch-context on/off, metric-rules on/off, loop 1/3 iter), her hedef için ≥3 tekrar (sıcaklık/tohum belgeli). `rlens bench run --suite lensbench-v1 --provider ...` → `bench/results/<model>/<date>.json`; `rlens bench report` → markdown tablo.

**Yayın:** `bench/` dizini repo'da; sonuç tablosu README'de; katkı kılavuzu (yeni model sonucu PR ile eklenir; prompt/hedef seti sürümü eşleşmeli). İsim **LensBench** (RefactorBench adı mevcut bir benchmark'a ait).

## 8. GitHub Action ve ratchet
- `rlens diff origin/main..HEAD --format=pr-comment` → sınıf bazlı delta, yeni/kapanan ihlaller, koku deltaları, `suspicious` uyarısı.
- **Ratchet:** baseline dosyası (`.rlens-baseline.json`) mevcut ihlalleri kabul eder; yalnızca **yeni** ihlal/regresyon CI'ı kırar. `rlens baseline update` ile güncellenir.
- Action girdileri: `path`, `fail-on: regression|new-violation|none`, `comment: true|false`. LLM gerektirmez (`diff` lokal).

## 9. Config eklemeleri
```yaml
tests:
  command: "pytest -q"
  timeout: 300
apply:
  allow_files: []            # hedef dosya dışında izin verilenler
  keep_failed: false
loop:
  max_iter: 3
chartests:
  enabled_when_no_tests: true
  per_method_cases: 3
bench:
  suite: lensbench-v1
  repeats: 3
```

## 10. Depo değişiklikleri
```
src/rlens/
├── apply/{worktree.py, patch.py, gate.py, runner.py}
├── loop/feedback.py
├── chartests/generator.py
├── analysis/{refactoring_types.py, typed_resolution.py}
├── verify/calibration.py
├── diff/{git_refs.py, pr_comment.py, baseline.py}
└── bench/{suite.py, runner.py, report.py}
bench/                        # hedef seti, prompt sürümleri, sonuçlar
action/                       # GitHub Action (action.yml, entrypoint)
```

---

## 11. Aşama planı ve kabul kriterleri

### Aşama 0 — Davranış kapısı ve worktree altyapısı
Kapı seviye 1, worktree/branch yönetimi, patch doğrulama (dosya kısıtı, çakışma), invariant testleri.
**Bitti ⇔** sahte bir patch worktree'de uygulanıp test koşuluyor; kirli ağaç reddediliyor; izinsiz dosya değişikliği reddediliyor; hiçbir testte kullanıcı branch'i değişmiyor (invariant testleri).

### Aşama 1 — `apply`
Patch prompt şeması, onarım denemesi, kapı entegrasyonu, verify çağrısı, rapor.
**Bitti ⇔** `layered_project`'te bir öneri uçtan uca uygulanıp `improved|regressed|mixed|suspicious` sonucu alınıyor; kapı geçmeyen vaka temizleniyor.

### Aşama 2 — `chartests` ve kapı 2.0
Karakterizasyon üretimi, ön-doğrulama (mevcut kodda geçmeli), seviye 3 opsiyonu.
**Bitti ⇔** testsiz bir fikstürde (`examples/untested_project`) `apply` kapı 2 ile çalışıyor; üretilen testlerin mevcut kodda geçme oranı raporlanıyor.

### Aşama 3 — `loop` ve kalibrasyon
Geri besleme bloğu, durma koşulları, `confidence` alanı, Brier hesabı.
**Bitti ⇔** 3 iterasyonluk koşu kaydediliyor; iterasyon başına metrikler raporda; Brier altın değerle test ediliyor.

### Aşama 4 — Refactoring türü tespiti ve tip çıkarımı
`refactoring_types.py` (fikstürde bilinen refactoring'lerle altın test); `[typed]` extra ile DCC/CAM `typed` çözümleme, `inferred` ile karşılaştırma raporu.
**Bitti ⇔** 5 tür fikstürde doğru sınıflandırılıyor; typed modda CAM `null` oranı düşüyor (ölçülüp belgeleniyor).

### Aşama 5 — `diff`, baseline, GitHub Action
**Bitti ⇔** örnek PR'da yorum üretiliyor; ratchet mevcut ihlalleri geçirip yeni ihlali kırıyor (test); Action marketplace'te yayınlandı.

### Aşama 6 — LensBench ve FINDINGS-3
Hedef seti dondurma, prosedür, `bench run/report`, en az 4 model (≥3 ücretsiz/lokal + 1 pahalı kontrol), tüm koşullar.
**H1:** Geri besleme yapısal tahmin doğruluğunu iterasyonlar boyunca artırır.
**H2:** Karakterizasyon testleri davranış tutarsızlığı yakalama oranını artırır (kapı 1 vs kapı 2).
**H3:** Modeller aşırı güvenlidir (Brier ve kova analizi); büyüklükle kalibrasyon değişir mi?
**H4:** Tür bazında tahmin doğruluğu farklıdır (Extract Method vs Move Method).
**Bitti ⇔** `FINDINGS-3.md` + benchmark tablosu README'de; ham veri `experiments/v3/`; **v3.0.0** PyPI'da; literatür bağı (SWE-Refactor, EMSE 2026, SpecBench) kurulmuş.

---

## 12. Riskler
| Risk | Savunma |
|---|---|
| `apply` kullanıcı kodunu bozar | invariant'lar §2; worktree/branch izolasyonu; asla merge yok |
| Kod çalıştırma güvenliği | yalnızca kullanıcının kendi test komutu, timeout; README'de açık uyarı |
| Maliyet (loop × bench) | önbellek, bütçe, ücretsiz/lokal varsayılan, pahalı model küçük kontrol |
| Karakterizasyon testlerinin yanlış davranışı sabitlemesi | testler mevcut davranışı belgeler, doğruluk iddia etmez; README'de belirtilir |
| Benchmark'ın çabuk eskimesi | hedef seti ve prompt sürümlü; sonuçlar sürümle etiketli |
| Kapsam şişmesi | `03` yazılmadan v4 özelliği eklenmez |

## 13. Devam talimatı
Sıra: kapı + worktree invariant'ları → `apply` → `chartests` → `loop`/kalibrasyon → tür tespiti/typed → `diff`/Action → LensBench/FINDINGS-3. Şema değişiklikleri `04`'e işlenir; `schema_version: 3`.
