# Framework giriş noktaları

Sertleştirme Blok 1b, madde 4. Kural: `src/rlens/analysis/entry_points.py`;
karar: `docs/v2-tanim-kararlari.md` K6; testler: `tests/test_entry_points.py`.

```bash
python experiments/hardening/entry_points.py   # results/entry-points.json
```

## Soru

Dogfooding: `too_many_params`'ın 19 vakasının "büyük kısmı" typer komutuydu —
parametreler CLI seçenekleri, kötü tasarım değil. Plan: dekoratörle tanımlanan
giriş noktaları parametre sayımında ayrı ele alınır.

## Ölçüm 1 — dekoratör "giriş noktası" demek değil

Korpusta 5+ parametreli fonksiyonlar (26 proje, varsayılan tarama):

| | Fonksiyon | Pay |
|---|---:|---:|
| Dekoratörsüz | 1 696 | %75.8 |
| Giriş noktası olmayan dekoratör | 525 | %23.5 |
| **Framework giriş noktası** | **17** | **%0.8** |
| **Toplam** | **2 238** | |

Dekoratörlülerin en sıkları `@classmethod` (alternatif kurucular), pandas'ın
`@doc` / `@final` / `@Appender`'ı, Celery'nin `@app.task`'ı. Plandaki
"dekoratörlü fonksiyonlar ayrı ele alınır" kuralı uygulansaydı, 542 dekoratörlü
fonksiyonun 525'i — gerçek API tasarımları — kokudan sessizce çıkardı.

## Ölçüm 2 — tanınan giriş noktaları

Kural, parametre listesinin **kimin tasarımı** olduğuna bakar:

| Tür | Tanıma | Korpusta | Örnek |
|---|---|---:|---|
| `cli` | click/typer `command`/`group`/`callback()`; `option`/`argument` yalnızca `click`/`typer` sahipli ya da `-` ile başlayan | 7 | black `main` (29 parametre, 31 dekoratör), flask `run_command`, httpx `main` |
| `web_route` | HTTP fiili ya da `route`, yol string'i `/` ile başlıyorsa | 3 | mealie `router.post("/create/ai")` |
| `signal_handler` | `@receiver(...)`, `@event.listens_for(...)` | 7 | netbox `@receiver(post_save, sender=Location)` |
| `fixture` | `@pytest.fixture` | 0 | test dizinleri varsayılan taramada yok |

Örnekler tek tek okundu; hepsi gerçek giriş noktası. Ürün kodundaki sınıflandırıcı
prototip ölçümle aynı 17 fonksiyonu tanıyor.

**Bilinçli olarak tanınmayanlar:** Celery görevi (22 fonksiyon; parametreler
yazarın seçtiği mesaj içeriği), yol string'i olmayan `.get("key")`, sahibi
click/typer olmayan `.option("value")`, framework metodu override'ları (Django
`save(...)`; imza dikte edilmiş ama görmek taban sınıfı çözmeyi gerektirir).

## Etki

| | Önce | Sonra |
|---|---:|---:|
| Korpus `too_many_params` | 2 238 | 2 221 |
| — library | 800 | 798 |
| — cli | 612 | 611 |
| — web_app | 680 | 666 |
| — ml_research | 146 | 146 |
| RefactorLens'in kendi kodu | 20 | 15 |

Dağılım tablosunda (proje medyanı, 1000 fonksiyon başına) cli 35 → 34, web_app
21 → 20.

**Dogfooding notu düzeltildi.** "19 vakanın büyük kısmı typer komutu" değil:
bugünkü kodda 20 vakanın 5'i typer komutu (`scan`, `arch`, `advise`,
`explain`, `verify`). Kalan 15'i iç fonksiyonlar; aralarında `measure_class`
(6) ve iki sağlayıcının `generate` metodu (5) var.

## Sonuç

Kural doğru ve gerekli — bir CLI komutu için "parametreleri azalt" önerisi
yanlış tavsiyedir ve artık verilmiyor. Ama `too_many_params` gürültüsünün
kaynağı giriş noktaları değil; korpusta %99'u dekoratörsüz ya da giriş noktası
olmayan fonksiyonlardan geliyor. Kalan soru **eşik kararının** konusu:

- Kütüphanelerde 1000 fonksiyonda 93 vaka — pandas ve fastapi'nin bildirimsel API
  yüzeyi (`Query` 29 parametre) buradan geliyor.
- RefactorLens'in kalan 15 vakasının 7'sinde parametrelerin bir kısmı yalnızca
  anahtar (`*` sonrası). Adıyla verilmek zorunda olan parametre karıştırılamaz;
  yalnızca-anahtar parametreleri ayrı saymak eşik kararında bir seçenek.
