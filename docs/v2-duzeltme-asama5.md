# DÜZELTME — `01-v2-katman-farkinda-yorumlama.md` § 10, Aşama 5

`### Aşama 5 — Deney ve FINDINGS-2` bölümünün tamamını aşağıdakiyle değiştirin.
Aşama 0-4 değişmiyor.

---

## Neden değişti

Önceki tasarım: 2×2 koşul, koşul başına **≥50 doğrulanabilir tahmin**, öneriler
elle uygulanır.

v1'de 6 vaka 13 tahmin üretti — vaka başına ~2,2. 200 tahmin yaklaşık **90 vaka**
demektir. v1'de bir vaka (taze kopya → dar yorum kararı → elle refactoring →
davranış testi → ölçüm) 20-30 dakika sürdü. 90 vaka **35 saatin üzerinde** elle
iş eder ve her vakada yorum kararı verilmesi gerekir; bu, tek kişinin tutarlı
biçimde yapabileceği bir hacim değildir.

Uygulama otomatikleşmeden bu ölçek gerçekçi değil, ve `apply` v3'ün konusu.
Kapsam kilidi gereği v3 özelliği v2'ye çekilmez.

**Ama H1'in üç alt iddiasından biri uygulama gerektirmez.** Kısıt uyumu
önerinin metninden ölçülür: öneri `rejected` mi, hedef katmanı doğru mu
adlandırmış, kokuyu adreslemiş mi. Bunların hiçbiri kodu değiştirmeyi
gerektirmez. Yalnızca **tahmin doğruluğu** ve **davranış kapısı** uygulama ister.

Aşama 5 bu çizgiden ikiye ayrılır.

---

### Aşama 5a — Öneri düzeyi deney (uygulama yok)

**Ne ölçer:** Katman bağlamının ve metrik kurallarının **öneri kalitesine**
etkisi. Yalnızca API çağrısı; kod değiştirilmez.

**Tasarım:** 2×2 koşul (`arch-context` × `metric-rules`) × 3 model × 3 hedef ×
n=3 = **108 çalıştırma**. Önbellek ve bütçe zaten Aşama 0'da var; günlere
yayılabilir, kesintiye dayanıklı olmalı (v1'in `run_advice.py` deseni).

**Ölçülenler:**

| Ölçüt | Nasıl |
|---|---|
| Kısıt uyumu | `constraints_respected` beyanı **ve** araç tarafından bağımsız doğrulaması; uyuşmazlık ayrı raporlanır |
| `rejected` oranı | Katman kuralını ihlal eden öneri oranı, koşul başına |
| Hedef katman doğruluğu | `target_layer_after` beyanı elle değerlendirilir (3 hedef × 4 koşul = 12 karar, uygulanabilir) |
| Koku adresleme | `addresses_smells` gerçekten o kokuyu ele alıyor mu |
| Tekrarlar arası tutarlılık | v1'deki Jaccard ölçütü, koşul başına |
| `data_class` etkisi | `Customer` için öneri geliyor mu; etiket yanlış pozitifi nötrlüyor mu |
| Sözleşme uyumu | `unlinked`, onarım, ayrıştırılamayan oranları (v1 ile karşılaştırılabilir) |

**H1a:** Katman bağlamı kısıt uyumunu artırır ve `rejected` oranını düşürür.
**H1c:** Katman bağlamı, `data_class` etiketli sınıf için gereksiz öneri üretimini
azaltır.

**Bitti ⇔** 108 çalıştırma toplandı; `analysis-advice-v2.md` üretildi; H1a ve
H1c için koşul başına sayılar var.

---

### Aşama 5b — Uygulanmış deney (küçültülmüş)

**Ne ölçer:** Tahmin doğruluğu ve davranış kapısı — yalnızca uygulama ile
ölçülebilenler.

**Kritik daraltma: dört koşul yerine iki.** Uygulanacak eksen `metric-rules`
(açık/kapalı), `arch-context` sabit **açık** tutulur.

Gerekçe: v1'in 0/7 bulgusunun en basit açıklaması modelin metriğin **hangi
kapsamda** ölçüldüğünü bilmemesiydi. `metric-rules` bunu doğrudan test eder ve
**yalnızca uygulama ile** ölçülebilir. Katman bağlamının asıl vaadi ise daha iyi
öneri, ki onu 5a zaten ölçüyor.

**Tasarım:** 2 koşul × 3 model × 2 hedef × n=1 (her zaman rep1, her zaman öneri 1)
= **12 vaka**, tahmini 25-30 doğrulanabilir tahmin.

Hedefler: `layered_project`'ten `services.order_service:OrderService` (sınıf,
`god_class`) ve `api.report_view:ReportView.describe_customer` bağlamında bir
fonksiyon hedefi. v1'in "sınıf hedefi zor, fonksiyon hedefi kolay" ayrımı
korunur ki karşılaştırılabilir olsun.

**H2:** Hesaplama kurallarının prompt'a eklenmesi **Sınıf B** (kalıntıya bağlı)
metriklerde tahmin doğruluğunu artırır. Sınıf A'da etki beklenmez — zaten 6/6.

**Bitti ⇔** 12 vaka ölçüldü; `analysis-verify-v2.md` üretildi; H2 için koşul
başına Sınıf A / Sınıf B kırılımı var; her vaka için `applied.diff` ve gerekiyorsa
`INTERPRETATION.md` işlendi.

---

### Güç analizi ve dürüstlük

25-30 tahmin, ikiye bölündüğünde koşul başına ~13 — v1 ile aynı büyüklük.
**Bu, küçük bir etkiyi saptamaya yetmez.** Ne beklenebileceği açıkça yazılmalı:

- Sınıf B doğruluğu 0/7'den örneğin 5/13'e çıkarsa, bu **işaret**tir, kanıt
  değil. FINDINGS-2 bunu böyle sunmalıdır.
- Hiç değişmezse (0/13 gibi) bu daha güçlü bir sonuçtur: en basit müdahale
  işe yaramıyor demektir ve v3'ün geri besleme yaklaşımı için gerekçe olur.
- Etki büyüklüğü için güven aralığı verilmeli; yüzde tek başına yanıltıcıdır.

**Tam tasarım v3'e ertelenir.** `apply` uygulamayı otomatikleştirdiğinde
koşul başına ≥50 tahmin ulaşılabilir hale gelir ve 2×2 tasarım orada koşulur.
`02` (v3) Aşama 6'ya not düşülür: LensBench koşulları arasına `arch-context` ve
`metric-rules` eksenleri eklenir, böylece v2'nin küçük örneklemli işareti v3'te
gerçek güçle sınanır.

---

### FINDINGS-2 kapsamı

**Setup** → **Protocol** (5a ve 5b ayrı; rep1/öneri1 kuralları; dar yorum) →
**Results**: 5a tabloları (kısıt uyumu, `rejected`, tutarlılık), 5b tabloları
(**metrik başına önce**, sonra Sınıf A/B özeti — bkz. `04 §2.5` düzeltmesi) →
**Vaka analizleri** (en az 4, en az biri `data_class`, en az biri `suspicious`
ya da kapı hatası) → **Literatür bağı** (arXiv 2509.07763 mimari akıl yürütme,
SLR uyumluluk denetimi boşluğu, SpecBench proxy/gerçek hedef paraleli) →
**Limitations**.

Limitations'a mutlaka girecekler: 5b'nin n=1 olduğu ve koşul başına ~13 tahminle
küçük etkiyi saptayamayacağı; tam 2×2 tasarımın v3'e ertelendiği; uygulayanın
deneyi tasarlayan kişi olduğu; tek fikstür; ve `04 §2.5` sınıflandırmasının
kendisinin bir hipotez olduğu.

**Bitti ⇔** FINDINGS-2 yayınlandı; ham veri `experiments/v2/`; **v2.0.0** PyPI'da;
README güncel.
