# Metrik doğruluğu — fark tablosu

Sertleştirme Blok 1 (`docs/v2-sertlestirme.md`). Bu dosya metrik × hata
kategorisi × sıklık tablosudur: hangi farkların tanım gereği olduğu, hangilerinin
düzeltildiği, hangilerinin bilinen sınırlılık olarak kaldığı.

**Durum: Blok 1 tamam.** CC (§1), uç nokta testleri ve düzeltmeler (§2), DCC
elle sayımı (§4), CAM kapsamı (§5), kohezyon karşılaştırması (§6). Tanım
kararları §3'te; scan şeması 3 ile uygulandı.

Referans seti: `projects.txt`, 12 proje, commit hash'iyle dondurulmuş. Tarama
kapsamı her projenin ürün kodu; `tests/` dizinleri dışlanır.

| | |
|---|---|
| Dosya | 673 (ayrıştırılamayan: 0) |
| Fonksiyon ve metot (radon'un bildirdiği) | 16 128 |
| Bunlardan RefactorLens raporunda yer alan | 13 386 |
| Sınıf (modül en üst düzeyi) | 1 678 |
| radon sürümü | 6.0.1 |

---

## 1. CC — radon ile fonksiyon bazında karşılaştırma

Üretmek için:

```bash
pip install radon==6.0.1
python experiments/hardening/compare_radon.py fetch
python experiments/hardening/compare_radon.py compare
```

Ham sonuç: `results/cc-radon.json`. Yöntem: her fonksiyon için iki tanımın
ayrıldığı yapılar sayılır, radon'un değeri bizimkine bu farklar eklenerek
tahmin edilir. Tahmin tutarsa fark açıklanmıştır. Sınıflandırıcının kendisi
`tests/test_hardening_compare.py` ile sınanır — hem elle hesaplanmış değerlerle
hem gerçek radon ile.

### Sonuç

**16 128 fonksiyonun 14 935'inde (%92.6) değer birebir aynı. Kalan 1 193 farkın
tamamı belgelenmiş tanım farklarıyla açıklanıyor; sınıflandırılmamış fark 0.**
Kabul kriteri sağlandı.

| Kategori | Etkilenen fonksiyon | Toplam puan (radon − biz) | Tanım | Karar |
|---|---:|---:|---|---|
| `assert` | 1 070 | +1 558 | radon her `assert`'e +1; `04 §2.3` saymaz | tanım farkı, kalır |
| `try_else` | 108 | +112 | radon `try/else`'e +1; biz `else`'i dal saymayız | tanım farkı, kalır |
| `loop_else` | 56 | +63 | radon `for/while-else`'e +1 | tanım farkı, kalır |
| `assert_contents` | 39 | −52 | radon `assert` içine hiç inmez; biz içindeki `and/or`, ternary, comprehension'ı sayarız | tanım farkı, kalır |
| `match_wildcard` | 0 | 0 | radon `case _` / `case x`'i düşer; biz her `case`'i sayarız | tanım farkı, yalnızca sentetik test |
| `except_star` | 0 | 0 | radon `except*`'ı (TryStar) hiç tanımaz; biz handler'ları sayarız | radon eksikliği, yalnızca sentetik test |

Proje kırılımı:

| Proje | Fonksiyon | Aynı | Fark | Sınıflandırılmamış |
|---|---:|---:|---:|---:|
| requests | 233 | 230 | 3 | 0 |
| httpx | 437 | 419 | 18 | 0 |
| rich | 846 | 807 | 39 | 0 |
| pydantic | 1 130 | 1 087 | 43 | 0 |
| fastapi | 244 | 220 | 24 | 0 |
| attrs | 166 | 163 | 3 | 0 |
| click | 479 | 472 | 7 | 0 |
| flask | 341 | 332 | 9 | 0 |
| sqlalchemy/orm | 2 093 | 1 916 | 177 | 0 |
| black | 377 | 335 | 42 | 0 |
| mypy | 5 074 | 4 469 | 605 | 0 |
| pandas/core | 4 708 | 4 485 | 223 | 0 |

**Okuma notları.**

- Farkların %90'ı `assert`. mypy tek başına 605 farkın 583'ünü `assert`'ten
  alıyor; mypy iç değişmezlerini `assert` ile yazar. Bu deyimi kullanan kodda
  CC değerlerimiz radon'dan sistematik olarak düşüktür ve bu **bilinçlidir**:
  `assert` `-O` ile kaldırılabilen bir denetimdir, programın yürütme yolu değil.
- `match_wildcard` ve `except_star` referans setinde hiç yok: setin tag'leri
  Python 3.8/3.9 desteğini sürdürüyor. Bu iki kategori yalnızca sentetik testle
  doğrulandı. Blok 1b korpusu 3.10+ bir proje içermeli.
- **Yöntemin tespit gücü sınandı.** Bu oturumda düzeltilen dekoratör hatası
  (§2) geri konunca betik 2 sınıflandırılmamış fark raporluyor (sqlalchemy 1,
  black 1). Yani "0" sonucu sınıflandırıcının her şeyi açıklamasından değil,
  gerçek uyuşmadan geliyor.
- `unmatched_radon_blocks` 0: radon'un bildirdiği her fonksiyon AST'de aynı
  ad ve satırla bulundu.

### Kapsama farkı (değer farkı değildir)

radon'un ölçtüğü 16 128 fonksiyonun 2 742'si raporumuzda yok. Hepsi tanım
gereği:

| Neden | Adet | Tanım |
|---|---:|---|
| dunder metot | 2 152 | `04 §2.1`: dunder'lar metot kümesinde değil |
| `@overload` taslağı | 455 | tip beyanı, gövde değil (§2'de düzeltildi) |
| modül düzeyinde `if`/`try` altında tanım | 119 | yalnızca en üst düzey taranır |
| iç içe sınıfın metodu | 16 | yalnızca en üst düzey sınıflar ölçülür |

Son iki satır **bilinen sınırlılıktır**, tanımda yazılı değildir: `if
TYPE_CHECKING:` / `else:` ya da `try: import ... except ImportError:` altında
tanımlı sınıflar ve iç içe sınıflar (`class Config:` gibi) hiç ölçülmüyor.
Referans setinde 135 fonksiyon; oran küçük ama sessiz. Açık karar olarak
`docs/STATUS.md`'de.

---

## 2. Uç nokta testleri ve düzeltilen uygulama hataları

`tests/test_metric_edges.py`, Blok 1 madde 3'ün her şüpheli noktası için. Her
düzeltme önce kırmızı testle yakalandı. Hiçbiri `docs/04` tanımını değiştirmez;
uygulamayı tanıma çeker. Fikstürlerin (`messy_project`, `layered_project`)
hiçbiri bu deyimleri içermediği için altın değerler ve FINDINGS-1/2'nin verisi
etkilenmez — iki fikstür suite'i ve altın değer testleri değişmeden yeşil.

"Referans setinde etki" sütunu, düzeltmeden önceki commit (`205a3b8`) ile
sonrasının 1 678 sınıf üzerindeki farkıdır.

| Metrik | Hata | Referans setinde etki |
|---|---|---|
| CC | Dekoratör, varsayılan argüman ve annotation ifadelerindeki karar noktaları fonksiyona yazılıyordu | 2 fonksiyon |
| NESTING | `except*` (TryStar) iç içelik düğümü değildi; gövdesine inilmiyordu | referans setinde yok |
| NOM, WMC | `@overload` taslakları ayrı metot sayılıyordu | 34 sınıf; en büyüğü `pandas.DataFrame` NOM −43 |
| LCOM4, DAM | `@staticmethod`'un ilk parametresi `self` sanılıyordu (`row.name` sınıf attribute'u oluyordu) | LCOM4 6 sınıfta arttı (`sqlalchemy.collection` 6→9), DAM 2 sınıfta değişti |
| LCOM4, DAM | İç içe sınıfın ve `self`'i yeniden bağlayan iç fonksiyonun `self.x`'i dıştaki metoda yazılıyordu | yukarıdakiyle birlikte |
| DCC | String annotation'lar (`"Order"`, `list["Order"]`) görülmüyordu — `TYPE_CHECKING` importlarının tek kullanım biçimi | 84 sınıf, +123 referans; rich 57 sınıf |
| DCC | `from m import Order as O` takma adı çözülmüyordu | 8 sınıf, +8 referans |
| Arayüz | Property getter/setter ve `@overload` aynı adı birden çok listeliyordu; `accessor_ratio` paydası şişiyordu | 57 sınıfta metot listesi, 26 sınıfta erişimci oranı |
| Arayüz | İç içe sınıfın `self.x = ...` atamaları dıştakinin arayüzüne giriyordu | 8 sınıf |

**Düzeltmenin kendisinin ürettiği hata, referans setinde yakalandı.** İlk
takma ad kuralı yalnızca ada bakıyordu. `requests.exceptions` içinde
`from urllib3.exceptions import HTTPError as BaseHTTPError` var: kod takma adı
tam da projedeki `HTTPError` ile çakışmayı önlemek için kullanıyor, kural bunu
tersine çevirip urllib3 sınıfını proje sınıfı sayıyordu. Kural, import
grafiğinin kullandığı proje-içi modül çözücüsüne bağlandı (göreli import her
zaman proje içi; mutlak import ancak çözücü onaylarsa). DCC'si değişen
sınıflardan örneklem elle incelendi (`rich.containers.Lines`,
`click.parser.ParsingState`, `rich.progress._TrackThread`,
`fastapi.openapi.models.Encoding`, `fastapi.security.oauth2.OAuth2PasswordBearer`,
`pydantic.color.Color`); hepsi gerçek proje sınıfı referansı. Aynı incelemeden
iki önlem daha çıktı: `Literal["Order"]` bir değerdir ve `Annotated[T, "meta"]`
içinde yalnızca `T` tiptir; ikisi de sayılmaz.

### Sabitlenen davranışlar (düzeltilmedi, test altında)

| Metrik | Davranış | Neden kalıyor |
|---|---|---|
| CC | Lambda gövdesi dıştaki fonksiyona yazılır | Lambda ayrı raporlanmaz; radon da aynı |
| CC | Her `case` sayılır, joker dahil | `04 §2.3`; radon farkı §1'de |
| NOM | Property getter ve setter iki metottur | İki ayrı gövde, iki ayrı CC |
| NOM | `Protocol`/`ABC` soyut metotları sayılır | Metot beyanıdır; CC 1 |
| LCOM4 | `@dataclass`, `NamedTuple`, `TypedDict`, `Enum` alanları ve `__slots__` attribute'tur | `04 §2.2` attribute kaynakları |
| DCC | Sınıf adıyla aynı adı taşıyan yerel değişken/parametre referans sayılır | İsim tabanlı çözüm (`resolution: inferred`); oranı DCC elle sayımında ölçülecek |
| DCC | Aynı adlı iki proje sınıfı tek referanstır; üçüncü parti sınıfla aynı ad proje sınıfı sayılır | Aynı sınırlılık; takma adda kapatıldı, düz adda kalıyor |

### Tanım ile uygulamanın çeliştiği iki yer — açık karar

Bu ikisi **düzeltilmedi**. Doküman tanım değişikliğini ayrı karara ve
`schema_version` artışına bağlıyor; hangi tarafın doğru olduğu da tartışmalı.
Mevcut davranış testle sabitlendi.

1. **LOC.** `04 §2.3`: "gövde satır sayısı (boş/yorum hariç)". Uygulama: `def`
   satırından son satıra, boş ve yorum dahil, dekoratör hariç. FINDINGS-1/2'deki
   LOC tahmin verisi uygulamanın tanımıyla toplandı.
2. **Metotsuz sınıfta LCOM4.** `04 §2.2`: `null`. Uygulama: `0`, gerekçesi
   docstring'de ("veri sınıfları meşrudur"). `null` invariant'ı ("hesaplanamayan
   metrik sıfır değil `null`") dokümanın tarafında; ama koku eşikleri ve delta
   mantığı `None` karşılaştırmasını ele almalı.

---

## 3. Tanım kararları — karara bağlandı

Blok 1 ölçümlerinin bıraktığı sorular `docs/v2-tanim-kararlari.md`'de karara
bağlandı ve scan şeması 3'te uygulandı (2026-09-16):

| Soru | Karar | Uygulama |
|---|---|---|
| LOC boş/yorum dahil mi (§2) | Hariç; docstring de hariç (K1, Goodhart) | şema 3 |
| Metotsuz sınıfta LCOM4 (§2) | `null` (K2, invariant) | şema 3 |
| DCC'de sınıfın kendi iç içe sınıfı (§4) | Sayılmaz (K3) | şema 3 |
| `god_class`'ın LCOM4 kapısı (§6) | Değişmez; yoğunluk ölçüsü v2.2'de (K4) | — |
| `if`/`try` altındaki tanımlar (§1) | Raporlanmaz; kimlik tasarımı v2.2'de (K5) | — |

Bu belgedeki §1, §2, §5 ve §6 sayıları şema 3'le yeniden üretildi ve
değişmedi (CC, CAM ve karşılaştırmaya giren sınıfların LCOM4'ü bu kararlardan
etkilenmez). §4 DCC sonuçları şema 3'e göre güncellendi.

---

## 4. DCC — elle sayım

Üretmek için (önce `compare_radon.py fetch`):

```bash
python experiments/hardening/dcc_sample.py worksheet   # okuma için ipuçları
python experiments/hardening/dcc_sample.py summary     # kararları uygular
```

Girdi: `results/dcc-sample.json` (örneklem), `dcc-verdicts.json` (kararlar).
Çıktı: `results/dcc-manual.csv` (referans başına bir satır),
`results/dcc-manual-summary.json`.

### Yöntem

**Örneklem.** Her projeden üç sınıf, sabit tohumla (`SEED = 20260915`),
katmanlı: düşük (DCC 0-2), orta (3-6), yüksek (7+) banttan birer tane. Toplam
36 sınıf, 154 sayılan referans. attrs'ta yüksek bant boş (sette 7+ DCC'li
sınıfı yok); o yuva düşük banttan dolduruldu ve aşağıda "yüksek" satırında
sayılıyor. Örneklem dosyası `--force` olmadan yeniden yazılamaz: kararlar
sınıflara bağlıdır.

**Karar.** Betik her sayılan ad için bağlanma kaynağını çıkarır (aynı
modülde sınıf, proje importu, harici import, yerel ad) ve bir ipucu verir.
İpucu karar değildir. Kural:

- İpucu `likely_tp` olan referans — adın bağlandığı satır bir proje importu ya
  da aynı modüldeki sınıf tanımıdır — doğru pozitif kabul edilir; örneklemden
  kontrol edildi.
- İpucu başka herhangi bir şey olan **her** referans (24 adet; çözücü
  düzeltmesinden önce pandas'ın 11 referansı da buradaydı ve onlar da okundu,
  toplam 35) ve betiğin ürettiği **her** yanlış negatif adayı (11 adet) kodda okunup
  `dcc-verdicts.json`'a gerekçesi ve satır numarasıyla yazıldı.
- `summary`, kararı eksik bir şüpheli ya da örneklemde karşılığı olmayan
  bayat bir karar görürse sonuç üretmeyi reddeder
  (`tests/test_hardening_dcc.py`).

Yanlış negatif aramak için üç aday türü tarandı: annotation dışı string'ler
(`cast("X")`, `TypeVar(bound="X")`), modül düzeyi tip takma adı üzerinden
dolaylı referans, ve aynı adı taşıyan iki proje sınıfının tek sayılması. Bu
üç türün dışındaki bir yanlış negatif (ör. `# type:` yorumu, `getattr` ile
string'den sınıf) aranmadı; duyarlılık bu türlerle sınırlıdır.

**Sınırlılık.** Kararları aracı geliştiren taraf verdi — FINDINGS-1'deki
"deneyi tasarlayan uyguladı" sınırlılığıyla aynı. Azaltma: her karar
dosya ve satırla yazılı, bağımsız biri `worksheet` çıktısıyla yeniden
denetleyebilir.

### Sonuç

| | |
|---|---:|
| Sayılan referans | 152 (şema 2: 154) |
| Doğru pozitif | 148 |
| Yanlış pozitif | 4 (şema 2: 6) |
| Yanlış negatif | 6 |
| **Kesinlik** (TP / sayılan) | **%97.4** (şema 2: %96.1) |
| **Duyarlılık** (TP / gerçek) | **%96.1** |
| DCC'si birebir doğru sınıf | 31 / 36 (şema 2: 30) |

Kararlar şema 2 ile okundu. K3 sınıfın kendi iç içe sınıflarını DCC'den
çıkardığında o kategorideki iki yanlış pozitif sayılmaz oldu; kararları
`dcc-verdicts.json`'da `resolved_by_schema_3` altında duruyor. Diğer kararlar
değişmedi. Örneklem bantları şema 2 DCC'siyle çekildi ve örneklem korunmak için
yeniden çekilmedi; hiçbir sınıf bu yüzden bant değiştirmezdi (tek değişen
sınıflar 4→3 ve 11→10, bant sınırlarını geçmiyor).

Çalışma kâğıdı DCC'yi kendi başına yeniden hesaplar. Şema 3'ün ilk koşusunda
K3 yalnızca `dcc()`'ye girdi, çalışma kâğıdına girmedi ve özet sessizce eski
sonucu üretti. Artık her örneklem sınıfında çalışma kâğıdının referans sayısı
`dcc()`'ye eşit olmak zorunda; değilse betik durur.

| Bant | Sınıf | TP | FP | FN | Birebir doğru |
|---|---:|---:|---:|---:|---:|
| düşük (0-2) | 12 | 8 | 0 | 0 | 12 |
| orta (3-6) | 12 | 42 | 0 | 1 | 11 |
| yüksek (7+) | 12 | 98 | 4 | 5 | 8 |

**Hatalar yüksek DCC'de toplanıyor** — ama örneklemde hiçbiri `dcc` eşiğini
(7) geçirmiyor ya da altına indirmiyor: yanlış ölçülen dört yüksek sınıf
ölçülen→gerçek 10→15, 9→8, 12→11, 10→8. Koku kararı değişmezdi. Toplam
ölçülen (152) ile gerçek (154) yakın, ama bu yanlış pozitif ve negatiflerin
birbirini kısmen götürmesinden gelir; doğruluk göstergesi değildir.

### Kategoriler

| Tür | Kategori | Adet | Örnek | Durum |
|---|---|---:|---|---|
| ~~FP~~ | `own_local_class` | 0 (şema 2: 2) | `SubqueryLoader._SubqCollections`: sınıfın kendi iç içe sınıfı; `ValidatedFunction` metodu içinde tanımlı `DecoratorBaseModel` | **şema 3 K3 ile giderildi** |
| FP | `external_same_name` | 2 | `flask.sansio.App`: werkzeug `Response`; `click.Option`: `t.Tuple` (typing) ile `click.types.Tuple` | isim tabanlı çözüm sınırlılığı |
| FP | `local_name` | 1 | `SubqueryLoader`: yerel değişken `collection` ile `collections.collection` sınıfı | isim tabanlı çözüm sınırlılığı |
| FP | `module_same_name` | 1 | `SubqueryLoader`: `query` modülü ile metot içi `class query` | isim tabanlı çözüm sınırlılığı |
| FN | `type_alias` | 5 | `fastapi.Components`: `SecurityScheme = Union[APIKey, HTTPBase, ...]` — tek sınıf | sınırlılık |
| FN | `same_name_merged` | 1 | `fastapi.HTTPDigest`: iki farklı `HTTPBase` tek sayılıyor | sınırlılık |

Yanlış negatiflerin 5'i tek sınıftan; sınıf bazında FN yalnızca 2/36 sınıfta
görülüyor. Doğru pozitiflerin 19'u modül üzerinden nitelikli erişim
(`orm_util.PathRegistry`), 2'si maskelenmiş harici erişim (httpx sınıfı hem
`httpcore.Request` hem kendi `Request`'ini kullanıyor; ad bir kez sayıldığı
için sonuç değişmiyor).

### Elle sayımın yakaladığı uygulama hatası

Çalışma kâğıdı pandas referanslarını "harici import" diye işaretledi. Sebep
DCC değil, import çözücüsüydü: tarama kökü `pandas/core` iken kod
`pandas.core.frame` yazar ve çözücü yalnızca `core`'u kırpıyordu. Etkisi DCC'den
büyüktü: `pandas/core` taramasında import grafiği **0 kenar** veriyordu (1182
mutlak importun 1179'u kayıp), yani Ca, Ce, instability ve döngüler sessizce
boştu. Düzeltildi (`root_package_name`, ayrı commit): pandas/core 0 → 1189 kenar,
diğer 11 projede kenar sayısı birebir aynı.

### Neden `external_same_name` şimdi düzeltilmedi

Adın modülde yalnızca harici bir importa bağlandığı durumda saymamak iki
yanlış pozitifi kapatır. Ama bu, çözücünün proje importunu tanımasına tam
bağımlı hale getirir: çözücü düzeltmesinden önce aynı kural bu örneklemde 11
doğru pozitifi (pandas) yanlış negatife çevirirdi. Düzeltmeden sonra da
namespace paketleri, `sys.path` hileleri ve vendored kopyalar çözücünün
göremediği yerlerdir. 154'te 2'lik bir kazanç için DCC'yi çözücünün
hatalarına bağlamak şu an iyi bir takas değil; ölçüm korpusu (Blok 1b)
genişleyince yeniden tartılır.

---

## 5. CAM — annotation kapsamı

Üretmek için: `python experiments/hardening/cam_coverage.py` →
`results/cam-coverage.json`.

CAM parametre **tipleri** üzerinden tanımlıdır; annotation kapsamı 0.7'nin
altındaysa `null` döner. Rapordaki `no_annotated_parameters` sebebi iki durumu
birleştirir — hiç parametre yok, ya da parametre var ama hiç annotation yok —
betik bunları ayırır. (Etiket her iki durum için de doğrudur; ayrım yalnızca bu
analiz için gerekli, uygulamada değişiklik yapılmadı.)

| Durum | Sınıf | Pay |
|---|---:|---:|
| Hesaplandı | 786 | %46.8 |
| — bunlardan ayırt edici (parametreli ≥ 2 metot) | 455 | %27.1 |
| Kapsam eşiğin altında (0 < kapsam < 0.7) | 86 | %5.1 |
| Parametre var, annotation yok | 86 | %5.1 |
| Parametre yok | 720 | %42.9 |
| **Toplam** | **1 678** | |

| Proje | Sınıf | Hesaplandı | Ayırt edici | Medyan kapsam |
|---|---:|---:|---:|---:|
| requests | 44 | %0 | 0 | 0.0 |
| attrs | 33 | %3 | 1 | 0.0 |
| fastapi | 89 | %10 | 3 | 1.0 |
| pandas/core | 246 | %29 | 44 | 0.64 |
| pydantic | 179 | %32 | 33 | 1.0 |
| sqlalchemy/orm | 256 | %33 | 67 | 1.0 |
| httpx | 85 | %44 | 14 | 1.0 |
| black | 44 | %45 | 18 | 1.0 |
| rich | 170 | %55 | 43 | 1.0 |
| click | 66 | %65 | 24 | 1.0 |
| mypy | 420 | %79 | 181 | 1.0 |
| flask | 46 | %83 | 27 | 1.0 |

**Okuma.**

- **Hesaplanan CAM'lerin %42'si hiçbir şey söylemiyor.** Parametreli tek
  metodu olan sınıfta CAM tanım gereği 1.0'dır. 786 hesaplanmış değerin 331'i
  bu durumda.
- **Eşik neredeyse etkisiz.** Kapsam iki kutuplu: bir proje ya baştan sona
  annotation'lıdır (medyan 1.0) ya da hiç değildir (requests, attrs). Eşiği
  0.5 / 0.7 / 0.9 yapmak hesaplanan sınıf sayısını 837 / 786 / 761 yapar; fark
  neredeyse tamamen sqlalchemy ve pandas'tan gelir. CAM'in kullanılabilirliğini
  eşik değil **projenin annotation alışkanlığı** belirliyor.
- **Sınıfların %43'ünde parametre yok** — çoğu istisna sınıfı, enum, veri
  taşıyıcı. Bunlarda CAM kavramsal olarak tanımsızdır, eksik değildir.
- **Dogfooding gözleminin sebebi annotation değil.** `docs/STATUS.md`'deki
  "CAM kendi deposunda %80 hesaplanamıyor" gözlemi aynı betikle ölçüldü:
  66 sınıfın 53'ünde parametre yok (veri sınıfları, rapor modelleri), annotation
  eksikliğinden hesaplanamayan sınıf **0**; ayırt edici CAM 6 sınıfta. Yani
  yoğun annotation'lı bir kodda bile CAM'i sınırlayan şey parametresiz sınıf
  deyimidir.
- Blok 1b girdisi: CAM'in kapsama tablosunda "ayırt edici" oranı (%27)
  esas alınmalı, "hesaplanabilir" oranı (%47) değil.

---

## 6. Kohezyon — `cohesion` aracı ile sıralama korelasyonu

Üretmek için: `pip install cohesion==1.2.0`, sonra
`python experiments/hardening/compare_cohesion.py` →
`results/cohesion-spearman.json`.

İki araç farklı yapı ölçer, bu yüzden mutlak değer değil sıra karşılaştırılır:

| | LCOM4 (bizde) | `cohesion` 1.2.0 |
|---|---|---|
| Ne | Metot–attribute–çağrı grafiğinin bileşen sayısı | Metotların kullandığı sınıf değişkeni yoğunluğu, % |
| Yön | Yüksek = kötü | Yüksek = iyi |
| Metotlar arası çağrı | Bağ sayılır | Görülmez |
| Dunder metotlar | Hariç | `__init__` dahil |
| Ölçtüğü | **Bağlantı** | **Yoğunluk** |

Karşılaştırmaya giren: en az iki farklı adlı metodu ve en az bir sınıf
değişkeni olan 675 sınıf. (İlk koşuda filtre NOM'a bakıyordu; property
getter/setter NOM'da iki, LCOM4 grafiğinde tek düğüm olduğu için
`flask.SessionMixin` gibi fiilen tek metotlu sınıflar karşılaştırmaya girip
sahte sapma üretti. Filtre farklı metot adına çevrildi.)

### Sonuç

**Spearman ρ = −0.62** (675 sınıf), beklenen negatif yönde. Proje bazında
−0.35 (black) ile −0.72 (httpx, pandas) arası; fastapi yalnızca 3 sınıfla
anlamsız.

İki tanım aynı yöne işaret ediyor ama örtüşmüyor. Soru sapmaların uygulama
hatasından mı tanım farkından mı geldiği — en çok ayrışan **25 sınıfın 25'i**
tanım farkıyla açıklandı, açıklanamayan 0:

| Kategori | Adet | Ne oluyor | Örnek |
|---|---:|---|---|
| `call_edges` | 20 | Ortak bir yardımcı metot her metodu çağrıyla bağlıyor; çağrılar çıkarılınca sınıf parçalanıyor. LCOM4 = 1, yoğunluk %4-13 | `mypy.TypeChecker`: 217 metot, çağrısız grafikte 86 bileşen |
| `isolated_methods` | 5 | Hiçbir attribute'a dokunmayan metotlar LCOM4'te ayrı bileşen; `cohesion` onları yalnızca yoğunluğu biraz düşüren metot sayar | `mypy.TypeMeetVisitor`: 24 metodun 20'si `self.s` kullanıyor, LCOM4 = 5, yoğunluk %72 |

**Sınıflandırıcının kendi hatası.** İlk sürüm LCOM4 = 1 ve düşük yoğunluklu
sınıfları "birkaç ortak attribute her şeyi bağlıyor" (`hub_attributes`) diye
etiketliyordu — 18 sınıf. Bu bir **varsayımdı**, ölçülmemişti. Grafiğin
çağrısız hali hesaplanınca 18'inin de parçalandığı görüldü (`SubexpressionFinder`
42 metot, 42 bileşen: hiç ortak attribute yok). Bağlayan şey çağrılardı.
Kategori artık ölçülerek atanıyor ve iki durum testte ayrı sınıflara düşüyor.

### `god_class` için sonucu

`god_class` kokusu `nom ≥ 20`, `wmc ≥ 50` **ve** `lcom4 ≥ 3` ister. Çağrı
kenarları LCOM4'ü düşürdüğü için:

| | Sınıf |
|---|---:|
| Boyut koşulunu geçen (NOM ve WMC) | 107 |
| `god_class` ateşlendi | 71 |
| LCOM4 koşulunda elendi | 36 |
| — **yalnızca çağrı kenarları yüzünden** elendi | **34** |

Referans setinin büyük sınıflarının **üçte biri** god class kokusundan
kaçıyor ve bunun neredeyse tek sebebi ortak yardımcı metot deyimi: ziyaretçi
(visitor) sınıfları, `self.add(...)` / `self.fail(...)` gibi bir merkezden
dağılan sınıflar. Örnekler: `mypy.TypeChecker` (NOM 217), `pydantic.GenerateSchema`
(62), `pandas.StringMethods` (50), `sqlalchemy.JoinCondition` (37).

Bu **uygulama hatası değil**: Hitz ve Montazeri LCOM4'ü çağrıyı bağ sayarak
tanımlar ve `docs/04` bu tanımı izler. Soru tanımın kendisinin
`god_class` için doğru kapı olup olmadığı — ya da kapının bağlantı yerine
yoğunluğa mı bakması gerektiği. **Karar (K4, §3):** kapı şema 3'te değişmez;
yerine konacak yoğunluk ölçüsü `docs/v2.2-python-metrikleri.md` §5b'de dokuz
madde şablonuyla tasarlanacak. Blok 1b dağılım tablosu bu 34 sınıfı ayrı satır
olarak raporlar.
