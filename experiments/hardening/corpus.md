# Kalibrasyon korpusu — envanter

Sertleştirme Blok 1b, madde 1 (`docs/v2-sertlestirme.md`). Eşikler bu
korpusun dağılımından türetilecek. Bu belge korpusun **ne olduğunu** ve
RefactorLens'in onun **ne kadarını gördüğünü** kayda geçirir; dağılım tablosu
(madde 2) tanım kararlarından sonra ayrı belgede üretilecek.

```bash
python experiments/hardening/corpus.py fetch       # ~850 MB, .cache/
python experiments/hardening/corpus.py inventory   # ~60 s, tek çekirdek
```

Girdi `corpus.txt`; çıktı `results/corpus-inventory.json` (tekrar üretildiğinde
birebir aynı) ve `results/corpus-timing.json` (ortama bağlı).

## Tasarım kararları

**Tür dengeli.** Blok 1'in 12 projesi tamamen kütüphaneydi; dogfooding
metriklerin kod deyimine göre saptığını gösterdi (typer komutları
`too_many_params`'ı şişirdi). Korpus dört türde en az beşer proje içerir.
black ve mypy, birincil rolleri komut satırı aracı olduğu için `cli`.

**Doğruluk seti değişmez.** `projects.txt` Blok 1'in sayılarına bağlıdır;
korpus onu birebir kapsar (commit, kapsam, dışlama) ve bunu
`tests/test_hardening_corpus.py` sınar.

**Kapsam kullanıcının varsayılan taramasıdır.** Varsayılan config `tests/`,
`migrations/`, `venv/`, `build/`, `dist/` dışlar; korpus da. Eşik kullanıcının
varsayılan taramasına uygulanacağı için başka bir kapsamda kalibre etmek onu
yanlış yere oturtur. Ek dışlama yalnızca varsayılanın kaçırdığı üretilmiş ya da
kopya kod içindir: mealie `alembic/` (migration), pydantic `v1/` (gömülü kopya),
mypy `test/` ve `typeshed/`. Django migration'ları varsayılan tarafından zaten
dışlanıyor — saleor'da 1452, netbox'ta 309, healthchecks'te 192 dosya; dahil
olsalardı web uygulamaları gerçekte olduğundan çok daha basit fonksiyonlu
görünürdü.

**"generated" başlığı kanıt değil.** Başlığında "generated" geçen dosyalar tek
tek okundu: netbox formları, saleor GraphQL tipleri, yt-dlp modülleri elle
yazılmış (kelime yorumda geçiyor); mealie'nin `schema/__init__.py`'leri
yalnızca yeniden dışa aktarım, sınıf ya da fonksiyon içermiyor. Dışlanmadılar.

**Config tuzağı.** `.cache/` bu deponun içinde; `load_config` yukarı doğru
arayıp RefactorLens'in kendi `rlens.yaml`'ını (`include: ["src/"]`) bulurdu ve
her tarama sessizce boş çıkardı. Betik config'i proje başına açıkça yazar.

## Envanter

| Proje | Tür | Modül | Sınıf | Modül fonk. | Metot | Mantık satırı | Ölçülen |
|---|---|---:|---:|---:|---:|---:|---:|
| requests | library | 18 | 44 | 72 | 104 | 4 686 | %96.4 |
| httpx | library | 23 | 85 | 67 | 242 | 7 757 | %97.2 |
| rich | library | 78 | 170 | 86 | 496 | 19 658 | %87.4 |
| pydantic | library | 77 | 179 | 299 | 457 | 25 628 | %91.9 |
| fastapi | library | 44 | 89 | 85 | 49 | 16 796 | %96.9 |
| attrs | library | 19 | 33 | 90 | 27 | 5 168 | %98.1 |
| click | library | 16 | 66 | 111 | 243 | 9 190 | %96.7 |
| flask | library | 24 | 46 | 65 | 225 | 8 358 | %97.1 |
| sqlalchemy | library | 38 | 256 | 227 | 1 446 | 59 324 | %98.9 |
| pandas | library | 179 | 246 | 853 | 3 143 | 145 998 | %98.5 |
| black | cli | 25 | 44 | 231 | 132 | 10 832 | %96.9 |
| mypy | cli | 132 | 420 | 965 | 3 671 | 88 789 | %98.4 |
| httpie | cli | 78 | 105 | 174 | 201 | 8 056 | %82.5 |
| yt-dlp | cli | 1 045 | 2 323 | 458 | 4 329 | 204 527 | %99.5 |
| awscli | cli | 426 | 1 394 | 961 | 4 626 | 93 369 | %97.1 |
| pipx | cli | 49 | 91 | 442 | 125 | 11 796 | %96.5 |
| healthchecks | web_app | 225 | 214 | 300 | 410 | 12 837 | %95.0 |
| netbox | web_app | 777 | 4 116 | 541 | 2 610 | 125 008 | %97.4 |
| saleor | web_app | 1 164 | 2 535 | 2 665 | 3 957 | 170 426 | %97.7 |
| redash | web_app | 167 | 247 | 409 | 937 | 22 522 | %93.4 |
| mealie | web_app | 395 | 662 | 279 | 1 092 | 25 914 | %97.8 |
| nanogpt | ml_research | 15 | 6 | 5 | 12 | 801 | %44.1 |
| yolov5 | ml_research | 53 | 99 | 266 | 206 | 12 656 | %96.5 |
| detectron2 | ml_research | 141 | 213 | 321 | 580 | 29 047 | %98.6 |
| whisper | ml_research | 14 | 36 | 37 | 75 | 3 497 | %98.7 |
| segment-anything | ml_research | 15 | 19 | 24 | 57 | 2 309 | %99.7 |
| **toplam** | | **5 237** | **13 738** | **10 033** | **29 452** | **1 124 949** | **%97.6** |

Ayrıştırılamayan dosya: **0**. Tarama süresi (`arch` açık, tek çekirdek): toplam 60 s, en yavaş yt-dlp 12 s (1 045 modül).

| Tür | Proje | Modül | Sınıf | Fonksiyon + metot | Mantık satırı | Ölçülen |
|---|---:|---:|---:|---:|---:|---:|
| library | 10 | 516 | 1 214 | 8 387 | 302 563 | %97.0 |
| cli | 6 | 1 755 | 4 377 | 16 315 | 417 369 | %98.2 |
| web_app | 5 | 2 728 | 7 774 | 13 200 | 356 707 | %97.3 |
| ml_research | 5 | 238 | 373 | 1 583 | 48 310 | %97.2 |

## Bulgu 1 — Dağılım proje bazında ağırlıklandırılmalı

Sınıfların %47'si iki projede: netbox 4 116, yt-dlp 2 323 (toplam 13 738). İkisi de tek bir
deyimin binlerce tekrarı — netbox'ta Django form/serializer/filterset/table
sınıfları, yt-dlp'de birbirine çok benzeyen `InfoExtractor` alt sınıfları.
Tüm sınıfları tek havuzda toplayıp persentil almak, eşiği bu iki projenin
deyimine göre kalibre eder; kütüphane türü (1 214 sınıf) ve ML türü (373
sınıf) sayıca boğulur.

Dağılım tablosu için öneri: persentiller **proje başına** hesaplanır, tür ve
genel değer projelerin **medyanı** olarak verilir. Havuzlanmış persentil
yalnızca karşılaştırma için yanında gösterilir. ml_research'ün 373 sınıfı
tür bazında sınıf metrikleri için ince; fonksiyon metrikleri (1 583) için yeterli.

## Bulgu 2 — Ölçülmeyen kod: deyim, tür değil

**Ölçülen mantık payı:** raporda yer alan birimlerin (modülün en üst
düzeyindeki fonksiyon ve sınıflar, dekoratörleriyle) kapsadığı satırların, tüm
mantık satırlarına oranı. Mantık satırından hariç: `import` satırları, birim
dışındaki serbest string'ler (docstring'ler) ve birim dışındaki düz veri
atamaları (değeri `ast.literal_eval` ile okunabilen `X = {...}`). Kural
`corpus.line_coverage`'da, sınırları testte.

26 projenin 24'ünde %87-99. İki gerçek kör nokta:

| Proje | Ölçülen | Ölçülmeyen mantık neden |
|---|---:|---|
| nanoGPT | %44 | Betik: `train.py`, `bench.py`, `sample.py` en üst düzeyde yazılmış eğitim/çıkarım döngüsü (`if`, `while`) |
| httpie | %83 | Bildirimsel CLI: `cli/definition.py`'de modül düzeyinde ~770 satır `parser.add_argument(...)` |

Ara değerler de açıklandı:
- **rich %87:** ölçülmeyenin %40'ı hesaplanmış atamalar — renk paletleri, kutu
  ve stil tanımları (`_palettes.py`, `box.py`, `default_styles.py`; değerler
  sabit değil çağrı olduğu için mantık sayılır), %42'si modül düzeyi `if`
  blokları, %14'ü `if`/`try` altındaki tanımlar.
- **pydantic %92:** ölçülmeyenin en büyük kısmı `if TYPE_CHECKING:` / `else:`
  altında tanımlı sınıf ve fonksiyonlar (`types.py`). Bu, Blok 1'de bulunan
  kapsama boşluğudur (metric-accuracy §1): `if`/`try` altındaki tanımlar
  raporda hiç yer almıyor.

**Tür bu kör noktayı öngörmüyor.** ml_research türünün geri kalanı %97-99:
yolov5, detectron2, whisper, segment-anything paket olarak yazılmış. Belirleyen
şey tür değil **yazım deyimi** — betik ve bildirimsel modül düzeyi kod.

**İlk tanımın iki hatası.** İlk sürüm veri tablolarını mantık saydı: netbox
%48 ölçülmüş göründü, ölçülmeyen 130 bin satırın 127 bini tek bir BM liman
kodu tablosuydu (`extras/data/un_locode.py`, 111 bin satır); rich'in emoji
tablosu da aynı. İkinci sürüm pydantic'in attribute docstring'lerini
(`x: int` altındaki `"""..."""`) mantık saydı. İkisi de ölçülen payı
yapay olarak düşürüyordu; düzeltildi ve testle sabitlendi. Sınır bilinçli
olarak basit tutuldu: sabit atama (`batch_size = 12`, `step = 0`) veridir,
değeri hesaplanan atama mantıktır.

## Blok 1b'nin sonraki maddeleri için

- **Dağılım tablosu** tanım kararlarından sonra (`docs/STATUS.md`). Korpus ve
  ağırlıklandırma önerisi hazır.
- **Kapsama tablosu:** CAM verisi metric-accuracy §5'te; `if`/`try` altındaki
  tanımların ölçülmemesi burada da ikinci kez görüldü ve kapsama kararına
  girdi olmalı.
- **Framework giriş noktaları:** korpusta şimdi 5 web uygulaması ve 6 CLI var;
  `too_many_params` kuralı gerçek dekoratör deyimleri üzerinde ölçülebilir.
