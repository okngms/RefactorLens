# DÜZELTME 2 — `04-ortak-spesifikasyon.md` § 2.5

> `docs/SPEC-duzeltme-2.5.md`'nin yerine geçer. O belge v1'in 13 tahminine
> dayanıyordu ve kendi çürütme koşulunu yazmıştı. **Koşul 5b verisiyle
> tetiklendi.** Bu belge mekanizmayı yeniden tanımlar.

---

## Ne çürüdü

`docs/SPEC-duzeltme-2.5.md` şunu yazmıştı:

> Çürütme koşulu açıktır: yeni veride Sınıf B metriklerinden biri tutarlı
> biçimde doğru tahmin edilirse, mekanizma yanlıştır ve yeniden tanımlanmalıdır.

5b, 31 doğrulanabilir tahminle bunu sınadı:

| Metrik | Eski sınıf | v1 | v2 (5b) |
|---|---|---|---|
| WMC | A (çıkarımsal) | 2/2 | 5/6 · %83 |
| DCC | B (kalıntıya bağlı) | 0/2 | 5/9 · %56 |
| LCOM4 | B | 0/2 | 5/11 · %45 |
| NOM | B | 0/2 | 1/5 · %20 |

`DCC` ve `LCOM4` v1'de sıfırdı, v2'de yazı-tura civarına çıktı. "Sınıf B tahmin
edilemez" iddiası ayakta değil.

Ama `NOM` %20'de kaldı ve `WMC` %83'te durdu. Yani sınıflandırma tamamen yanlış
da değil. Yanlış olan **neye göre sınıflandırdığıydı**.

---

## Yeni tanım: belirleyici metrik değil, değişiklik

Eski mekanizma metriği sabit bir sınıfa koyuyordu. v2 verisi gösteriyor ki aynı
metrik, uygulanan değişikliğin şekline göre hem tahmin edilebilir hem
edilemez oluyor.

Belirleyici olan tek şey şu: **değişiklik hedefte kalıntı bırakıyor mu?**

### Kalıntı bırakan değişiklik

Metot taşınır ama yerine devredici bir sarmalayıcı konur; attribute taşınır ama
yerine yenisi gelir; bağımlılık taşınır ama yerine yeni sınıf referansı gelir.

Bu durumda `NOM`, `LCOM4` ve `DCC` **yerinde sayar** ve modeller bunu neredeyse
hiç öngörmez. 5b'de cephe kuran her öneri `NOM`'da ıskaladı.

### Kalıntı bırakmayan değişiklik

Metotlar gerçekten gider. O zaman aynı üç metrik gerçekten hareket eder ve
tahmin tutar.

5b vaka 6: `notify`, `sent_count`, `reset_sent` silindi → `NOM down` tuttu,
4/4.
5b vaka 5: aynı hedef, aynı model, cephe kuruldu → `NOM down` ıskaladı, 2/4.

Aynı sınıf, aynı refactoring türü, tek fark sarmalayıcının kalıp kalmaması.

### `WMC` neden ayrı

`WMC` toplamsaldır ve **kalıntıdan da etkilenmez**: 26 metodu sarmalayıcıya
çevirmek her birini CC=1'e indirir, dolayısıyla toplam yine düşer. Bu yüzden
`WMC` her iki değişiklik türünde de tahmin edilebilir kalıyor ve %83 ile en
yüksek.

Eski belgenin "Sınıf A" sezgisi burada doğruydu; yanlış olan aynı sezgiyi
`NOM`'a uygulamamaktı — `NOM` da bir sayımdır, ama kalıntıya duyarlıdır.

---

## Sınıflandırma (v2)

Metriğe değil, **(metrik, değişiklik türü) çiftine** uygulanır.

| Metrik | Kalıntısız değişiklik | Kalıntılı değişiklik |
|---|---|---|
| WMC | tahmin edilebilir | tahmin edilebilir |
| NOM | tahmin edilebilir | **edilemez** |
| LCOM4 | tahmin edilebilir | **edilemez** |
| DCC | kısmen | **edilemez** |
| LOC, PARAMS, CC | tahmin edilebilir | (fonksiyon hedeflerinde kalıntı seyrek) |

`DCC` "kısmen"dir çünkü kalıntısız bir çıkarma bile yerine yeni sınıf
referansı koyabilir — 5b'de dört kez `DCC` sabit kaldı, model iki kez `up` iki
kez `down` tahmin etti ve dördünde de yanıldı.

---

## Raporlama kuralı (değişmedi)

**Her FINDINGS önce metrik başına raporlar.** Sınıf düzeyi özet ikincildir ve
artık iki boyutlu olduğu için tek bir yüzdeye indirgenemez: "Sınıf A doğruluğu"
diye bir sayı yoktur, "kalıntısız değişikliklerde NOM doğruluğu" vardır.

Değişiklik türü `verify` tarafından **otomatik tespit edilmez**. v2'de elle
sınıflandırılır ve vaka notlarına yazılır; v3'ün refactoring türü tespiti
(`02 §5`) bunu ölçülebilir hale getirecek.

---

## Yeni çürütme koşulu

Bu mekanizma da hipotezdir; 31 tahmine dayanır ve hücre başına 1-6 gözlem
içerir.

Çürütülmüş sayılır eğer: kalıntı bırakan bir değişiklikte `NOM` ya da `LCOM4`
tutarlı biçimde doğru tahmin edilirse, **ya da** kalıntısız bir değişiklikte
aynı metrikler tutarlı biçimde yanlış çıkarsa.

v3'ün LensBench'i bunu koşul başına ≥50 tahminle sınayacak; şu anki sayılar
işaret düzeyindedir.

---

## `04`'e uygulanacak değişiklik

`§ 2.5`'in tamamı bu belgeyle değiştirilir. `schema_version` artmaz: bu bir
rapor alanı değil, analiz sözleşmesidir.

Ek olarak `§ 9` (deney kayıt standardı) şunu ister: her uygulanmış vaka için
`change_shape: residue | no_residue` alanı, elle doldurulur ve gerekçesi vaka
notunda durur.
