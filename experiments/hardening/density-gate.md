# `god_class` kapısı — yoğunluk adayları

v2.2 §5b'nin ilk sorusu (`docs/v2.2-python-metrikleri.md`, K4). `god_class` bugün
NOM ≥ 20 ∧ WMC ≥ 50 ∧ LCOM4 ≥ 3 ister; LCOM4 metot çağrısını bağ saydığı için
ortak yardımcı metodu olan büyük sınıflar kokudan kaçıyor. Bu belge kapının
yerine konabilecek iki literatür ölçüsünü §3'ün dokuz maddesiyle yazar ve
korpusta ölçer. Karar `docs/v2-tanim-kararlari.md` K9'da.

**Sonuç tek cümleyle:** iki aday da kabul edilmedi. Ölçüm, sorunun çağrı
kenarı değil **durumsuz metot** olduğunu gösterdi: büyük sınıfların %41'inde
metotların çoğu hiçbir `self.<attr>`'a dokunmuyor ve durum paylaşımına bakan
hiçbir kapı bunları "çok sorumluluk"tan ayıramıyor.

```bash
python experiments/hardening/corpus.py fetch     # bir kez, ~850 MB
python experiments/hardening/density_gate.py     # ~2 dk
```

Çıktılar: `results/density-gate.json`, `results/density-gate-tables.md`; tekrar
üretildiğinde birebir aynı.

## Dokuz madde

**Sıra, dürüstçe:** maddeler 1-4, 8'in kuralı ve 9(b) ölçümden önce yazıldı
(`density_gate.py` docstring'i). 9(a) ve 9(c) sonuçlar görüldükten sonra
formüle edildi; bu yüzden onlara dayanan ret daha zayıf kanıttır ve öyle
okunmalı. 5-7 bu belgeyle birlikte yazıldı.

| # | LCOM3-HM | TCC (doğrudan) |
|---|---|---|
| 1. Neyi sayıyor | LCOM4'ün metot–attribute grafiği, çağrı kenarları olmadan; bağlı bileşen sayısı (Hitz ve Montazeri 1995). Adı Henderson-Sellers'ın LCOM3'üyle (LCOM\*) çakışır, o başka bir formüldür. | En az bir attribute'u doğrudan paylaşan metot çifti / bütün çiftler (Bieman ve Kang 1995; Lanza ve Marinescu 2006 God Class stratejisi). Özgün tanımın dolaylı erişimi (çağrı ağacı) sayılmaz: sayılırsa ortak yardımcı yine her şeyi bağlar. |
| 2. Birim | Sınıf. Düğüm kümesi `lcom4` ile aynı: `class_methods`, adla (getter/setter tek düğüm), `accessed_attributes`. | Aynı. |
| 3. Aralık, yön | ≥ 1, yüksek = kötü. | 0..1, düşük = kötü. |
| 4. Hesaplanamaz | Metot yok → `null`. | İkiden az metot adı → `null`. |
| 5. Altın değerler | `tests/test_hardening_density_gate.py`: ortak yardımcılı 4 metotlu sınıfta LCOM4 1, LCOM3-HM 3, TCC 1/6; iki kümeli sınıfta LCOM4 = LCOM3-HM = 2, TCC 1/3. Elle, koddan önce. Aday reddedildiği için fikstür altın değerleri hesaplanmadı. | Aynı test. |
| 6. Bilinen yanlış pozitifler | Durumsuz metotlar her biri ayrı bileşen: taslak arayüzler (`pass`), `@staticmethod` resolver'lar, kardeşine devreden metotlar. Kalıtılan attribute ile kalıtılan metot ayırt edilmez (`self.fail` üst sınıftaysa attribute sayılır). | Aynı durumsuz metotlar hiçbir çifte katılmaz; TCC'yi sıfıra çeker. |
| 7. Kanıt alanları | Yeni koku sürümünde `lcom3_hm` ve `thresholds`; FINDINGS'in `god_class` kanıtı değişmez. | `tcc` ve `thresholds`. |
| 8. Eşik kuralı | Bugünkü kapının yeri: LCOM4 ≥ 3, sınıf dağılımının ≈ p90'ı. Aday aynı persentilden. | Düşük uçta aynı yer: ≈ p10. |
| 9. Geçerlilik iddiası ve çürütme | İddia: büyük ve durum paylaşımı parçalı sınıf. Çürütme: (a) kapı büyük sınıfları ayırmıyorsa (neredeyse hepsinde ateşliyorsa) boyuttan başka bilgi taşımıyordur; (b) yeni ateşlediği sınıfların çoğu durumsuzsa "çok sorumluluk" değil "durumsuzluk" ölçüyordur. | Aynı; ayrıca (c) eşik persentili dağılımın sabit bir bölgesine düşüyorsa (p10 = p25 = 0) persentil eşiği tanımlanamaz. |

## Ölçüm

26 proje, scan şeması 3. Dağılım: en az iki farklı adlı metodu olan sınıflar,
proje başına persentil, projelerin medyanı (17 proje).

| Ölçü | p5 | p10 | p25 | p50 | p75 | p90 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| TCC | 0 | 0 | 0 | 0.059 | 0.368 | 1 | 1 |
| LCOM3-HM | 1 | 1 | 2 | 3 | 5 | 7.30 | 11 |

Kapılar, boyut koşulunu geçen 159 sınıfta. Yeni / kayıp: bugünkü kapıya göre.
"Durumsuz": metotlarının en az yarısı hiçbir attribute'a dokunmayan sınıf
(159'un 65'i).

| Kapı | ateşler | yeni | kayıp | yeni içinde durumsuz | ateşleyen içinde durumsuz |
|---|---:|---:|---:|---:|---:|
| lcom4 >= 3 (bugün) | 96 | 0 | 0 | 0 | 44 |
| lcom3 >= 3 | 157 | 61 | 0 | 21 | 65 |
| lcom3 >= 5 | 151 | 56 | 1 | 21 | 65 |
| lcom3 >= 10 | 115 | 35 | 16 | 21 | 65 |
| tcc < 0.05 | 56 | 15 | 55 | 15 | 53 |
| tcc < 0.1 | 74 | 20 | 42 | 19 | 61 |
| tcc < 0.2 | 101 | 32 | 27 | 21 | 65 |
| tcc < 0.333 | 125 | 44 | 15 | 21 | 65 |

**Doğrulama.** `lcom3 >= 3`'ün yeni ateşlediği 61 sınıf, dağılım tablosunun
"yalnız çağrı kenarı yüzünden elenen" 61 sınıfıyla aynı sayı; iki ayrı yol
tutarlı. Betik ayrıca her sınıfta LCOM3-HM ≥ LCOM4 olduğunu denetler (uymayan 0).

Durumsuz metotların türü (büyük sınıflardaki bütün durumsuz metot adları):

| Tür | metot | baskın olduğu durumsuz sınıf |
|---|---:|---:|
| taslak (`pass`, `...`, `raise NotImplementedError`) | 283 | 3 |
| alıcısız (`@staticmethod`) | 285 | 6 |
| kardeşine devreden | 2 481 | 38 |
| alıcısı var, kullanılmıyor | 1 018 | 20 |

## Bulgular

### 1. LCOM3-HM kapıyı boyut koşuluna indiriyor

`lcom3 >= 3` 159 büyük sınıfın **157'sinde** ateşliyor. Kapı artık bilgi
taşımıyor; `god_class` fiilen "NOM ≥ 20 ∧ WMC ≥ 50" olur. Persentil kuralı
(≈ p90 → 8) da durumu değiştirmiyor: `lcom3 >= 10` bile 115'inde ateşliyor ve
bugünkü kapının 16 sınıfını kaybediyor. Çürütme (a) karşılandı.

### 2. TCC'nin persentil eşiği tanımlanamıyor

Tipik projede sınıfların en az dörtte birinin TCC'si **0** (p5 = p10 = p25 = 0);
medyan 0.059. Düşük uçta bir persentil eşiği sabit bir bölgeye düşer. Lanza ve
Marinescu'nun 1/3'ü sınıfların %73.8'ini işaretliyor. Eşik düşürüldükçe kapı
bugünkünden **daha çok** sınıf kaybediyor (`tcc < 0.05`: 15 yeni, 55 kayıp).
Çürütme (c) karşılandı.

### 3. Asıl sorun durumsuz metot

- Büyük sınıfların **%41'i** (159'un 65'i) durumsuz. En kalabalık tür
  **kardeşine devreden** metot (2 481); çağrı kenarı sorunu bunun öbür yüzü:
  LCOM4 onları çağrıyla birleştirir, LCOM3-HM ve TCC her birini ayrı sayar.
- Durum paylaşımına bakan bir ölçü, "tek sorumluluğun uzun kataloğu"
  (`mypy.MessageBuilder`: 139 metodun 84'ü durumsuz ve bir kardeş metodu
  çağırıyor) ile
  "birbirine ilgisiz sorumluluklar"ı ayıramaz: ikisinde de metotlar durum
  paylaşmaz. Bu ayrım için bir doğruluk verisi (etiketli god class) gerekiyor.
- Çürütme (b) tam karşılanmadı: `lcom3 >= 3`'ün yeni 61 sınıfının 21'i (%34)
  durumsuz, çoğunluk değil. Aday (a) yüzünden reddedildi.

### 4. Bugünkü kapının da yanlış pozitifleri var

Bugün ateşleyen 96 `god_class`'ın **44'ü** durumsuz. Sekizi açıkça şüpheli:
metotlarının en az yarısı taslak olan soyut arayüzler (`mypy.NodeVisitor` —
83 metodun 83'ü `pass`, `mypy._Hasher`, `pandas.BaseStringArrayMethods`) ve
metotlarının en az yarısı `@staticmethod` olan graphene tipleri (saleor
`User`, `Checkout`, `Order`, `Product`, `Shop`). LCOM4 her taslak ya da
alıcısız metodu ayrı bileşen sayar; bunlar kokunun "bölünebilir sınıf"
iddiasıyla örtüşmüyor. Sınıf sınıf okunup etiketlenmedi; "şüpheli" sayım bir
ölçü, hüküm değil.

## Karar girdisi

- Kapı değişmez (K4 sürer). İki aday dokuzuncu maddede düştü.
- Sıradaki soru durumsuz metotların ne yapılacağı. Adaylar (her biri dokuz
  maddeden geçer): taslak metotları NOM/LCOM4'ün düğüm kümesinden çıkarmak
  (tanım değişikliği, şema artışı); kapıyı yalnızca durumlu metotlar üzerinde
  kurmak; ya da `god_class`'ı etiketli veriyle doğrulamak.
- **Etiketli veri:** §2 PySmell'in etiketli veri setine dayanıyor; Large Class
  etiketlerinin bu soruyu cevaplayıp cevaplamadığı **incelenmedi**. Kapı
  yeniden tasarlanmadan önce bakılması gereken ilk kaynak.
