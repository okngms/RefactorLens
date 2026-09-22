# Anotasyon kapsamı — ön kayıt

v2.2 §3'ün dört yeni ölçüsünden biri (`docs/v2.2-python-metrikleri.md`). K7:
CAM'in sorunu ayrım değil kapsama; kapsamın kendisi ayrı bir ölçü olmalı.
**Bu bölüm ölçümden önce yazıldı** (2026-09-22) ve sonuçlar görüldükten sonra
değiştirilmez; sonuçlar "Ölçüm" bölümüne eklenir.

## Dokuz madde

1. **Neyi sayıyor.** Bir fonksiyonun parametre yuvalarından annotation'lı
   olanların payı. Yuvalar `param_count` ile birebir aynı: yalnızca-konumsal,
   konumsal, yalnızca-anahtar, `*args`, `**kwargs`; metotta alıcı (`self` /
   `cls`, `@staticmethod` hariç) sayılmaz. String annotation (`"Order"`) ve
   `Any` annotation'lı sayılır. Ayrıca dönüş annotation'ı var mı (evet/hayır).
2. **Birim.** Fonksiyon (`annotation_coverage`, `returns_annotated`) ve sınıf
   (`annotation_coverage`: raporlanan metotlarının bütün yuvaları üzerinden
   havuz oran — CAM'in içeride kullandığı kapsamın aynısı).
3. **Aralık, yön.** 0..1. **Yön yok:** yüksek "daha iyi" demek değildir; ölçü
   betimseldir.
4. **Hesaplanamaz.** Parametre yuvası yoksa `null` (CAM bu durumda `0.0`
   taşıyor; yeni alan `null` invariant'ına uyar).
5. **Altın değerler.** `tests/test_annotation_coverage.py`, elle, koddan önce.
6. **Bilinen yanlış pozitif / negatifler.** `Any` kapsamı artırır ama tip
   bilgisi taşımaz (kapsam ≠ kesinlik). Ayrı `.pyi` dosyalarıyla ya da
   typeshed'de tiplenen paketler annotation'sız görünür (`.pyi` okunmaz).
   `# type:` yorumları (Python 2 dönemi) sayılmaz. Dekoratörün değiştirdiği
   imza görülmez.
7. **Kanıt alanları.** Koku yok; kanıt alanı yok. Yeni rapor alanları:
   `functions[].annotation_coverage`, `functions[].returns_annotated`,
   `classes[].annotation_coverage`. Alan eklemek şema sürümü artırmaz (`04` §1).
   `advise` prompt'u donmuş (`prompts.py`); alanlar prompt'a girmez.
8. **Eşik.** **Tanımlanmaz.** Ölçü bir kalite iddiası taşımıyor (madde 9);
   eşik, "düşük kapsam kötüdür" iddiasını gizlice sokmak olur. Dağılım
   raporlanır.
9. **Geçerlilik iddiası ve çürütme — ölçümden önce.** İddia: bu sayı, kodun
   imzalarında ne kadar tip bilgisi **yazılı** olduğunu ölçer. İddia
   **edilemeyecek**: yüksek kapsam yüksek kalite. Bağımsız sinyal: PEP 561
   `py.typed` işareti (paketin kendini tiplenmiş ilan etmesi; kapsam
   hesabından bağımsız bir dosyadır). Ölçü şu koşullardan **herhangi biri**
   gerçekleşirse "yazılı tip bilgisi" göstergesi olarak reddedilir ve araca
   eklenmez:
   - (a) `py.typed` taşıyan projelerin fonksiyon kapsamı medyanı, taşımayanların
     medyanından **büyük değilse**;
   - (b) `py.typed` taşıyan projelerin **%80'inden azı**, bütün projelerin
     medyanının üstündeyse;
   - (c) sınıf düzeyindeki değer, CAM'in iç kapsamıyla parametresi olan
     herhangi bir sınıfta **farklıysa** (iki tanım aynı olmalı; fark bir
     uygulama hatasıdır ve önce düzeltilir).

   Ek betimsel sorular (ret koşulu değil): proje içinde dağılım iki kutuplu mu
   (Blok 1'in CAM gözlemi); dönüş annotation'ı parametreden farklı mı
   davranıyor.

**Proje düzeyi değer.** Projenin fonksiyon kapsamı = bütün fonksiyonların
yuvaları üzerinden havuz oran (yuvası olmayan fonksiyon katılmaz). Tür ve
genel değer dağılım tablosuyla aynı kuralla projelerin medyanı.

`py.typed`: tarama kökünün altında (dışlanan dizinler hariç) en az bir
`py.typed` dosyası.

---

## Ölçüm

*Bu bölüm ölçümden sonra eklendi; yukarısı değiştirilmedi.*

```bash
python experiments/hardening/annotations.py     # ~2 dk
```

Çıktılar `results/annotation-coverage.json`,
`results/annotation-coverage-tables.md`; tekrar üretildiğinde birebir aynı.
Ölçü fonksiyonları aracın kendisinden gelir.

| Grup | proje | kapsam | tam annotation'lı fonksiyon | hiç annotation'sız | dönüş annotation'ı |
|---|---:|---:|---:|---:|---:|
| tüm korpus | 25 | %82.4 | %75.9 | %12.8 | %69.1 |
| library | 10 | %99.5 | %99.0 | %0.6 | %99.0 |
| cli | 6 | %88.8 | %87.9 | %8.9 | %84.5 |
| web_app | 5 | %56.7 | %43.3 | %29.2 | %28.4 |
| ml_research | 4 | %54.4 | %46.7 | %42.6 | %30.0 |

Proje başına tablo `results/annotation-coverage-tables.md`'de.

### Ön kayıtlı çürütme koşulları

- `py.typed` taşıyan 9 projenin kapsam medyanı **%100.0**, taşımayan 16
  projenin **%59.6**; genel medyan %82.4.
- (a) py.typed medyanı büyük değil: **hayır**.
- (b) py.typed projelerinin %80'inden azı genel medyanın üstünde: **hayır**
  (9'un 8'i).
- (c) sınıf değeri CAM'in iç kapsamından farklı: **hayır** (parametreli her
  sınıfta aynı).
- **Sonuç: çürütülmedi.** Ön kayda göre alanlar araca eklendi (K11).

### Bulgular

1. **Tek istisna öngörülmüştü.** attrs `py.typed` taşıyor ama kapsamı %11.4:
   tiplerini ayrı `.pyi` dosyalarında tutuyor (`src/attr/` ve `src/attrs/`
   altında 10 dosya). Ön kaydın 6. maddesindeki yanlış negatif.
2. **Kapsam proje içinde iki kutuplu.** Tipik projede fonksiyonların %75.9'u
   tam annotation'lı, %12.8'i hiç annotation'sız; kısmi annotation'lı
   fonksiyon azınlık. Blok 1'in CAM için gördüğü desen fonksiyon düzeyinde de
   geçerli.
3. **Projeler arasında da iki kutuplu.** 26 projenin 7'si %3'ün altında
   (nanoGPT, awscli, yolov5, redash, requests, netbox, yt-dlp), 10'u %99'un
   üstünde; arada kalan dokuz projenin ikisi %30'un altında (attrs .pyi
   yüzünden %11.4, detectron2 %26.4). Kütüphanelerde
   medyan %99.5, web uygulamaları ve ML'de %55 civarı.
4. **README'nin eski iddiası düzeltildi.** README "most Python codebases are
   unannotated" diyordu; bu korpusta projelerin medyanı %82.4. Doğru olan:
   annotation'sız projeler bir azınlık ama büyük bir azınlık (26'nın 7'si %3'ün
   altında). CAM tipik projede sınıfların yalnızca %27.7'sinde hesaplanıyor
   (`coverage.md`); Blok 1 referans setinde hesaplanamayan sınıfların büyük
   kısmı parametresizdi (`metric-accuracy.md` §5). Korpusta iki nedenin payı
   ayrıştırılmadı.
5. **Dönüş annotation'ı parametreden daha seyrek** web uygulamaları ve ML'de
   (%28-30'a karşı %55-57): parametreleri annotation'lı fonksiyonlar dönüşü
   yazmamış olabilir. Tek tek incelenmedi.
