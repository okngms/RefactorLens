# `god_class` kör etiketleri — sonuç

v2.2 §5b, K9/K10'un açık bıraktığı soru: `god_class` kapısının "birden fazla
sorumluluk" iddiası, kapıdan bağımsız bir yargıyla tutuyor mu; R4 (durumlu
metotlarda LCOM3-HM, `stateless-gate.md`) bugünkü kapıdan iyi mi? Örneklem ve
kılavuz etiketlerden önce yazıldı (`god_class_sample.py`,
`god-class-labeling.md`). Karar `docs/v2-tanim-kararlari.md` K17.

```bash
python experiments/hardening/god_class_sample.py summary
```

Özet `results/god-class-summary.json`; kararlar `god-class-verdicts.json`;
ham yanıtlar `yanitlar.md`.

## Etiketleyici ve işleme

- **Etiketleyici: Claude Sonnet 5**, her sınıf ayrı bir sohbette
  (`yanitlar.md`'nin ilk satırı). İnsan değil. Örneklemi çeken ve kapıları
  ölçen asistandan ayrı bağlamda çalıştı; hangi girdiyi gördüğü (yalnız kod
  mu, kılavuz mu) bu depodan doğrulanamıyor — notlar metot adlarına ve
  gövdelere dayanıyor.
- 32 yanıtın 32'si ayrıştı; kimlikler örneklemle sırasıyla birebir aynı.
  Bir onarım yapıldı: #01'in `note` metninde kaçışsız çift tırnak vardı
  (`raise "..."`), JSON geçersizdi; iki tırnak kaçışlandı, karar ve
  sorumluluklar değişmedi. `yanitlar.md`'ye dokunulmadı.
- `summary` kararları doğruladı (her `god` en az iki sorumluluk adlandırıyor).

## Sonuç

Kararlar: 4 `god`, 22 `not_god`, 6 `unsure`.

| Hücre | popülasyon | örneklem | god | not_god | unsure |
|---|---:|---:|---:|---:|---:|
| ikisi de ateşliyor | 53 | 8 | 1 | 5 | 2 |
| yalnız bugünkü kapı | 40 | 8 | 0 | 7 | 1 |
| yalnız R4 | 17 | 8 | 1 | 6 | 1 |
| hiçbiri | 46 | 8 | 2 | 4 | 2 |

`god` etiketliler: `yt-dlp.YoutubeDL` (ikisi), `healthchecks.Profile`
(yalnız R4), `mealie.RecipeController` ve `healthchecks.Check` (hiçbiri).

Hücre büyüklükleriyle ağırlıklı (unsure hariç):

| Kapı | kesinlik | duyarlılık |
|---|---:|---:|
| Bugünkü (LCOM4 ≥ 3) | %9.5 | %33.2 |
| R4 | %16.1 | %42.4 |

Kararı verilmiş örneklerde kesin binom aralıkları (Clopper–Pearson, %95):
bugünkü kapının ateşlediği hücrelerde 1/13 god (%0.2–%36), R4'ün ateşlediği
hücrelerde 2/13 (%1.9–%45), hiçbirinin ateşlemediği hücrede 2/6 (%4.3–%78).
Büyük sınıfların tahmini %17'si (156'da ~27) etiketleyiciye göre god.

## Değerlendirme

1. **R4 bugünkü kapıdan iyi olduğunu göstermedi.** Aradaki fark tek bir sınıf
   (`healthchecks.Profile`); aralıklar neredeyse tümüyle örtüşüyor. R4'ün
   kabulü için "üstünse" koşulu yazılmıştı ama marj tanımlanmamıştı; 4 pozitifle
   hiçbir marj savunulamaz. **R4 eklenmez.**
2. **İki kapının da kesinliği düşük.** Kapının ateşlediği 13 kararlı sınıftan
   yalnızca 1'i (bugünkü) ya da 2'si (R4) god. Etiketleyiciye göre büyük
   sınıfların çoğu tek bir sorumluluğun uzun kataloğu ya da framework'ün dikte
   ettiği arayüz: ziyaretçiler, DataFrame benzeri API'ler, GraphQL mutasyon
   tabanları. Kılavuz bu durumları açıkça `not_god` sayıyordu; düşük kesinlik
   kılavuzun SRP tanımının doğrudan sonucu.
3. **Kohezyon koşulu god sınıfları zenginleştirmiyor.** En yüksek god oranı
   hiçbir kapının ateşlemediği hücrede (2/6). Örneklem küçük; "kohezyon koşulu
   ters çalışıyor" denemez, ama "çalışıyor" hiç denemez.
4. **Sonuç `god_class` kokusu için:** bugünkü haliyle koku, "bölünebilir sınıf"
   iddiasını bu etiketleyiciye göre büyük sınıfların küçük bir kısmında
   taşıyor. Kapıyı değiştirmek (yeni koku sürümü) için bu kanıt yetmez: tek
   etiketleyici, LLM, 26 kararlı etiket.

## Sınırlılıklar — değerlendirmeyle birlikte okunmalı

- **Etiketleyici bir LLM.** Proje, LLM'lerin kendi önerileri hakkındaki
  yargısını ölçüyor; ölçüyü bir LLM yargısıyla doğrulamak döngüseldir.
  Etiketleyici bu projeyi tasarlayan asistanla aynı model ailesinden (Claude);
  ortak önyargılar dışlanamaz.
- **Tek etiketleyici, uyum ölçülmedi.** Kılavuzun istediği ikinci
  etiketleyici ve Cohen κ yok.
- **Küçük örneklem:** 32 sınıf, 26 kararlı, 4 pozitif.
- **Körlük doğrulanamıyor:** etiketleyicinin kapı sonuçlarını görmediği
  varsayımı sohbet düzeninden geliyor, kayıttan değil.

## Sonraki adım

Bir kapı değişikliği düşünülecekse önce: aynı 32 sınıfı kör etiketleyen bir
**insan** ve LLM ile uyum (κ). İnsan etiketleri bu sonucu doğrularsa
`god_class`'ın yeniden tanımı (boyut + başka bir sinyal) v2.2 sonrasının
konusudur; bugünkü kanıt alanları FINDINGS için donmuş olduğundan yeni bir koku
sürümü olarak.
