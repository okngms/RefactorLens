# RefactorLens — Genel Bakış, Sürüm Haritası ve Literatür Konumu

> **Doküman seti:** Bu dosya giriş noktasıdır. Diğer dosyalar:
> `01-v2-katman-farkinda-yorumlama.md` · `02-v3-kapali-dongu-ve-benchmark.md` · `03-v4-zaman-ve-platform.md` · `04-ortak-spesifikasyon.md`
>
> **Okuyucu:** Projeye sıfır bağlamla gelen bir geliştirici veya asistan. Her sürüm dokümanı kendi başına uygulanabilir olacak şekilde yazıldı; ortak kavramlar bu dosyada ve `04`'te tanımlıdır.

---

## 1. Proje nedir?

**RefactorLens**, Python kod tabanları için **metrik-kanıtlı AI kod inceleme** aracıdır (`pip install refactorlens`, CLI adı `rlens`). Üç fikir üzerine kurulur:

1. **Metric-grounded prompting.** LLM'e ham kod değil, önce statik analizle hesaplanmış tasarım metrikleri verilir; her öneri bir metriğe bağlanmak ve **ölçülebilir bir tahmin** içermek zorundadır ("LCOM4 düşer, DCC değişmez").
2. **Verify loop.** Öneri uygulandıktan sonra metrikler yeniden hesaplanır; hem kodun gerçekten iyileşip iyileşmediği hem de **modelin kendi tahmininin doğru olup olmadığı** puanlanır.
3. **Davranış kapısı.** Davranış testleri geçmeden hiçbir metrik iyileşmesi sayılmaz. Metrikleri iyileştirip programı bozan değişiklik regresyondur.

### Mevcut durum: v1.0.0 (PyPI'da)
- Komutlar: `scan`, `advise`, `verify`.
- Metrikler: NOM, WMC, LCOM4, DAM/`dam_strict`, DCC (isim tabanlı), CAM (annotation kapsamı ≥ eşik ise); fonksiyon düzeyinde CC, LOC, params, nesting.
- Deney bulgusu (FINDINGS.md): 13 doğrulanabilir tahminden 6'sı doğru. **Aritmetik** metriklerde (CC, WMC, PARAMS) 6/6, **yapısal** metriklerde (LCOM4, DCC, NOM, LOC) 0/7. Bir vakada model, sınıfın tüm public arayüzünü silerek metrikleri "iyileştirdi"; yalnızca davranış testleri yakaladı.
- Tasarım ilkeleri (tüm sürümlerde korunur): hedef kod asla çalıştırılmaz (`ast` ile parse); "—" (hesaplanmadı) ≠ 0; bilinmeyen config anahtarı hatadır; `--dry-run` gönderilecek prompt'u gösterir; doğrulanamayan tahminler orandan dışlanır; model adları koda gömülmez.

---

## 2. Sürüm haritası (tek bakışta)

| Sürüm | Tema | Ana soru | Ana teslimat | Bulgu raporu |
|---|---|---|---|---|
| **v1** (yayında) | Ölç ve doğrula | Modeller metrik etkisini tahmin edebiliyor mu? | scan/advise/verify | FINDINGS-1 |
| **v2** | Katman-farkında yorumlama | Mimari bağlam öneri kalitesini ve tahmin doğruluğunu artırır mı? | `arch` komutu, katman çıkarımı, ihlal tespiti, katmana göre eşikler, koku etiketleri, Goodhart koruması, bütçe/önbellek | FINDINGS-2 |
| **v3** | Kapalı döngü ve benchmark | Döngü otomatik kapanınca ve geri besleme verilince modeller iyileşiyor mu? Hangi model en iyi kalibre? | `apply`, geri beslemeli advise, davranış kapısı 2.0, refactoring türü tespiti, kalibrasyon, **LensBench**, GitHub Action | FINDINGS-3 + benchmark tablosu |
| **v4** | Zaman ve platform | Mimari borç zaman içinde nasıl birikiyor; hangi sınıflar gerçekten önemli? | git geçmişi trendi, hotspot analizi, dil eklenti protokolü, ekip raporu/politikalar | FINDINGS-4 |

**Kural:** Her sürümün bir bulgusu olmak zorundadır. Bulgusu olmayan sürüm özellik yığınıdır. Bir sürüm bitmeden sonrakine başlanmaz.

---

## 3. Literatür konumu (Eylül 2026 itibarıyla)

### 3.1 Benzer çalışmalar ve RefactorLens'in farkı

**LLM refactoring kalitesi (ampirik çalışmalar).**
- TOSEM 2026: StarCoder2, GPT-4o-mini, GPT-4o, LLaMA 3, DeepSeek-v3 ile 30 Java projesinde metrik tabanlı değerlendirme (Understand aracıyla); geliştiriciler karmaşık, bağlama duyarlı refactoring'lerde LLM'lerden daha iyi.
- EMSE 2026 (refactoring consistency): 8.096 LLM refactoring'inde 928 davranışsal tutarsızlık, 180 tam başarısızlık; DataRef (468 Java + 544 Python) veri seti.
- ASE journal 2025: LLM'lerin refactoring fırsatı tespiti genel olarak düşük, açık problem.
- **Fark:** Bu çalışmalar LLM çıktısını *dışarıdan* ölçer. RefactorLens modelin **kendi etkisi hakkındaki tahminini** ölçer (self-prediction accuracy). Bu açı literatürde yok.

**LLM ve mimari.**
- arXiv 2509.07763 (refactoring motivasyonları): LLM'ler yüzeysel motivasyonları yakalar, **mimari akıl yürütmede zorlanır**; "hibrit LLM-metrik modeller ampirik doğrulama bekliyor".
- SLR "Software Architecture Meets LLMs" (2025): **uyumluluk denetimi (conformance checking) az araştırılmış** alan.
- ArchAgent (2026): statik analiz + LLM ile mimari kurtarma; bağımlılık bağlamının doğruluğu artırdığını ablation ile gösteriyor.
- **Fark:** RefactorLens v2, katman bağlamını *öneri kalitesine* bağlar ve bunu A/B ile ölçer; mimari kurtarma değil, mimari-farkında öneri hedeflenir. Katman çıkarımı için klasik yaklaşım (bağımlılık yönü + hafif tip yayılımı sezgisi; Miranda et al.) ile uyumludur.

**Benchmark'lar.**
- SWE-Refactor (Şubat 2026): 18 Java projesinden 1.099 geliştirici yazımı refactoring; **yalnızca Java**, Python-merkezli benchmark'lara tamamlayıcı olmayı hedefler. Codex ajanı bileşik refactoring'lerde %39,4.
- SmellBench (2026), CodeTaste (2026), **RefactorBench (mevcut, isim alınmış)**.
- **Fark ve isim kararı:** v3 benchmark'ının adı **LensBench** olacaktır (RefactorBench çakışıyor). LensBench'in ölçtüğü şey farklıdır: refactoring başarısı değil, **metrik tahmin doğruluğu, kalibrasyon, kısıt uyumu ve metrik oyunlama oranı**. SWE-Refactor ile rakip değil, tamamlayıcıdır; Python'da olması da bilinçli boşluk doldurmadır.

**Reward hacking / metrik oyunlama.**
- SpecBench (Mayıs 2026): proxy metriği (görünür testler) gerçek hedeften (tutulan testler) ayırarak reward hacking'i nicel ölçer; reward hacking farkı LOC ile ölçeklenir.
- RewardHackingAgents (Mart 2026), EVILGENIE, TRACE: ajan tabanlı ortamlarda metrik/test manipülasyonu.
- **Fark:** Bu literatür genel ajan güvenliğine aittir; **refactoring benchmark'larında metrik oyunlama ölçümü yoktur**. RefactorLens'in arayüz-silme vakası ve Goodhart koruması, bu temayı refactoring alanına taşır. FINDINGS'lerde bu bağ açıkça kurulmalıdır (atıf: SpecBench'in proxy/gerçek hedef ayrımı ≈ metrik/davranış testi ayrımı).

### 3.2 Literatürden alınan somut kararlar
| Karar | Kaynak gerekçe |
|---|---|
| Davranış kapısı zorunlu, testsiz projede karakterizasyon testi üretimi (v3) | EMSE 2026: yüksek tutarsızlık oranı |
| Refactoring türü tespiti (Extract/Move/Inline…) ve tür bazında analiz (v3) | SWE-Refactor ve TOSEM çalışmaları tür bazında raporlar; karşılaştırılabilirlik |
| Katman bağlamı A/B deneyi (v2) | arXiv 2509.07763 + SLR: mimari akıl yürütme zayıf, uyumluluk az çalışılmış |
| Benchmark adı LensBench; ölçüm hedefi tahmin/kalibrasyon/oyunlama (v3) | RefactorBench adı dolu; boşluk self-prediction ve Goodhart |
| Python odaklı kalmak (v2-v3) | SWE-Refactor Java-only; Python tamamlayıcı olarak açıkça istenmiş |

---

## 4. Fikir havuzunun yeniden analizi

Aşağıdaki fikirler bu dokümanlar hazırlanırken yeniden değerlendirildi. Her birine sürüm ve gerekçe atandı.

| Fikir | Karar | Sürüm | Gerekçe |
|---|---|---|---|
| Katman çıkarımı + katmana göre eşik | **Kabul** | v2 | Literatür boşluğu + v1 bulgusunun olası açıklaması |
| Metrikten türetilen **koku etiketleri** (God Class, Data Class, Feature Envy adayı) | **Kabul (yeni)** | v2 | Literatür standart (Lanza & Marinescu kuralları); modele "DCC=8" yerine "God Class adayı" demek daha anlamlı; ucuz |
| Goodhart koruması (public arayüz kaybı) | **Kabul** | v2 | v1'in en güçlü vakası; SpecBench paraleli |
| Bütçe/önbellek | **Kabul** | v2 | Deney maliyeti; ücretsiz modellerle çalışma bir özellik |
| Metrik hesaplama kuralını prompt'a ekleme (H2) | **Kabul** | v2 deneyi | 0/7 bulgusunun en basit açıklaması; ucuz A/B |
| `apply` (git sandbox, test gating) | **Kabul** | v3 | Döngüyü kapatır; ölçekli deneyi mümkün kılar |
| Geri beslemeli advise | **Kabul** | v3 | "Tahminin yanlıştı" bilgisinin etkisi ölçülür |
| **Karakterizasyon testi üretimi** (testsiz projelerde davranış kapısı) | **Kabul (yeni)** | v3 | EMSE 2026 tutarsızlık bulgusu; testsiz projelerde araç kullanılamıyor |
| **Refactoring türü tespiti** (AST diff → Extract Method vb.) | **Kabul (yeni)** | v3 | Tür bazında tahmin doğruluğu; literatürle karşılaştırılabilirlik |
| **Kalibrasyon ölçümü** (model güven beyanı vs gerçek; Brier) | **Kabul (yeni)** | v3 | Self-prediction açısını derinleştirir; benchmark boyutu |
| LensBench (benchmark) | **Kabul (isim değişti)** | v3 | RefactorBench adı dolu |
| Çoklu model ensemble | **Kabul (küçük)** | v3 | Uyuşma oranı ucuz bir sinyal |
| GitHub Action / PR diff + ratchet | **Kabul** | v3 | Kullanıcı kazanımı için şart |
| Tip çıkarımı (jedi/pyright) | **Kabul** | v3 (opsiyonel bağımlılık) | DCC/CAM'in en büyük sınırlılığı |
| Git geçmişi trendi, hotspot (churn × karmaşıklık) | **Kabul** | v4 | Statik fotoğraftan zaman serisine |
| Dil eklenti protokolü (C# ikinci dil) | **Kabul** | v4 | Ayrı analizör, ortak spesifikasyon (`04`) |
| Ekip dashboard / policy-as-code | **Kabul (keşif)** | v4 | Olası ticari katman; kullanıcı gelmeden yapılmaz |
| Web UI, IDE eklentisi | **Ertelendi** | FUTURE | v4 sonrası; talep görülmeden yapılmaz |
| Java desteği | **Ertelendi** | FUTURE | C# öncelikli (spesifikasyon hazır olunca) |
| Otomatik merge / insansız uygulama | **Red** | — | Davranış kapısı insana bırakılır; güvenlik ilkesi |
| Kod üretimi (refactoring dışı) | **Red** | — | Kapsam dışı; ürün kimliği "denetleyen araç" |

---

## 5. Çalışma kuralları (tüm sürümler)
1. **Kapsam kilidi:** Sürüm dokümanındaki kapsam değişmez; yeni fikir `FUTURE.md`'ye gider.
2. **Bitti kriteri:** Her aşamanın kabul kriteri testle doğrulanır; kriter sağlanınca aşama kapanır, cila sonraki sürüme.
3. **Geriye uyumluluk:** Eski rapor JSON'ları okunmaya devam eder; şema sürümü (`schema_version`) her raporda bulunur (bkz. `04`).
4. **Dürüstlük:** Hesaplanamayan değer "—"/`null`; çıkarılan bilgi güven skoruyla; sınırlılıklar README'de.
5. **Deney disiplini:** Kullanılan model adları, sürüm, tarih, prompt hash'i ve ham veri `experiments/` altında; bulgular literatüre atıfla bağlanır.
6. **Maliyet:** Ücretsiz/lokal modeller varsayılan; pahalı model yalnızca küçük kontrol örneklemi.
