# DÜZELTME — `04-ortak-spesifikasyon.md` § 2.5

`§ 2.5 Metrik sınıfları` bölümünün tamamını aşağıdakiyle değiştirin. Dosyanın
başka hiçbir yeri değişmiyor. `schema_version` artmaz: bu bir rapor alanı değil,
analiz sözleşmesidir.

---

## 2.5 Metrik sınıfları (deney analizinde kullanılır)

> **Bu bölüm v1 verisine göre düzeltildi.** Önceki sürüm `NOM` ve `LOC`'u
> "aritmetik" sayıyor ve v1 bulgusuna dayandığını söylüyordu. v1'de her ikisi de
> **yanlış tahmin edilen** gruptaydı (NOM 0/2, LOC 0/1). Eski sınıflandırmayla
> FINDINGS-2, aritmetik doğruluğu 6/6 yerine 6/9 raporlar ve v1'in en net
> sonucu görünmez olurdu.

Ayrımın ekseni "sayma mı, ilişki mi" değildir. v1'de tahminleri ayıran şey
**değişikliğin hedefte ne bıraktığıydı**.

### Sınıf A — çıkarımsal (subtractive)

Hedeften iş çıkarıldığında değer düşer ve **yerine bir şey geçmez.** Tahmin
etmek için yalnızca neyin alındığını bilmek yeterlidir.

`CC`, `WMC`, `PARAMS`

- Bir dalı fonksiyondan çıkarın: CC düşer.
- Bir metodu sınıftan taşıyın: WMC düşer, çünkü toplam olan karmaşıklık gider.
- İmzayı tek nesneye indirin: PARAMS düşer.

v1: **6/6 doğru.**

### Sınıf B — kalıntıya bağlı (residue-dependent)

Değer, değişikliğin hedefte **ne bıraktığına** bağlıdır. Tahmin etmek için
kalıntıyı — sarmalayıcıyı, yeni attribute'u, yeni bağımlılığı — hesaba katmak
gerekir.

`NOM`, `LCOM4`, `DCC`, `LOC`, `DAM`, `CAM`, `Ca`, `Ce`

- **NOM:** metot taşındı ama devredici sarmalayıcı bırakıldı → sayı değişmez.
  v1'de iki öneri de sarmalayıcıyı **kendi taslağında yazmıştı**, biri örnek kod
  bile verdi, yine de NOM'un düşeceğini tahmin etti.
- **LCOM4:** bileşen çıkarıldı ama sarmalayıcılar `self._pricing`,
  `self._audit` gibi ayrı attribute'lara dokunuyor → bileşen sayısı değişmez.
- **DCC:** işbirlikçiler taşındı ama yeni sınıf bağımlılık olarak eklendi →
  yerine geçme; sayı düşer veya sabit kalır, artmaz.
- **LOC:** satırlar silinmedi, taşındı — ama hedeften çıktı. Model proje
  genelini düşündü, metrik fonksiyonu ölçüyor.

v1: **0/7 doğru.**

`DAM`, `CAM`, `Ca`, `Ce` için v1'de doğrulanmış tahmin **yoktur**; sınıf ataması
mekanizmaya göre yapılmıştır, veriye göre değil. FINDINGS-2 bunları ayrı
işaretlemelidir.

### Bu bir hipotezdir, taksonomi değil

Sınıflandırma 13 tahminden türetildi ve metrik başına 1-3 gözlem içeriyor. Bu
sayılarla kesin bir sınıflandırma ilan etmek aşırı uydurma olur.

Bu nedenle **her FINDINGS raporu tahmin doğruluğunu önce metrik başına
raporlar**, sınıf düzeyi özet ikincildir. Sınıf ataması bir gözlemi
açıklamak için önerilmiş bir mekanizmadır ve v2/v3 verisiyle **çürütülebilir**.

Çürütme koşulu açıktır: yeni veride Sınıf B metriklerinden biri tutarlı biçimde
doğru tahmin edilirse (ya da Sınıf A'dan biri tutarlı biçimde yanlış), mekanizma
yanlıştır ve yeniden tanımlanmalıdır.

### Neden isimler değişti

Eski adlar (`aritmetik` / `yapısal`) yanıltıcıydı: NOM bir sayımdır, yani
kelimenin düz anlamıyla aritmetiktir — ama v1'de yanlış tahmin edildi. Sorun
metriğin sayı olup olmaması değil, **tahmin etmek için gereken akıl yürütmenin
türüydü.** Yeni adlar mekanizmayı taşır.

FINDINGS-1'in verisi değişmedi; yalnızca iki grubun tanımı netleşti.
