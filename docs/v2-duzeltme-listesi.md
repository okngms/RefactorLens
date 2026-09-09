# v2 Düzeltme Listesi — Sonraki Aşamaların Çözmeyeceği Sapmalar
### `okngms/RefactorLens` main @ commit `0619145` (2026-09-05) incelemesine göre

> **Kime:** Geliştirmeyi sürdüren asistan. Bu dosya `v2-kalan-kapsam.md`'ye ektir ve **Aşama 5a'dan önce** uygulanır.
> **Neden var:** Aşama 1b–4 kodu spesifikasyona büyük ölçüde sadık; ancak altı noktada spesifikasyondaki bir cümle uygulanırken düşmüş. Bunlar planlı aşamalarda yoktur ve v3/v4 tarafından kendiliğinden düzelmez — ikisi tersine v3 `apply`'ı bozar. Her madde: **ne**, **nerede**, **neden önemli**, **düzeltme**, **test**, **kabul**.
> **Öncelik:** D1 ve D2 zorunlu (tez cümlelerine dokunuyor). D3 belgeleme. D4–D6 yayın öncesi cila.
>
> Kilitli ilkeler değişmiyor: hedef kod çalıştırılmaz, `—`≠0, ham eşik modele gitmez, hiçbir öneri silinmez, davranış kapısı yerine hiçbir şey geçmez.

---

## D1 — Goodhart koruması "taşınma" kontrolünü atlıyor (ZORUNLU)

**Ne:** `src/rlens/verify/goodhart.py::SuspicionCheck.is_suspicious` yalnızca `metrics_improved and net_loss > 0` bakıyor. `net_loss = len(removed) − len(added)` hedef sınıfın **kendi** arayüzüyle sınırlı; kaybolan üyelerin projede başka bir sınıfta (özellikle `verify`'ın `added` olarak raporladığı yeni sınıflarda) yeniden ortaya çıkıp çıkmadığına bakılmıyor.

**Neden önemli:** Spesifikasyon (`01 §6`, `v2-kalan-kapsam §3 Aşama 4`) açıkça "kaybolan üyeler projede başka sınıfa **taşınmadıysa**" diyordu. Mevcut hâliyle god class'tan `AuditLog` çıkaran meşru bir Extract Class, hedefte net −N ürettiği için `suspicious` olur; `verify.treat_suspicious_as_regression` varsayılan `true` olduğundan `--fail-on-regression` kırılır. Araç, tam olarak önerdiği refactoring türünü cezalandırıyor. v1'in iki vakası bu ayrımın turnusolu: arayüz-silme vakasında üyeler **yok oldu**, audit-extraction vakasında üyeler **taşındı**. v3 `apply` otomatik uygulamada her Extract Class'ı reddedeceği için sorun büyür, küçülmez.

**Düzeltme:**
1. `check_entity(delta, before, after)` imzasına `after_project: dict` (after scan raporunun tamamı) ekle. `SuspicionCheck`'e `moved: tuple[tuple[str, str], ...]` alanı ekle: `(üye_adı, hedef_sınıf_qualname)`.
2. Kaybolan her üye için after raporundaki **diğer** sınıfların `public_interface.methods ∪ attributes` kümelerinde aynı ad aranır. Öncelik: `delta` raporunda `added` statüsündeki sınıflar; sonra hedefle aynı modüldeki sınıflar; sonra tüm proje. İlk eşleşme `moved` sayılır. (Arite karşılaştırması `public_interface`'te parametre bilgisi olmadığı için yapılamaz; bu sınırlılık docstring'e yazılır ve v3'te AST diff ile kesinleştirilir.)
3. `deleted = removed − {m for m, _ in moved}`; `is_suspicious = metrics_improved and (len(deleted) − len(added)) > 0`.
4. `reason` metni taşınan ve silinenleri ayrı sayar: `"metrics improved while 3 public member(s) were deleted (x, y, z); 5 moved to orders.AuditLog"`.
5. `to_dict`'e `moved`, `deleted`, `net_deleted` alanları; `04 §7` verify şeması güncellenir (alan ekleme, `schema_version` artmaz).
6. Terminal ve markdown raporu (`report/verify.py`) taşınanları "moved to X" olarak gösterir; yalnız silinenler `suspicious` gerekçesinde yer alır.

**Test (`tests/test_goodhart.py`):**
- `test_extract_class_moving_members_is_not_suspicious`: before'da `A{f,g,h}`, after'da `A{f}` + yeni `B{g,h}`; metrikler iyileşmiş → `is_suspicious is False`, `moved == (("g","…:B"),("h","…:B"))`.
- `test_deleting_members_stays_suspicious`: v1'in arayüz-silme vakası (`experiments/cases/*__god_OrderManager` içindeki `applied.diff`'lerden silen olanı) → `is_suspicious is True`.
- `test_mixed_move_and_delete`: 2 taşındı, 3 silindi → `suspicious`, `deleted` 3 üye.
- `test_rename_is_neutral` mevcut davranışı korur (added ile dengelenir).
- CLI: `tests/test_cli.py`'de layered fikstürde elle yapılmış bir Extract Class diff'iyle `verify --fail-on-regression` **exit 0**.

**Kabul:** Dört test yeşil; `examples/messy_project` audit-extraction senaryosu `improved`, arayüz-silme senaryosu `suspicious`.

---

## D2 — Ham eşik sayıları koku kanıtı yoluyla prompt'a sızıyor (ZORUNLU)

**Ne:** `src/rlens/advise/prompts.py::format_architecture` koku `evidence`'ındaki dict/list değerleri filtreliyor. `god_class`, `feature_envy_candidate`, `long_method` eşikleri iç içe `thresholds` dict'inde olduğu için temiz kalıyor. Ama `smells.py`'de `layer_misfit` eşiği `dcc_threshold: 4`, `too_many_params` eşiği `threshold: 5` **düz skaler** alan olarak yazılıyor → bloğa giriyor. Doğrulandı: çıktı `layer_misfit (layer=domain, dcc=9, dcc_threshold=4, …)` ve `too_many_params (params=7, threshold=5)`.

**Neden önemli:** AGENTS.md'nin kilitli invariant'ı: *"Raw threshold numbers never reach the model."* Modelin sayıyı bilmesi, tasarımı düzeltmek yerine sayıyı tatmin etmeyi öğrenmesi demektir — projenin ortaya çıkarmak istediği Goodhart tuzağının ta kendisi. Mevcut `tests/test_prompts.py::TestNoRawThresholds` yalnızca ölçüm bloğunu ve `"{key}: {warn}"` desenini test ettiği için yakalamadı. 5a hedeflerinde (OrderService, Customer, ReportView) bu iki etiket çıkmadığından deney verisi etkilenmiyor; ama kullanıcıya açık bir sızıntı.

**Düzeltme (iki katman, ikisi de yapılır):**
1. **Kaynakta tutarlılık:** `smells.py`'de tüm eşikler tek bir iç içe `thresholds: {...}` sözlüğünde tutulur. `detect_layer_misfit` → `evidence={"layer", "dcc", "module_has_violation", "thresholds": {"dcc": ...}}`; `detect_function_smells`'in `too_many_params`'ı → `"thresholds": {"params": ...}`.
2. **Çıkışta beyaz liste:** `format_architecture` "dict/list olmayanı bas" yerine **yalnızca bilinen ölçüm anahtarlarını** basar (`nom, wmc, lcom4, dam, dcc, cc, loc, params, envied, accesses_to_other, accesses_to_self, ratio, accessor_ratio, layer`). `threshold` kelimesini içeren hiçbir anahtar basılmaz. Kara liste değil beyaz liste: yeni bir koku eklendiğinde varsayılan **sızdırmamak** olmalı.

**Test:**
- `tests/test_prompts.py::TestNoRawThresholds` genişletilir: `build_user_prompt` çıktısının **tamamı** (evidence + architecture + metric rules) üzerinde, config'teki her eşik değeri için `re.search(rf"\b{value}\b")` yerine daha güvenli olarak `"threshold" not in prompt.lower()` **ve** her `(key, warn/critical)` çifti için `f"{key}={warn}"`, `f"{key}_threshold"`, `f"threshold={warn}"` desenlerinin yokluğu.
- `layer_misfit` ve `too_many_params` üreten sentetik bir hedefle `format_architecture` çıktısında `"threshold"` geçmez.
- `tests/test_smells.py`: her koku için `evidence` içinde eşiğin **yalnızca** `thresholds` altında olduğu (`assert not any("threshold" in k for k in evidence if k != "thresholds")`).

**Kabul:** Üç test yeşil; `rlens advise --dry-run` çıktısında hiçbir hedefte `threshold` kelimesi geçmiyor (grep ile doğrulanır).

---

## D3 — Kısıt denetimi spesifikasyondan dar (BELGELEME)

**Ne:** `src/rlens/advise/advisor.py::validate_constraints` yalnızca (a) `target_layer_after`'ın şemada var olan bir katman adı olup olmadığına ve (b) modelin kendi `constraints_respected: false` beyanına bakıyor. Hedef katmandan `target_layer_after`'a taşımanın izin matrisine uyup uymadığı, ya da taslakta bir yasak import ima edilip edilmediği denetlenmiyor. Docstring bunu bilinçli ("taslak metninden import çıkarmak güvenilir değil") diye gerekçelendiriyor — gerekçe geçerli.

**Neden önemli:** `v2-kalan-kapsam §3 Aşama 4` matris kontrolü istiyordu; yapılmadı. Bu bir hata değil, **daraltma**; ama FINDINGS-2'de `rejected` oranı "kısıt uyumu" diye sunulursa yanıltır: ölçülen şey aslında "geçersiz katman adı + modelin kendi itirafı"dır.

**Düzeltme (kod değil, tanım):**
1. `docs/v2-duzeltme-asama5.md` 5a ölçütler tablosuna dipnot: *"`rejected` = tool tarafından doğrulanabilen dar kural (geçersiz katman adı) ∪ modelin kendi beyanı. Yön/import düzeyi kısıt uyumu v2'de ölçülmez; v3'te `apply` diff'inden ölçülür."*
2. FINDINGS-2 Limitations bölümüne aynı cümle.
3. `04 §6` öneri şemasında `status: rejected` tanımı bu daraltmayı yansıtır.
4. **Opsiyonel küçük genişletme (v2'de yapılabilir, ~15 satır):** `target_layer_after` hedef katmandan farklıysa ve hedef katman `target_layer_after`'ı import edemiyorsa (`scheme.allowed`), `tool_verdict=False`, reason `"moving a responsibility from X to Y requires X→Y, which the scheme forbids"`. Bu, matrisin **doğrulanabilir** kısmıdır; import tahmini gerektirmez. Yapılırsa 5a başlamadan önce yapılır, sonra prompt/mantık dondurulur.

**Kabul:** Üç doküman güncel; opsiyonel genişletme yapıldıysa `tests/test_advisor.py`'de bir `rejected` testi.

---

## D4 — `--no-arch` kokuları ve Goodhart korumasını da kapatıyor

**Ne:** `src/rlens/analysis/scanner.py` `public_interface` ve `detect_class_smells`'i yalnızca `architecture is not None` iken çalıştırıyor. `--no-arch` (veya `arch.enabled: false`) ile scan yapan kullanıcı koku etiketi alamıyor ve raporda arayüz kümesi olmadığı için `verify` Goodhart kontrolü yapamıyor (`interface_data_unavailable`).

**Neden önemli:** `god_class`, `data_class`, `feature_envy_candidate`, `long_method`, `too_many_params` ve public arayüz katmandan bağımsızdır; yalnızca `layer_misfit` katman ister. Bayrağın adı "mimariyi kapat", yaptığı "yorumlama katmanını kapat". Spesifikasyon `--no-arch`'ı "v1 davranışı" diye tanımlamıştı ve bunu kelimesi kelimesine uygulayan bir okuma savunulabilir; ama Goodhart korumasının kaybı istenmeyen bir yan etki.

**Düzeltme:** `scanner.py`'de arayüz ve katmandan bağımsız kokular her zaman hesaplanır; `layer_misfit` ve `Layer` sütunu mimari analize bağlı kalır. `--no-arch` help metni: *"Skip layer analysis and violations. Smell labels and public interface are still computed."* `test_report.py::layered_no_arch` snapshot'ı buna göre güncellenir (kokular görünür, katman sütunu görünmez).

**Test:** `--no-arch` ile scan → raporda `public_interface` ve `smells` dolu, `layer` `None`, `violations` boş; ardından `verify` Goodhart kontrolü çalışır.

---

## D5 — Onarım prompt'u mimari şemayı düşürüyor

**Ne:** `prompts.py::build_repair_prompt` `output_schema()`'yı `architectural=False` ile çağırıyor. Bozuk JSON onarılırken modele gösterilen şemada `target_layer_after`, `constraints_respected`, `addresses_smells` yok; onarılmış cevap bu alanları düşürebilir.

**Neden önemli:** 5a'da onarım geçiren cevaplarda kısıt alanları sistematik olarak eksik çıkar ve `rejected`/uyuşmazlık istatistiği koşullar arasında eşit olmayan biçimde kirlenir (onarım sayısı ölçülüyor, dolayısıyla ayıklanabilir — ama önlemek daha ucuz).

**Düzeltme:** `build_repair_prompt(raw_reply, error, *, architectural: bool)`; çağıran yer (`advisor.py`) ilk prompt'ta mimari blok kullanıldıysa `True` geçirir. Test: `tests/test_prompts.py`'de `architectural=True` ile onarım şemasında üç alan var.

---

## D6 — `interface.py` docstring/kod uyumsuzluğu

**Ne:** `public_interface` docstring'i attribute kaynaklarının `class_metrics.assigned_attributes` ile aynı olduğunu ve `__slots__` adlarını içerdiğini söylüyor; kod `__slots__` içindeki adları çıkarmıyor (`__slots__` dunder olduğu için `is_public` atlıyor, içeriği okunmuyor).

**Düzeltme:** Ya `__slots__` listesindeki public adlar `attributes`'a eklenir (tercih: `class_metrics`'teki aynı yardımcıyı yeniden kullan), ya docstring düzeltilir. Tutarlılık için birincisi. Test: `__slots__ = ("x", "_y")` olan sınıfta `attributes == ("x",)`.

---

## Uygulama sırası ve dondurma noktası

```
D1 (+4 test)  →  D2 (+3 test)  →  D5  →  D3 (opsiyonel genişletme dahil)
   →  PROMPT VE MANTIK DONDURULUR (prompt_hash kaydedilir)  →  Aşama 5a başlar
D4, D6  →  5a koşarken (prompt'u etkilemez)  →  yayın öncesi
```

**Dondurma kuralı:** 5a'nın ilk çağrısı yapıldıktan sonra `prompts.py`, `smells.py` (kanıt alanları), `advisor.py::validate_constraints` değişmez. Değişirse `experiments/v2/` sıfırlanır ve toplama baştan yapılır — `docs/v2-duzeltme-asama5.md`'deki "protokol sonradan değiştirilmez" kuralı bunu kapsar.

## AGENTS.md'ye eklenecek satırlar
- Invariant testi **tüm prompt'u** kapsar; yeni bir prompt bloğu eklenirken `TestNoRawThresholds` genişletilmeden merge edilmez.
- Koku kanıtlarında eşikler yalnızca `evidence.thresholds` altında yaşar; prompt tarafı beyaz listeyle basar.
- `suspicious` yalnızca **silinen** (taşınmamış) public üye için verilir; taşınma `moved` olarak ayrı raporlanır.
