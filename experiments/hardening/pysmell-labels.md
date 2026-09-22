# PySmell etiketleri — neyi kodluyorlar (ön kayıt)

v2.2 §2 (`docs/v2.2-python-metrikleri.md`). §2'nin dayanağı: PySmell (Chen ve
ark. 2016) etiketli veri seti yayınladı, "kendi tespitimizi dış bir referansa
karşı doğrulayabiliriz". Large Class için bu tutmadı: elle incelenen 300
etiket tek bir `CLOC >= 37` eşiğiyle 1 hatayla ayrılıyor (`stateless-gate.md`).
Bu belge aynı soruyu on kokunun hepsi için sorar. **Bu bölüm ölçümden önce
yazıldı** (2026-09-22) ve sonuçlar görüldükten sonra değiştirilmez.

## Veri

`github.com/chenzhifei731/Pysmell`, commit
`233afebac24c910be89d065ffa661ec72458a62c`,
`pysmell/detection/example repository/manual inspection/<Koku>.csv`. Her
satır bir kod öğesi: PySmell'in ölçtüğü metrik sütunları, iki otomatik
dedektörün kararı (`experience-based`, `statistics-based`) ve elle verilmiş
karar (`manual analysis`).

## Soru ve okuma kuralı

Her koku için, elle verilmiş etiket PySmell'in **kendi** metrik sütunlarıyla ne
kadar iyi yeniden üretilebiliyor?

- **Tek eşik:** tek bir metrikte `değer >= t` ya da `değer <= t` kuralının en
  az hatalısı.
- **İki eşik:** iki metrikte eşiklerin `ve` / `veya` birleşiminin en az
  hatalısı (yalnızca birden fazla metrik sütunu olan kokular).

Okuma (her koku için, N satır, P pozitif):

| Durum | Koşul | Anlamı |
|---|---|---|
| yetersiz pozitif | P < 10 | sonuç çıkarılmaz |
| tek eşiği kodluyor | tek eşik hatası ≤ max(1, ⌈0.02·N⌉) | etiket bir uzmanın seçtiği eşiktir; kokunun anlamını değil eşiği doğrular |
| kuralı kodluyor | tek eşik değil, iki eşik hatası ≤ aynı sınır | etiket iki metrikli bir kuraldır |
| bağımsız yargı | ikisi de değil | etiket PySmell'in metriklerinin göremediği bir şey taşır; dış doğrulama olarak kullanılabilir |

Ek olarak: elle verilen etiketin iki otomatik dedektörle uyumu (satırların
yüzde kaçında aynı). Elle etiket bir dedektörle birebir aynıysa etiket o
dedektörün çıktısıdır.

## Sınırlar (ölçümden önce)

- Soru yalnızca etiketin PySmell'in **kendi** sütunlarıyla açıklanıp
  açıklanmadığını sorar. "Bağımsız yargı" çıkması etiketin doğru olduğunu
  göstermez; yalnızca eşik olmadığını gösterir.
- Satırlar PySmell'in 2015 sürüm projelerinden (django 1.8.2, numpy 1.9.2,
  ...). Bizim tarayıcımızın bu kodu ayrıştırıp ayrıştıramadığı bu belgenin
  sorusu değildir.

---

## Ölçüm

*Bu bölüm ölçümden sonra eklendi; yukarısı değiştirilmedi.*

```bash
python experiments/hardening/pysmell_labels.py     # ~10 s
```

Çıktılar `results/pysmell-labels.json`, `results/pysmell-labels-tables.md`;
tekrar üretildiğinde birebir aynı.

### Ön kayıtlı okuma

| Koku | N | pozitif | en iyi tek eşik (hata) | en iyi iki eşik (hata) | sınır | okuma |
|---|---:|---:|---|---|---:|---|
| LargeClass | 300 | 11 | `CLOC >= 37` (1) | - | 6 | tek eşiği kodluyor |
| MultiplyNestedContainer | 300 | 15 | `DNC >= 3` (2) | `DNC >= 3 and NCT >= 2` (2) | 6 | tek eşiği kodluyor |
| LongLambdaFunction | 200 | 16 | `NOO >= 17` (11) | `NOC >= 72 and NOO >= 15` (4) | 4 | kuralı kodluyor |
| LongTernaryConditionalExpression | 201 | 11 | `NOL >= 3` (7) | `NOC >= 98 or NOL >= 3` (5) | 5 | kuralı kodluyor |
| LongMessageChain | 300 | 36 | `LMC >= 4` (7) | - | 6 | bağımsız yargı |
| LongParameterList | 300 | 31 | `PAR >= 5` (13) | - | 6 | bağımsız yargı |
| ComplexContainerComprehension | 300 | 22 | `NOO >= 22` (19) | `NOC >= 86 and NOO >= 22` (10) | 6 | bağımsız yargı |
| LongScopeChaining | 69 | 6 | - | - | 2 | yetersiz pozitif |
| LongMethod | 300 | 2 | - | - | 6 | yetersiz pozitif |
| LongBaseClassList | 300 | 0 | - | - | 6 | yetersiz pozitif |

### Sonradan eklenen analiz (ön kayıtta yok)

PySmell'in dedektör kodu (`pysmell/detection/detector.py`) okundu: iki
dedektör de **genel** eşikler kullanıyor, proje başına değil. CSV'deki
`statistics-based` sütunu 10 kokunun 9'unda o kodun kuralıyla birebir aynı
(ComplexContainerComprehension'da 12 satır farklı; `experience-based` sütunu
beş kokuda koddan ayrılıyor, nedeni incelenmedi). Elle verilen etiketin
statistics-based kuralından ayrıldığı satır:

| Koku | kural ≠ elle | N |
|---|---:|---:|
| LongLambdaFunction | 4 | 200 |
| LongTernaryConditionalExpression | 5 | 201 |
| LargeClass | 6 | 300 |
| LongMessageChain | 7 | 300 |
| MultiplyNestedContainer | 8 | 300 |
| ComplexContainerComprehension | 25 | 300 |
| LongParameterList | 68 (experience kuralı `PAR >= 5`: 13) | 300 |

Bu tablo ön kayıtlı okumayı değiştirmez; yalnızca yorumlar.

## Bulgular

1. **Yeterli pozitifi olan yedi kokunun beşinde etiket, PySmell'in kendi
   kuralının %2.0-2.7'lik bir sapmasıyla yeniden üretiliyor.** LargeClass,
   MultiplyNestedContainer, LongLambdaFunction, LongTernaryConditionalExpression
   ve LongMessageChain. LongMessageChain ön kayıtla "bağımsız yargı" çıktı
   (7 hata, sınır 6) ama statistics-based kuralından yalnızca 7 satırda
   ayrılıyor; sınıra bir satır uzak. Bu beşinde etiket, bir uzmanın PySmell'in
   eşiklerini onaylamasıdır; kokunun gerçekliğine dair bağımsız bir yargı
   değildir.
2. **İki kokuda etiket metrikten belirgin biçimde ayrılıyor.**
   LongParameterList'te elle verilen etiket `PAR >= 5`'ten 13 satırda (%4.3)
   ayrılıyor; ComplexContainerComprehension'da en iyi iki eşikli kural bile 10,
   PySmell'in kuralı 25 satır hata yapıyor. Bu iki koku, etiketin sayının
   ötesinde bir şey taşıdığı yerler. Ayrılan satırlar okunmadı: PySmell deposu
   konu projelerin kaynak kodunu içermiyor.
3. **Üç kokuda veri yetersiz.** LongBaseClassList'te elle incelenen 300 satırın
   hiçbiri pozitif değil; LongMethod'da 2, LongScopeChaining'de 6 pozitif var.
   §2'nin almayı planladığı altı kokudan ikisi (Long Scope Chain, Long Base
   Class List) için dış doğrulama verisi fiilen yok.

## v2.2 §2 için sonuç

- PySmell etiketleri §2'nin varsaydığı gibi bir **dış kehanet** değil. Altı
  yeni kokudan dördünde etiket PySmell'in kuralına %2-3 yakın, ikisinde
  yeterli pozitif yok. Bizim tespitimizi bu etiketlere karşı sınamak, PySmell'in 2015
  eşiklerini yeniden üretip üretmediğimizi sınar; kokunun gerçek olup
  olmadığını değil.
- Kullanılabilecekleri tek rol: **literatür eşiği** olarak, dokuz maddenin 8.
  maddesinde korpus persentiliyle karşılaştırma noktası (ör. LongMessageChain
  için PySmell `LMC >= 4`).
- Yeni kokuların geçerlilik iddiası (madde 9) başka bir yoldan gelmeli: ön
  kayıtlı bağımsız sinyal (K11'deki `py.typed` gibi) ya da kör etiketli
  örneklem (`god_class_sample.py` deseni).
- Mevcut `too_many_params` için yan bulgu: PySmell'in elle etiketi `PAR >= 5`
  (bizim varsayılan eşiğimiz) ile 300'de 13 satırda ayrılıyor. Hangi yönde
  ayrıldığı ve nedeni incelenmedi; K8'in yalnızca-anahtar parametre sorusuyla
  (FUTURE.md) ilişkisi bilinmiyor.
