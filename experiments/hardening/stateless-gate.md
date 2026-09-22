# `god_class` ve durumsuz metotlar — ön kayıt

v2.2 §5b, K9'un açtığı soru. **Bu bölüm ölçümden önce yazıldı** (2026-09-22) ve
sonuçlar görüldükten sonra değiştirilmez; sonuçlar ve karar aşağıdaki
"Ölçüm" bölümüne eklenir. K9'da reddi taşıyan iki koşul sonuçlardan sonra
formüle edilmişti; bu belge o zayıflığı tekrarlamamak için var.

## Etiketli veri — yol 1'in sonucu

K9 önce etiketli veriye bakılmasını önerdi. Bakıldı:

- **PySmell** (Chen ve ark. 2016, `github.com/chenzhifei731/Pysmell`, commit
  `233afeb`, 2018): Large Class verisi yalnızca `CLOC` sütunu taşıyor. Elle
  incelenen 300 sınıfın (`manual inspection/LargeClass.csv`; django 1.8.2,
  scipy 0.16, matplotlib 1.4.3, boto, nltk, numpy 1.9.2, ansible, tornado,
  ipython) etiketi tek bir eşikle **1 hatayla** ayrılıyor: `CLOC >= 37`
  (11 pozitif, 289 negatif). Etiket boyutu kodluyor, sorumluluk dağılımını
  değil.
- **PeerJ 2023** (Sandouka ve Aljamaan, Python Large Class ML veri seti):
  "each instance was labeled based on the published labeled PySmell dataset" —
  aynı etiket.
- **MLCQ** God Class etiketleri taşıyor ama Java.

Sonuç: `god_class` kapısının kohezyon koşulunu doğrulayacak bir Python etiket
kaynağı **yok**. Kohezyon iddiası ancak kendi etiketli örneklemimizle sınanabilir
(bkz. "Sonraki adım").

## Adaylar

Hepsi yalnızca boyut koşulunu (NOM ≥ 20 ∧ WMC ≥ 50) geçen sınıflarda sonuç
değiştirir. Durumlu metot: en az bir `self.<attr>`'a dokunan metot adı
(`density_gate.attribute_sets`); durumsuz türleri `density_gate.stateless_kinds`.

| Aday | Kural | Tanıma dokunur mu |
|---|---|---|
| R1 | Metot adlarının en az yarısı taslaksa (`pass`, `...`, `return None`, `raise NotImplementedError`) koku verilmez. | Hayır; K6 gibi yalnızca koku kuralı. |
| R2 | Metot adlarının en az yarısı alıcısızsa (`@staticmethod`) koku verilmez. | Hayır; koku kuralı. |
| R3 | Kapı LCOM4 ≥ t, ama LCOM4 yalnızca durumlu metotların grafiğinde (çağrı kenarları dahil). | Yeni ölçü (kanıt alanı) → yeni koku sürümü. |
| R4 | Kapı LCOM3-HM ≥ t, yalnızca durumlu metotlar üzerinde. | Yeni ölçü → yeni koku sürümü. |

R3/R4 için t: bugünkü kapının yeri, ölçünün sınıf dağılımında ≈ p90 (en az iki
durumlu metot adı olan sınıflar, proje başına, projelerin medyanı; en yakın
tamsayı).

## Dokuz madde (R3, R4)

1. **Neyi sayıyor.** R3: durumlu metot adlarının grafiğinde, ortak attribute
   ya da doğrudan çağrı kenarıyla bağlı bileşen sayısı. R4: aynı düğümler,
   yalnızca ortak attribute kenarı.
2. **Birim.** Sınıf; düğüm kümesi `lcom4` ile aynı kurallarla, sonra durumsuz
   adlar çıkarılır.
3. **Aralık, yön.** ≥ 1; yüksek = durum paylaşımı parçalı.
4. **Hesaplanamaz.** Durumlu metot adı yoksa `null`.
5. **Altın değerler.** `tests/test_hardening_stateless_gate.py`, elle, koddan
   önce.
6. **Bilinen yanlış pozitifler.** Kalıtılan attribute ile kalıtılan metot
   ayırt edilmez (`self.fail` üst sınıftaysa attribute sayılır ve o metodu
   durumlu yapar); yalnızca `self.helper()` çağıran metot durumsuz sayılır
   ve kapıya hiç girmez — "kardeşine devreden" 2 481 metot kapının dışında
   kalır. Bu adayların bilinçli bedeli: kapı durumsuz katalog sınıflarını
   **görmez**.
7. **Kanıt alanları.** Yeni koku sürümünde `lcom4_stateful` / `lcom3_stateful`,
   `stateful_methods`, `thresholds`; FINDINGS'in `god_class` kanıtı değişmez.
8. **Eşik.** Yukarıdaki kural (≈ p90).
9. **Geçerlilik iddiası ve çürütme — ölçümden önce.** İddia: büyük bir sınıfın
   durum taşıyan metotları birbirinden kopuk kümelere ayrılıyorsa sınıf
   birden fazla veri sorumluluğu taşır. Bir aday şu koşullardan **herhangi
   biri** gerçekleşirse reddedilir:
   - (a) boyut koşulunu geçen sınıfların **%90'ından fazlasında** ateşliyorsa
     (boyuttan başka bilgi taşımıyor);
   - (b) metot adlarının en az yarısı taslak olan **herhangi bir** sınıfta
     ateşliyorsa (davranışı olmayan sınıf sorumluluk taşımaz — tanım gereği
     yanlış pozitif);
   - (c) eşik persentili dağılımın sabit bir bölgesine düşüyorsa (p75 = p90 =
     p95: eşik ayırmıyor);
   - (d) bugünkü kapının ateşlediği ve durumsuz olmayan (durumsuz payı < %50)
     sınıfların **yarısından fazlasını** kaybediyorsa (bugünkü kapının en az
     tartışmalı kısmını atıyor).

   R1 ve R2 için: (b)'nin R1'e uygulanışı kuraldır; R1 ve R2 bugünkü kapının
   **en fazla %10'unu** kaldırmalı, yoksa "dar kural" olmaktan çıkar ve bir
   tanım değişikliği gibi tartılmalı (K6'nın dar tanım ilkesi).

**Kabulün tavanı.** Etiketli veri olmadığı için hiçbir aday bu ölçümle
"doğrulandı" olamaz. Çürütmeleri geçen bir aday **"etiketli örneklemle
sınanacak aday"** olur; kodlanmaz. İstisna R1: (b) tanım gereği bir yanlış
pozitifi kaldırdığı için etiket gerektirmez; (d) ve %10 sınırını geçerse
K6 gibi dar bir koku kuralı olarak uygulanabilir.

## Sonraki adım (her durumda)

Kohezyon iddiasını sınamak için etiketli örneklem: boyut koşulunu geçen
159 sınıftan tabakalı örneklem, yazılı bir etiketleme kılavuzuyla ve
etiketleyenin kapı sonuçlarını görmeden karar verdiği bir protokolle
(`dcc-verdicts.json`'ın deseni). Etiketleyen bu projeyi tasarlayan kişi
olduğu sürece sonuç o sınırlılığı taşır ve yazılır.

---

## Ölçüm

*Bu bölüm ölçümden sonra eklendi; yukarısı değiştirilmedi.*

```bash
python experiments/hardening/stateless_gate.py     # ~2 dk
```

Çıktılar `results/stateless-gate.json` ve `results/stateless-gate-tables.md`;
tekrar üretildiğinde birebir aynı. R1'in taslak payı aracın K10 kuralıyla
aynı fonksiyondan gelir (`class_metrics.stub_method_share`); kural araca
eklendikten sonra yeniden koşuldu, sonuç değişmedi.

Dağılım (en az iki durumlu metot adı olan sınıflar, 13 proje):

| Ölçü | p50 | p75 | p90 | p95 |
|---|---:|---:|---:|---:|
| LCOM4, durumlu | 1 | 2 | 2 | 2 |
| LCOM3-HM, durumlu | 2 | 2 | 3 | 3.8 |

Boyut koşulunu geçen 159 sınıf; bugünkü kapı 96'sında ateşliyor, 3'ü taslak
arayüz:

| Aday | eşik | ateşler | yeni | kayıp | ateşleyen içinde durumsuz | ateşleyen taslak arayüz | çürütme |
|---|---:|---:|---:|---:|---:|---:|---|
| R1 | - | 93 | 0 | 3 | 41 | 0 | yok |
| R2 | - | 91 | 0 | 5 | 39 | 3 | (b) |
| R3 | 2 | 64 | 13 | 45 | 23 | 0 | (c) |
| R4 | 3 | 70 | 17 | 43 | 28 | 0 | yok |

## Sonuçlar — ön kayda göre

- **R1 kabul, uygulandı (K10).** Hiçbir çürütme koşulu gerçekleşmedi;
  kaldırdığı 3 sınıf (`mypy.NodeVisitor`, `mypy._Hasher`,
  `pandas.BaseStringArrayMethods`) bugünkü kapının %3.1'i, dar kural sınırı
  (%10) içinde. Ön kayıttaki istisna gereği etiket gerektirmez.
- **R2 reddedildi, (b).** R2 taslak arayüzlere dokunmaz ve onlarda ateşlemeye
  devam eder. Açıkça yazmak gerekir: (b) R2'yi **kurgusu gereği** reddetti;
  R1 ile birleşik bir R1+R2 adayı ön kayıtta yoktu ve sonradan eklenmedi.
  graphene tiplerinin (`@staticmethod` resolver'lar) god class olup olmadığı
  etiket gerektiren bir soru; etiketli örneklemde görünecek.
- **R3 reddedildi, (c).** p75 = p90 = p95 = 2: eşik ayırmıyor.
- **R4 çürütmeleri geçti.** Tavan gereği "etiketli örneklemle sınanacak aday";
  **kodlanmadı.** Yeni ateşlediği 17 sınıfın ilk örnekleri `mypy.TypeChecker`,
  `saleor.PluginsManager`, `mypy.MessageBuilder`, `pydantic.GenerateSchema`;
  kaybettiği 43 sınıfın ilk örnekleri `saleor.WebhookPlugin`,
  `mypy.ExpressionChecker`, `pandas.ArrowExtensionArray`.

## Etiketli örneklem — hazırlandı, etiketlenmedi

`god_class_sample.py sample` 32 sınıf çekti (seed 20260922, hücre başına 8).
Popülasyon K10 sonrası 156 büyük sınıf; hücreler bugünkü kapı × R4:

| Hücre | sınıf |
|---|---:|
| ikisi de ateşliyor | 53 |
| yalnız bugünkü kapı | 40 |
| yalnız R4 | 17 |
| hiçbiri | 46 |

Tutarlılık: 53 + 40 = 93 (K10 sonrası `god_class` sayısı, envanterle aynı);
53 + 17 = 70 (R4). Etiketleyenin göreceği dosya (`god-class-sample.json`)
yalnızca kimlik ve konum taşır; kılavuz `god-class-labeling.md`; kararlar
`god-class-verdicts.json`'a. `summary` tek bir karar eksikken sonuç üretmez.

**Bu oturumda etiketlenmedi, çünkü etiketleyen kör değil:** örneklemi çeken
ve kapıları ölçen asistan hangi sınıfta hangi kapının ateşlediğini gördü
(yukarıdaki örnek listeler). Kör etiketleme için etiketleyen bu listeleri ve
`results/` altındaki kapı çıktılarını görmemiş biri olmalı.
