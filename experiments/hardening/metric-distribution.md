# Metrik dağılımı — kalibrasyon korpusu

Sertleştirme Blok 1b, madde 2 (`docs/v2-sertlestirme.md`). 26 proje, scan
şeması 3, kullanıcının varsayılan taraması.

**Bu belge eşik değiştirmez.** Mevcut varsayılanların gerçek kodda nereye
düştüğünü gösterir. Eşik kararları ayrı bir kayıtla verilir (bkz. son bölüm).

```bash
python experiments/hardening/corpus.py fetch     # bir kez, ~850 MB
python experiments/hardening/distribution.py     # ~60 s
```

Çıktılar: `results/metric-distribution.json` (proje başına tüm istatistikler)
ve `results/metric-distribution-tables.md` (aşağıdaki tablolar aynı dosyadan
alındı). İkisi de tekrar üretildiğinde birebir aynıdır.

## Yöntem

- **Proje başına persentil, projelerin medyanı.** Sınıfların %47'si netbox ve
  yt-dlp'den geliyor (`corpus.md` Bulgu 1). Havuzlanmış değer karşılaştırma için
  yanında verilir; farkı tablolarda görülüyor (DCC).
- **Küçük örneklem:** bir proje, o metrikte en az 30 hesaplanmış değeri varsa
  katılır. "Proje" sütunu kaç projenin katıldığını söyler.
- **`null`** dağılıma girmez; "null" sütunu projelerin medyan `null` payıdır.
- **Eşik kuralı** aracın kendisiyle aynı: `değer >= eşik`.
- **Doğrulama:** `god_class` kapısının AST'den hesaplanan ateşlenme sayısı (96)
  raporların ürettiği `god_class` kokusu sayısına birebir eşit.

Scan şeması 3. Proje başına persentil, projelerin medyanı; projenin katılması için metrikte en az 30 değer.

### Dağılım — tüm korpus

| Metrik | Birim | Proje | p50 | p75 | p90 | p95 | p99 | null | havuz p90 | havuz p99 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CC | function | 25 | 2 | 4 | 8 | 12 | 20 | %0.0 | 8 | 24 |
| LOC | function | 25 | 7 | 17 | 29.50 | 44.95 | 85.58 | %0.0 | 31 | 91 |
| PARAMS | function | 25 | 1 | 2 | 4 | 4.35 | 7 | %0.0 | 4 | 8 |
| NESTING | function | 25 | 1 | 1 | 2 | 3 | 4 | %0.0 | 2 | 4 |
| NOM | class | 24 | 1 | 2 | 5.55 | 9.93 | 17.60 | %0.0 | 5 | 24.63 |
| WMC | class | 24 | 1.25 | 5.50 | 19 | 31 | 66.53 | %0.0 | 15 | 87 |
| LCOM4 | class | 18 | 1 | 2 | 3 | 4.65 | 9.35 | %32.0 | 3 | 11.57 |
| DCC | class | 24 | 1 | 2 | 4.25 | 5.40 | 9.68 | %0.0 | 7 | 21 |
| DAM | class | 21 | 0 | 0 | 0.25 | 0.47 | 1 | %21.6 | 1 | 1 |
| CAM | class | 12 | 0.81 | 1 | 1 | 1 | 1 | %61.6 | 1 | 1 |
| Ca | module | 17 | 1 | 4 | 10 | 20 | 34.48 | %0.0 | 9 | 62 |
| Ce | module | 17 | 3 | 6 | 10 | 12 | 17.60 | %0.0 | 12 | 30 |
| I | module | 17 | 0.67 | 0.83 | 1 | 1 | 1 | %4.5 | 1 | 1 |

### p90 tür bazında

| Metrik | library | cli | web_app | ml_research |
|---|---:|---:|---:|---:|
| CC | 8.50 (10) | 9.50 (6) | 6 (5) | 8.50 (4) |
| LOC | 30 (10) | 34.95 (6) | 25 (5) | 33.90 (4) |
| PARAMS | 4 (10) | 3 (6) | 3 (5) | 4 (4) |
| NESTING | 2 (10) | 2.50 (6) | 2 (5) | 2.50 (4) |
| NOM | 7.80 (10) | 5.85 (6) | 4 (5) | 5 (3) |
| WMC | 25 (10) | 20 (6) | 12 (5) | 21.20 (3) |
| LCOM4 | 5 (7) | 3 (4) | 3 (5) | 2.50 (2) |
| DCC | 4.80 (10) | 3 (6) | 7 (5) | 2.50 (3) |
| DAM | 0.88 (8) | 0.47 (6) | 0 (5) | 0.50 (2) |
| CAM | 1 (7) | 1 (2) | 1 (3) | — (0) |
| Ca | 13.20 (5) | 6 (5) | 10 (5) | 8.40 (2) |
| Ce | 13 (5) | 7 (5) | 10 (5) | 8.50 (2) |
| I | 0.92 (5) | 0.89 (5) | 1 (5) | 1 (2) |

### Mevcut eşikler — eşiği karşılayan pay

Proje başına pay; medyan ve aralık. Eşiğin denk geldiği persentil ≈ 100 − medyan pay.

| Eşik | Proje | medyan | min | max | library | cli | web_app | ml_research | havuz |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CC>=10 (warn) | 25 | %6.9 | %1.2 | %18.5 | %8.1 | %9.5 | %3.7 | %7.5 | %6.7 |
| CC>=20 (critical) | 25 | %1.2 | %0.0 | %6.1 | %1.7 | %2.0 | %0.6 | %2.4 | %1.6 |
| PARAMS>=5 (warn) | 25 | %5.1 | %1.1 | %31.3 | %9.3 | %3.5 | %2.1 | %6.9 | %5.7 |
| NESTING>=4 (warn) | 25 | %2.6 | %0.0 | %8.8 | %3.4 | %2.9 | %2.0 | %3.7 | %2.7 |
| NOM>=20 (warn) | 24 | %1.3 | %0.0 | %18.7 | %2.9 | %1.4 | %0.9 | %1.0 | %1.5 |
| WMC>=50 (warn) | 24 | %2.7 | %0.0 | %21.1 | %6.0 | %1.8 | %1.1 | %4.0 | %2.2 |
| LCOM4>=2 (warn) | 18 | %32.1 | %11.1 | %61.8 | %42.6 | %23.9 | %32.2 | %24.3 | %27.6 |
| LCOM4>=4 (critical) | 18 | %7.5 | %1.2 | %29.1 | %12.5 | %6.1 | %7.9 | %3.1 | %7.5 |
| DCC>=7 (warn) | 24 | %4.8 | %0.0 | %25.2 | %7.9 | %2.1 | %11.5 | %2.8 | %12.3 |
| LOC>=40 (long_method) | 25 | %6.5 | %2.2 | %36.6 | %6.6 | %8.5 | %3.1 | %7.3 | %6.5 |

### `god_class` kapısı (K4)

| Tür | Boyut koşulunu geçen | Ateşlendi | LCOM4'te elendi | Yalnız çağrı kenarı yüzünden |
|---|---:|---:|---:|---:|
| library | 67 | 52 | 15 | 15 |
| cli | 67 | 31 | 36 | 34 |
| web_app | 23 | 12 | 11 | 11 |
| ml_research | 2 | 1 | 1 | 1 |
| all | 159 | 96 | 63 | 61 |

### Koku oranları — 1000 birim başına, projelerin medyanı

`god_class`, `data_class`: 1000 sınıf başına; diğerleri 1000 fonksiyon başına.

| Koku | library | cli | web_app | ml_research |
|---|---:|---:|---:|---:|
| data_class | 0 | 2.15 | 0 | 0 |
| feature_envy_candidate | 57.09 | 49.99 | 77.12 | 67.70 |
| god_class | 17.35 | 1.29 | 1.51 | 0 |
| long_method | 45.88 | 59.10 | 18.31 | 58.82 |
| too_many_params | 92.81 | 33.85 | 19.72 | 63.26 |

---

## Bulgular

### 1. Fonksiyon eşikleri makul: projelerin medyanında üst %3-7

| Eşik | Karşılayan pay (proje medyanı) | Denk geldiği persentil | Projeler arası aralık |
|---|---:|---:|---|
| CC ≥ 10 (warn) | %6.9 | ≈ p93 | %1.2 (segment-anything) – %18.5 (black) |
| CC ≥ 20 (critical) | %1.2 | ≈ p99 | %0.0 – %6.1 (black) |
| PARAMS ≥ 5 | %5.1 | ≈ p95 | %1.1 (netbox) – %31.3 (fastapi) |
| NESTING ≥ 4 | %2.6 | ≈ p97 | %0.0 – %8.8 (black) |
| LOC ≥ 40 | %6.5 | ≈ p93.5 | %2.2 (awscli) – %36.6 (fastapi) |

Tipik bir projede fonksiyonların %3-7'si uyarı alıyor — bir uyarı eşiğinden
beklenen davranış. CC'nin `critical` eşiği p99'a oturuyor. Sorun ortalamada değil
**uçlarda**: aynı eşik black'te fonksiyonların beşte birini, awscli'de elliden
birini işaretliyor. black'in uç değerleri tek tek incelenmedi; fastapi'ninkiler
incelendi ve büyük ölçüde ölçünün bir sınırından geliyor (Bulgu 5).

### 2. LCOM4 uyarı eşiği bir uyarı değil

**LCOM4 ≥ 2, metodu olan sınıfların %32'sini işaretliyor** (≈ p68). Diğer
bütün uyarı eşikleri p93-p99 arasındayken bu, sınıfların üçte birini "uyarı"
seviyesine koyuyor. Korpusun p90'ı 3, p95'i 4.65. `critical` (4) %7.5 ile
diğer uyarı eşiklerinin yerine denk geliyor.

Kütüphanelerde oran %43 (sqlalchemy %62, pandas %60). Bu sınıfların neden
bölünmüş göründüğü tek tek incelenmedi; `README` "LCOM4 and data classes"
sınırlılığı (attribute paylaşmayan erişimciler) olası açıklamalardan biri.

### 3. DCC: ağırlıklandırma burada fark ediyor, tür de

- **Havuz ile proje medyanı ayrışıyor.** DCC p90: projelerin medyanı 4.25,
  havuz 7. DCC ≥ 7 payı: projelerin medyanı %4.8, havuz %12.3. Havuz netbox ve
  saleor'un Django sınıflarına kalibre olur; proje ağırlıklandırması tam bunun
  için seçildi.
- **Tür bağımlı.** DCC ≥ 7: web_app %11.5, library %7.9, ml_research %2.8, cli
  %2.1. p90: web_app 7, cli 3. Web uygulamasında bir view/serializer'ın beş-yedi
  model sınıfına bakması tasarım gereği; `thresholds.by_layer` bu yüzden var ama
  varsayılan olarak boş.
- Uç: mypy'de sınıfların %25'i DCC ≥ 7.

### 4. Sınıf boyut eşikleri tutucu; dağılım ağır kuyruklu

NOM ≥ 20 %1.3 (≈ p99), WMC ≥ 50 %2.7 (≈ p97). Tipik projede sınıfların yarısının
dunder dışında en fazla bir metodu var (NOM p50 = 1); LCOM4 `null` payı
(metotsuz sınıflar) projelerin medyanında %32. Uçta pandas:
sınıfların %19'u NOM ≥ 20, %21'i WMC ≥ 50.

### 5. K1'in sınırı: imzaya gömülü belge

fastapi'nin uçları (PARAMS %31, LOC ≥ 40 %37) büyük ölçüde bir deyimden
geliyor. fastapi parametrelerini imzada belgeliyor:
`Annotated[Any, Doc("""...""")]`. K1 docstring'leri dışlar ama bu string'ler
docstring değil, imzanın parçası. Ölçüm: `param_functions.Query`'nin LOC'u 300,
bunun 269 satırı imza ve 108'i `Doc()` string'i. fastapi genelinde kod
satırlarının **%38'i** `Doc()` string'lerinin içinde; 11 fonksiyon 40 satırı
yalnızca bu yüzden aşıyor.

Şema 3'te düzeltilmedi: tanımı değiştirmek şema 4 demek ve bu deyim tek bir
proje ailesine ait (fastapi, typer). K1'in bir sonraki gözden geçirmesine
girdi. PARAMS'taki yükseklik ise ölçü hatası değil: `Query` gerçekten 29
parametre alıyor — framework'ün bildirimsel API yüzeyi. Bu madde 4'ün
(framework giriş noktaları) konusu.

### 6. CAM ve DAM tabloda da ayırt edici değil

- **CAM:** yalnızca 12 proje yeterli değer taşıyor; p75'ten itibaren her
  persentil 1.0. CAM, hesaplanabildiği yerde tavana yapışıyor (metric-accuracy
  §5: tek parametreli metotlu sınıfta tanım gereği 1.0).
- **DAM:** p50 ve p75 0. Kütüphanelerde p90 0.88 (private attribute kültürü),
  web uygulamalarında p90 bile 0. Dogfooding'deki "DAM Python'da ölçtüğü şey yok"
  gözlemi web uygulamaları için tamamen, kütüphaneler için kısmen doğru.

### 7. Koku oranları türe göre 5-10 kat değişiyor

1000 birim başına, projelerin medyanı:

- `too_many_params`: library 93, ml_research 63, cli 34, web_app 20 (framework
  giriş noktası kuralından sonra; öncesinde cli 35, web_app 21 —
  `entry-points.md`).
- `god_class` (1000 sınıf başına): library 17, cli 1.3, web_app 1.5,
  ml_research 0.
- `long_method`: cli 59, ml_research 59, library 46, web_app 18.

Aynı eşik türler arasında çok farklı gürültü üretiyor; fonksiyon düzeyinde en
sessiz tür web uygulamaları. Nedeni bu belgede incelenmedi.

### 8. `god_class` kapısı: korpusun tamamında %38

Boyut koşulunu geçen 159 sınıfın 63'ü LCOM4'te eleniyor, 61'i yalnızca çağrı
kenarları yüzünden. cli'de oran yarıdan fazla (67 sınıfın 34'ü). K4 kararıyla
v2.2'ye kadar bilinçli olarak açık.

---

## Eşik kararı için girdi

Bu tablo eşik değiştirmez; karar ayrı kayda yazılır. Eşik değişikliğinin
`schema_version` gerektirip gerektirmediği o kayıtta değerlendirilmeli: metrik
değerleri değişmez, ama v2 şema notu (`model.py`) eşiklerin `verify`
deltalarının anlamını değiştirdiğini sürüm artışı gerekçesi saymıştı.
Verinin söylediği:

| Eşik | Durum | Aday |
|---|---|---|
| CC warn/critical, PARAMS, NESTING, LOC 40 | p93-p99; uyarı eşiği gibi davranıyor | korunur |
| NOM 20, WMC 50 | p97-p99; tutucu | korunur |
| **LCOM4 warn 2** | **p68; sınıfların üçte biri** | p90'a (3) ya da p95'e (4) çekilmeli |
| DCC 7 | proje medyanında p95, web_app'te p88 | genel değer korunur; tür/katman farkı `by_layer` ile |
| `too_many_params` | giriş noktaları artık hariç (madde 4); kalan gürültü dekoratörsüz API yüzeyi (pandas, fastapi `Query`) | eşik kararında; yalnızca-anahtar parametreler ayrı düşünülebilir (`entry-points.md`) |
| CAM, DAM | ayırt edici değil | eşik değil, ölçünün kendisi v2.2'de |

Madde 4 (framework giriş noktaları) tamamlandı ve tablo onunla yeniden
üretildi. Kararın önünde **madde 3** (kapsama tablosu — CAM, ölçülen mantık
payı ve LCOM4 `null` payı hazır) kaldı.
