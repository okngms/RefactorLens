# Kapsama — kalibrasyon korpusu

Sertleştirme Blok 1b, madde 3 (`docs/v2-sertlestirme.md`). 26 proje, scan
şeması 3, kullanıcının varsayılan taraması. Soru: her metrik kaç birimde
hesaplanabiliyor ve kaçında **ayırt ediyor**? Planın kuralı: ayrım yapmayan
metrik düşürülür ya da gerekçesiyle tutulur. Karar `docs/v2-tanim-kararlari.md`
K7'de.

**Bu belge metrik ve eşik değiştirmez.**

```bash
python experiments/hardening/corpus.py fetch     # bir kez, ~850 MB
python experiments/hardening/coverage.py         # ~2 dk
```

Çıktılar: `results/coverage.json` (proje başına tüm sayımlar) ve
`results/coverage-tables.md` (aşağıdaki tablolar aynı dosyadan). İkisi de
tekrar üretildiğinde birebir aynıdır.

## Yöntem

Her metrik ve her proje için birimler (fonksiyon, sınıf, modül) üç kovaya
ayrılır; toplamları birim sayısıdır:

| Kova | Anlamı |
|---|---|
| `null` | hesaplanamadı |
| **tanım gereği belli** | hesaplandı ama değer ölçmeden biliniyordu |
| **bilgi taşıyan** | geri kalanı |

Tanım gereği belli sayılan üç durum:

- **LCOM4:** tek adlı metodu olan sınıf. `lcom4` metotları adla düğüm yapar
  (property getter/setter tek düğüm); tek düğümlü grafiğin bileşen sayısı 1.
- **CAM:** parametreli tek metodu olan sınıf; tek metodun tipleri birleşimin
  tamamı, değer 1.0 (`cam_coverage.py`, Blok 1 §5).
- **DAM:** tek attribute'lu sınıf; değer yalnızca 0 ya da 1 olabilir. Oran
  değil, ikili bayrak.

**Ayırt ediyor mu?** Bilgi taşıyan değerlerde p10 ≠ p90 ise metrik o projede
birimlerin orta %80'ini birbirinden ayırıyor demektir. Yanında en sık değerin
payı (mod payı) verilir. Bu soruya yalnızca en az 30 bilgi taşıyan değeri olan
proje katılır (dağılım tablosuyla aynı `MIN_VALUES`).

**Ağırlıklandırma** dağılım tablosuyla aynı: paylar proje başına, genel değer
projelerin medyanı.

**Doğrulama.** Betik, tanım gereği belli sayılan her değerin gerçekten o değer
olduğunu (LCOM4 = 1, CAM = 1.0, DAM ∈ {0, 1}) korpusun tamamında denetler ve bir
tane bile uymazsa tablo üretmez. Korpusta uymayan değer 0.

**Dağılım tablosundan farkı.** `metric-distribution.md`'nin `null` sütunu yalnızca
o metrikte ≥ 30 değeri olan projelerin medyanıdır; burada birimi olan her
proje katılır. Bu yüzden CAM'in `null` payı orada %61.6, burada hesaplanan pay
%27.7 (yani `null` %72.3). İkisi farklı proje kümelerinin medyanı; çelişki
değil.

## Tablolar

Scan şeması 3. Paylar birim başına, projelerin medyanı. Yayılım ve mod: bilgi
taşıyan en az 30 değeri olan projeler.

### Kapsama — tüm korpus

| Metrik | Birim | Proje | hesaplanan | tanım gereği belli | bilgi taşıyan | yayılım (p10 < p90) | mod | mod payı |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| CC | function | 26 | %100.0 | %0.0 | %100.0 | 25/25 | 1 | %39.6 |
| LOC | function | 26 | %100.0 | %0.0 | %100.0 | 25/25 | 2 | %22.1 |
| PARAMS | function | 26 | %100.0 | %0.0 | %100.0 | 25/25 | 1 | %35.8 |
| NESTING | function | 26 | %100.0 | %0.0 | %100.0 | 25/25 | 0 | %42.4 |
| NOM | class | 26 | %100.0 | %0.0 | %100.0 | 24/24 | 0 | %43.2 |
| WMC | class | 26 | %100.0 | %0.0 | %100.0 | 24/24 | 0 | %39.6 |
| LCOM4 | class | 26 | %63.1 | %21.8 | %35.6 | 17/17 | 1 | %42.9 |
| DCC | class | 26 | %100.0 | %0.0 | %100.0 | 24/24 | 1 | %37.1 |
| DAM | class | 26 | %78.7 | %17.8 | %59.9 | 12/19 | 0 | %86.5 |
| CAM | class | 26 | %27.7 | %6.9 | %15.9 | 8/8 | 0.50 | %23.5 |
| Ca | module | 26 | %100.0 | %0.0 | %100.0 | 17/17 | 1 | %32.1 |
| Ce | module | 26 | %100.0 | %0.0 | %100.0 | 17/17 | 0 | %24.6 |
| I | module | 26 | %96.2 | %0.0 | %96.2 | 17/17 | 0 | %23.4 |

### Bilgi taşıyan pay — tür bazında

Hücre: bilgi taşıyan pay (yayılım gösteren proje / uygun proje).

| Metrik | library | cli | web_app | ml_research |
|---|---:|---:|---:|---:|
| LCOM4 | %38.5 (7/7) | %38.1 (4/4) | %27.0 (5/5) | %30.6 (1/1) |
| DAM | %53.2 (6/7) | %59.4 (4/5) | %51.9 (1/5) | %69.7 (1/2) |
| CAM | %18.2 (4/4) | %11.5 (1/1) | %5.0 (3/3) | %9.4 (0/0) |

Diğer on metriğin tamamı her türde %93'ün üstünde bilgi taşıyor ve uygun her
projede yayılım gösteriyor (tam tablo `results/coverage-tables.md`).

### Ölçülen mantık payı

Raporun birimlerinin kapsadığı mantık satırı payı (`corpus-inventory.json`,
tanım `corpus.md`).

| Genel | library | cli | web_app | ml_research | en düşük üç |
|---:|---:|---:|---:|---:|---|
| %97.1 | %97.0 | %97.0 | %97.4 | %98.6 | nanogpt %44.1, httpie %82.5, rich %87.4 |

---

## Bulgular

### 1. On metrik tartışmasız: her yerde hesaplanıyor, her yerde ayırıyor

CC, LOC, PARAMS, NESTING, NOM, WMC, DCC, Ca, Ce ve I birimlerin %96-100'ünde
hesaplanıyor ve uygun her projede yayılım gösteriyor. En sık değerin payı
%22-43. Bu metrikler için kapsama sorunu yok; soru yalnızca eşik.

### 2. CAM: kapsama sorunu, ayrım sorunu değil

- **Hesaplanan pay %27.7, bilgi taşıyan pay %15.9** (proje medyanı). Tipik bir
  projede CAM her altı sınıftan birinde gerçek bir ölçü.
- Kapsam **projenin annotation kültürüne** bağlı: yt-dlp %0.4, awscli %0.1,
  netbox %0.02, redash %0.4 bilgi taşıyan; flask %58.7, segment-anything %52.6.
  requests, yolov5 ve nanoGPT'de CAM hiç hesaplanmıyor. Blok 1'in "iki kutuplu
  kapsam" bulgusu (metric-accuracy §5) korpusta da geçerli.
- **Hesaplandığı yerde ayırıyor.** En az 30 bilgi taşıyan değeri olan 8
  projenin 8'inde yayılım var; p10'ların medyanı 0.14, p90'ların medyanı 0.84,
  mod payı %23.5.
- **Dağılım tablosunun Bulgu 6'sı düzeltiliyor.** Orada "CAM p75'ten itibaren
  1.0, tavana yapışıyor" yazıyordu. Tavanı tanım gereği 1.0 olan değerler
  üretiyor: onlar çıkarılınca p90 bile 1.0 değil. Dağılım tablosu CAM'in
  ayırt edici olmadığını değil, **ayırt edici olmayan değerlerin dağılımı
  domine ettiğini** gösteriyordu. `metric-distribution.md`'ye not düşüldü.

### 3. DAM: projeyi ayırıyor, projenin içindeki sınıfları çoğunlukla ayırmıyor

- **Bilgi taşıyan pay %59.9** — kapsama iyi. Sorun ayrımda: tipik projede bilgi
  taşıyan değerlerin **%86.5'i tek bir değerde** (mod payı medyanı); uygun 19
  projenin 17'sinde o değer 0. p90'ların medyanı 0.10.
- **19 uygun projenin 7'sinde yayılım yok** (p10 = p90 = 0): web uygulamalarının
  beşinden dördü (healthchecks, netbox, saleor, mealie), fastapi, pipx, yolov5.
  Bu projelerde bilgi taşıyan (en az iki attribute'lu) sınıfların en az
  %90'ında hiç `_` önekli attribute yok.
- **Yayılım gösterenler:** kütüphaneler (uygun 7'nin 6'sı), mypy, httpie,
  yt-dlp, awscli, detectron2, redash. yt-dlp ve awscli'de mod **1.0**: en sık
  durum yalnızca private attribute taşıyan sınıf.
- Veri, DAM'ın bir sınıfın kapsülleme kararından çok **projenin adlandırma
  geleneğini** yansıttığı yorumuyla tutarlı: mod bazı projelerde 0, bazılarında
  1.0 ve yayılımsız projelerin hepsi 0'da. Proje içi / projeler arası varyans
  ayrıştırması yapılmadı. *Sonrası (K12, `exposure.md`):* η² 0.74 (sınıf
  ağırlıklı) / 0.50 (proje başına en fazla 200 sınıf); ön kayıtlı okumayla
  kararsız. Dogfooding gözlemi ("66 sınıfın hepsinde 0.00") web
  uygulamaları için geçerli, kütüphaneler için değil.
- `data_class` kokusu `DAM ≥ 0.5` koşulu taşıyor ve web_app'te koku oranı 0
  (`metric-distribution.md`); bu tabloyla tutarlı, ama kokunun neden
  ateşlemediği sınıf sınıf incelenmedi.

### 4. LCOM4: sınıfların beşte biri tanım gereği 1

- Hesaplanan pay %63.1 (geri kalanı metotsuz sınıf, K2), tanım gereği 1 olan
  pay **%21.8** (tek adlı metot), bilgi taşıyan pay %35.6. Üçü ayrı ayrı
  projelerin medyanı; toplanmazlar.
- Bilgi taşıyan değerler uygun 17 projenin 17'sinde yayılım gösteriyor (p10
  medyanı 1, p90 medyanı 4). LCOM4 ayırıyor.
- **Eşik kararına girdi:** dağılım tablosundaki "LCOM4 ≥ 2 sınıfların %32'si"
  payının paydası tanım gereği 1 olan sınıfları da içeriyor. Bilgi taşıyan
  sınıflar arasında pay daha yüksek olmalı; bu tabloda ölçülmedi, eşik
  kararında ölçülecek.

### 5. Ölçülen mantık payı tür değil deyim

Genel %97.1; tür medyanları %97-98.6 arası. Düşük olanlar tek tek deyim:
nanoGPT %44.1 (betik tarzı eğitim döngüsü), httpie %82.5 (modül düzeyinde CLI
tanımı), rich %87.4 (incelenmedi). `corpus.md` Bulgu 2'yi değiştirmiyor; README
"What RefactorLens does not do"da yazılı.

---

## Karar girdisi

| Metrik | Kapsama | Ayrım | Karar (K7) |
|---|---|---|---|
| 10 metrik | %96-100 | her projede | tutulur, soru yalnızca eşik |
| LCOM4 | %36 bilgi taşıyan | her projede | tutulur |
| CAM | %16 bilgi taşıyan, annotation kültürüne bağlı | hesaplandığı her projede | tutulur; `null` + sebep zaten raporda |
| DAM | %60 bilgi taşıyan | 19 projenin 12'sinde; web_app'te 5'in 1'inde | tutulur, gerekçesiyle; yeniden tanım v2.2'de |

Düşürme seçeneğinin maliyeti K7'de: alan kaldırmak şema artışı demek, DAM
`data_class`'ın kanıt alanında ve ikisi de `advise` prompt'unun metrik
listesinde — deney protokolü başladıktan sonra değişmeyen iki dosya.
