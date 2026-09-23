# Modül düzeyi kohezyon — ön kayıt

v2.2 §3'ün dördüncü ölçüsü (`docs/v2.2-python-metrikleri.md`); kapsam
`docs/v2.2-sinifsiz-kod.md` §3. **Bu bölüm ölçümden önce yazıldı**
(2026-09-23) ve sonuçlar görüldükten sonra değiştirilmez; sonuçlar "Ölçüm"
bölümüne eklenir.

## Dokuz madde

1. **Neyi sayıyor.** Bir modülün raporlanan birimleri (modül düzeyi fonksiyon,
   `@overload` taslakları hariç; modül düzeyi sınıf) düğümdür. İki kenar türü:
   - **Durum kenarı:** iki birim aynı **modül global'ine** dokunuyorsa (okuma
     ya da yazma). Modül global'i: modülün en üst düzeyinde atamayla
     (`X = ...`, `X: T = ...`, `X += ...`) bağlanan ad; import edilen adlar
     ve birimlerin kendi adları global sayılmaz (paylaşılan bir import, iki
     birimi bağlamaz).
   - **Kullanım kenarı:** bir birim, aynı modüldeki başka bir birimin adını
     gövdesinde kullanıyorsa (çağrı, örnekleme, referans).

   Birimin gövdesi: fonksiyonda gövde (iç içe tanımlar dahil — modül
   düzeyinde bir birimin kapattığı her şey onundur), sınıfta bütün sınıf
   gövdesi. Dekoratörler ve varsayılan değerler dahil.

   İki değer, K9'un dersi yüzünden ayrı ayrı: **MCOH** (iki kenar türü; LCOM4'ün
   modül karşılığı) ve **MCOH-S** (yalnız durum kenarı; LCOM3-HM'nin modül
   karşılığı). Değer: bağlı bileşen sayısı.
2. **Birim.** Modül.
3. **Aralık, yön.** ≥ 1; yüksek: modülün birimleri birbirinden kopuk kümeler.
   Kalite yönü iddia edilmez (bir `utils.py` tasarım gereği kopuktur).
4. **Hesaplanamaz.** İkiden az birimi olan modülde `null`.
5. **Altın değerler.** `tests/test_module_cohesion.py`, elle, koddan önce.
6. **Bilinen yanlış pozitif / negatifler.** Birimler arası bağ modül dışından
   kurulursa (ortak bir sınıfın metotları üzerinden, `self` aracılığıyla)
   görülmez; bir global yalnızca başka modüller tarafından okunuyorsa bağ
   kurmaz; `__all__` ve `logger = logging.getLogger(...)` gibi her birimin
   dokunduğu "altyapı global'leri" birimleri yapay biçimde bağlar
   (`__all__` birimlerin içinde okunmaz, sorun değil; `logger` sorun olabilir).
7. **Kanıt alanları.** Koku yok. Kabul edilirse `modules[].cohesion_components`
   (MCOH) ve/veya `modules[].cohesion_components_state` (MCOH-S); şema artışı
   yok, prompt'a girmez.
8. **Eşik.** Tanımlanmaz (betimsel).
9. **Geçerlilik iddiası ve çürütme — ölçümden önce.** İddia: bileşenler,
   modülün birbirinden bağımsız kullanılan işlev kümeleridir. **Bağımsız
   sinyal: modülü kullananlar.** Bir modül gerçekten bağımsız kümelerden
   oluşuyorsa, onu `from M import a, b, ...` ile kullanan bir modül bu kümelerin
   rastgele beklenenden **azına** dokunmalıdır.

   - Çift: (kullanan modül, M) — kullanan, M'den en az iki birim adını
     `from ... import` ile alıyorsa ve M'nin değeri ≥ 2 ise. Çözüm import
     grafiğiyle aynı kural (`imports._Resolver`, `_absolute_name`).
   - Gözlenen: kullananın aldığı birimlerin dokunduğu farklı bileşen sayısı.
   - Beklenen: aynı sayıda birim M'nin birimleri arasından rastgele seçilseydi
     dokunulacak bileşen sayısının ortalaması; tam kombinatorik (hipergeometrik)
     hesap, rastgelelik yok.
   - R = gözlenen / beklenen.

   Bir değişken (MCOH ya da MCOH-S) şu koşullardan **herhangi biri**
   gerçekleşirse reddedilir:
   - (a) **Bağımsız sinyal:** bütün çiftlerde R'nin medyanı **0.95'ten
     küçük değilse** (kullananlar bileşenleri rastgeleden ayırt edilebilir
     biçimde az kullanmıyor), ya da uygun çift sayısı 100'ün altındaysa
     (sınanamıyor).
   - (b) **Yozlaşma (K9'un dersi):** ≥ 2 birimli modüllerin, projelerin
     medyanında **%50'sinden fazlası tamamen dağınıksa** (değer = birim sayısı;
     ölçü "hiçbir şey bağlı değil" demekten öteye geçmiyor).
   - (c) **Ayrım:** en az 30 değerli modülü olan projelerin **yarısından
     azında** p10 < p90 ise.

**Kabulün tavanı.** Geçen değişken(ler) betimsel alan olarak eklenir. İkisi de
geçerse ikisi de eklenir; hiçbiri geçmezse hiçbiri.

---

## Ölçüm

*Bu bölüm ölçümden sonra eklendi; yukarısı değiştirilmedi.*

```bash
python experiments/hardening/module_cohesion.py     # ~3 dk
```

Çıktılar `results/module-cohesion.json`, `results/module-cohesion-tables.md`;
tekrar üretildiğinde birebir aynı.

### Ön kayıtlı koşullar

| Değişken | çift | R medyanı | R < 1 payı | tamamen dağınık (proje medyanı) | yayılım | (a) | (b) | (c) |
|---|---:|---:|---:|---:|---|---|---|---|
| MCOH | 3 193 | 1.0 | %39.5 | %12.6 | 16/16 | ret | geçti | geçti |
| MCOH-S | 4 388 | 1.0 | %18.0 | %79.5 | 16/16 | ret | ret | geçti |

**Sonuç: ikisi de reddedildi.** Araca alan eklenmedi (K16).

- (a) Kullananlar bileşenleri rastgeleden az kullanmıyor: R'nin medyanı iki
  değişkende de 1.0 (eşik < 0.95).
- (b) MCOH-S yozlaşıyor: ≥ 2 birimli modüllerin tipik projede %79.5'i tamamen
  dağınık — K9'da LCOM3-HM'nin büyük sınıflarda yaptığının modül karşılığı.
  Modül fonksiyonlarının çoğu hiçbir modül global'ini paylaşmıyor.

### Sonradan eklenen analiz (ön kayıtta yok)

Kullanan modül M'nin bütün birimlerini alıyorsa seçim yoktur ve R tanım gereği
1'dir. Yalnız seçim yapılan çiftlerde de sonuç değişmiyor: MCOH 2 811 çift,
R medyanı 1.0, R < 1 payı %44.9; MCOH-S 3 836 çift, 1.0, %20.6.

Medyanın tam 1.0'a yığılmasının kesin bir nedeni var: bileşenlerin hepsi tek
birimliyse (tamamen dağınık modül) seçilen n birim her zaman n bileşene dokunur
ve beklenti de tam n'dir (N·(1 − C(N−1, n)/C(N, n)) = n), yani R = 1. Dağınık
ya da dağınığa yakın modüller dağılımı 1'e çekiyor. Bu modülleri de dışarıda
bırakıp yeniden bakmak sonuca göre veri seçmek olurdu; yapılmadı.

## Bulgular

1. **Modül fonksiyonları modül global'i üzerinden çok nadir bağlanıyor.**
   MCOH-S'nin %79.5 dağınıklığı bunu söylüyor: modül düzeyi fonksiyon ve
   sınıflar nadiren ortak bir modül global'i paylaşıyor. Bağ çoğunlukla çağrıyla
   kuruluyor (MCOH'da dağınıklık %12.6). Paylaşılan durumun nerede tutulduğu
   ölçülmedi.
2. **Bileşenler kullanımı öngörmüyor.** Bir modülün çağrı/durum grafiğindeki
   parçalar, o modülü kullananların hangi parçaları birlikte aldığıyla ilişkili
   görünmüyor. §3'ün "Python'un asıl birimi modül; LCOM4'ün mantığı modüle"
   iddiası bu ölçüyle desteklenmedi.
3. **Bağımsız sinyal tasarımının bir zaafı ortaya çıktı:** tamamen dağınık
   modüllerde R tanım gereği 1. Sonraki bir aday ya dağınıklığı ayrı bir ret
   koşuluna bağlamalı ya da sinyali bileşeni en az iki birimli modüllerle
   sınırlamalı — **ön kayıtta**, sonuçlardan önce.
