# `god_class` etiketleme kılavuzu

`god_class_sample.py`'nin ürettiği örneklem için. Amaç, `god_class` kapısının
"birden fazla sorumluluk" iddiasını kapıdan bağımsız bir yargıyla sınamak
(`stateless-gate.md`, "Sonraki adım"). Kılavuz etiketlemeden **önce** yazıldı
ve etiketleme sırasında değiştirilmez; değişirse etiketler baştan alınır.

## Körlük kuralları

1. Yalnızca `god-class-sample.json`'ı ve sınıfın kaynak kodunu aç.
2. `results/god-class-strata.json`, `results/stateless-gate*.json`,
   `results/density-gate*`, `rlens scan` çıktısı ve bu sınıfın metrikleri
   etiketleme bitene kadar açılmaz.
3. Kararı sınıfın kendi kodundan ver; üst sınıfı yalnızca bir metodun ne
   yaptığını anlamak için oku.
4. Bir kararı sonradan değiştirirsen `note`'a eski kararı ve nedenini yaz.

## Soru

> Bu sınıfın metotları, **birbirinden bağımsız olarak değişebilecek** en az iki
> sorumluluğa ayrılıyor mu — ve bu ayrım sınıfı bölmeyi haklı çıkaracak kadar
> belirgin mi?

"Sorumluluk" = sınıfın değişmesi için bir neden (Martin'in SRP tanımı).
Aynı kavramın farklı yüzleri tek sorumluluktur.

## Kararlar

| Karar | Ne zaman |
|---|---|
| `god` | En az iki sorumluluk kümesi adlandırılabiliyor, her biri birkaç metottan oluşuyor ve kümeler aynı amaca hizmet etmiyor. `responsibilities`'e **en az iki** küme yazılır, her birine 2-3 örnek metot adıyla: `"HTTP request building: prepare_request, merge_headers"`. |
| `not_god` | Sınıf büyük ama tek bir sorumluluğun uzun kataloğu: ziyaretçi (her düğüm türü için bir `visit_`), mesaj/hata kataloğu, bir veri yapısının API'si (`DataFrame` gibi), framework'ün dikte ettiği arayüz (GraphQL tipi, ORM modeli). `note`'a hangisi olduğunu yaz. |
| `unsure` | Kod okunduktan sonra iki okuma da savunulabiliyor. `note`'a iki okumayı yaz. `unsure` kesinlik/duyarlılık hesabına girmez; sayısı raporlanır. |

## Tuzaklar

- **Boyut karar değildir.** 200 metotlu bir ziyaretçi `not_god`, 25 metotlu
  bir "yönetici" sınıfı `god` olabilir.
- **Durum paylaşımı karar değildir.** Metotların ortak `self` attribute'u
  kullanıp kullanmadığına bakma; ölçülen şey tam olarak bu ve karar ondan
  bağımsız olmalı.
- **Kalıtım.** Mixin'lerden gelen sorumluluklar sınıfın kendi gövdesinde
  yoksa sayılmaz.
- **Belgeleme.** Docstring bir sorumluluk iddia edebilir; karar metot
  gövdelerinden verilir.

## Sınırlılık

Etiketleyen bu projeyi tasarlayan kişiyse, sonuç o sınırlılığı taşır ve
FINDINGS'te ilk cümlede yazılır. İkinci bir etiketleyici mümkünse aynı
örneklemi bağımsız etiketler ve uyum (Cohen κ) raporlanır.
