# Metrik doğruluğu — fark tablosu

Sertleştirme Blok 1 (`docs/v2-sertlestirme.md`). Bu dosya metrik × hata
kategorisi × sıklık tablosudur: hangi farkların tanım gereği olduğu, hangilerinin
düzeltildiği, hangilerinin bilinen sınırlılık olarak kaldığı.

**Durum:** CC tamam. Uç nokta testleri ve düzeltmeler tamam. Kohezyon (Spearman,
`cohesion` aracı), DCC elle sayımı (30-50 sınıf) ve CAM annotation kapsamı
**henüz yapılmadı** — bkz. son bölüm.

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

## 3. Henüz yapılmayanlar (Blok 1'in kalanı)

- **Kohezyon:** `cohesion` aracı ile sınıf bazında Spearman sıralama
  korelasyonu; büyük sapmalar elle.
- **DCC elle sayım:** her projeden 3-4 sınıf, toplam 30-50; yanlış
  pozitif/negatif kategorileri ve oranı. README "Limitations"a işlenir.
- **CAM:** annotation kapsamı dağılımı (projelerin yüzde kaçında hesaplanabiliyor).
- LOC ve boş sınıf LCOM4 kararları (§2).
