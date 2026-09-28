# `analysis` paketinde mutation testing (sertleştirme Blok 4, madde 3)

Betik: `mutation.py`. Sonuç: `results/mutation.json` (son durum),
`results/mutation-before-tests.json` (test eklenmeden önceki koşu).

## Yöntem

Plan `mutmut run --paths-to-mutate src/rlens/analysis` diyordu. mutmut 3
Windows'ta yalnızca WSL içinde çalışıyor. Bu makinede WSL'deki tek dağıtım
`docker-desktop` ve içinde Python yok. Docker servisi de kapalıydı ve
kullanıcının makinesinde kendiliğinden başlatılmadı. Aracın kendisi gibi
yalnızca `ast` kullanan küçük bir üreteç yazıldı.

- **Operatörler:** `<`↔`<=`, `>`↔`>=`, `==`↔`!=`, `in`↔`not in`,
  `is`↔`is not`; `+`↔`-`, `*`→`+`; `and`↔`or`; `not x`→`x`; tamsayı `n`→`n+1`;
  `True`↔`False`; `return x`→`return None`.
- **Yalıtım:** `src/rlens` her işçi için geçici bir dizine kopyalanır; özgün
  dosyalara dokunulmaz. Testlerin kopyayı içe aktardığı her koşudan önce
  denetlenir. Mutant dosya `ast.unparse` ile yazılır. **Taban koşusu:**
  değiştirilmemiş ama `unparse` edilmiş paket kendi testlerini geçmeli;
  geçmezse betik durur.
- **Koşu:** Her mutant için `pytest tests -x`, 8 işçi, mutant başına 180 sn
  zaman aşımı. Zaman aşımı "yakalandı" sayılır (2 mutant: sonsuz döngü).
- **Kayıt:** Her sonuç anında `.mutation-journal.jsonl`'e (git dışı) yazılır.
  Anahtar, dosyanın içerik özetini taşır. İlk koşu bir oturum kapanırken
  200. mutantta kesildi ve sonuç kaybolmuştu; kayıt bunun için eklendi.

Skor mutmut'unkiyle birebir karşılaştırılamaz (operatör kümesi farklı);
kendi içinde tekrar üretilebilir.

## Sonuç

| | Mutant | Yakalanan | Skor |
|---|---:|---:|---:|
| Test eklenmeden önce | 745 | 635 | %85.2 |
| Son durum | 745 | 689 | %92.5 |

Hedef (≥ %80) test eklenmeden de sağlanıyordu. Hayatta kalan 110 mutantın
her biri incelendi; 54'ü yeni testlerle öldürüldü
(`tests/test_mutation_survivors.py`, 39 test).
Kalan 56'nın gerekçesi aşağıda.

Son koşu, önceki koşularda yakalananları kayıttan aldı ve yalnızca hayatta
kalanları yeni testlerle yeniden koştu. Bu geçerli: test eklemek bir
mutantı yalnızca öldürebilir, diriltemez.

## Testlerin kapattığı boşluklar

Bunlar gerçek davranışlardı ve hiçbir test sınamıyordu:

- **LV-DIR/LV-SKIP sınırı:** Komşu iki katman arasında iki yönde de izin
  yoksa ihlal türü LV-DIR mi (tam 1 derinlik farkı).
- **Döngü ihlali:** `source`, `target` ve katmanları; mevcut testler yalnızca
  `members`'a bakıyordu.
- **`arch` notları:**
  - "match no declared prefix" notunun sayısı ve beyan yokken hiç
    çıkmaması;
  - annotasyonsuz sınıf sayısı, katmanı bilinmeyen modülün sayılmaması.
- **Derinlik (`graph`):** Döngü bileşeni kendine kenar alsaydı döngünün
  aşağısındaki modüllerin derinliği yanlış çıkardı. Döngünün kendi derinliği
  doğru kaldığı için mevcut test bunu göremiyordu.
- **Sınıf metrikleri:**
  - docstring'den sonra gerçek kodu olan metot taslak (stub) değildir;
  - `Annotated[T, "Ad"]` yalnızca `T`'yi sayar (metadata bir proje sınıfının
    adı olduğunda ayrım görünür);
  - `__slots__`'ta sabit olmayan eleman taramayı düşürmez;
  - anotasyon kapsamı tam eşikteyken CAM hesaplanır.
- **Giriş noktaları:** Ad ya da nitelik olmayan dekoratör, parantezsiz
  `@app.command`, çıplak `@command` ve `@command()`, sahibi tanınmayan
  `option("--x")`, argümansız `option()`; yalnızca yol anahtar kelimeleri
  okunur.
- **LOC:** Fonksiyondan hemen sonraki kod satırı sayılmaz.
- **İçe aktarma:** Zayıf kenarlar varsayılan olarak dahil, istenirse hariç;
  `edges_between`; boş hedef; noktalı kökün son parçası; kısmen çözülen bir
  import çözülemedi sayılmaz.
- **Parser:** Okunamayan yol, satır numaralı sözdizimi hatası,
  `RecursionError` (3.14'te `1+1+…` 200 bin terimle ulaşılıyor).
- **Kokular:**
  - `data_class`'ın WMC ve erişimci oranı sınırları;
  - `feature_envy` eşitlikte ada göre seçer, oran iki basamağa yuvarlanır
    (kanıt alanı prompt'a gider);
  - `layer_misfit` güven sınırı, kanıttaki `module_has_violation`, ve
    `detect_class_smells` üzerinden tetiklenme;
  - döngü tek başına `layer_misfit` üretmez.
- **Diğer:** Modül fonksiyonunda `self` adlı ilk parametre düşmez.
  `ARCH_SCHEMA_VERSION` sabit.

**Kod değişikliği:** Aynı önek iki katmanda beyan edilirse atama beyan
sırasına kalıyordu, sessizce (`architecture.py:208`, `>`↔`>=` mutantı eşitliği
gösterdi). Artık config hatası (`config.py`, eşleştirmeyle aynı
normalleştirme).

## Hayatta kalan 56 mutant

| Kategori | Adet | Neden test yok |
|---|---:|---|
| `@dataclass(frozen=True)` → `False` | 12 | Hiçbir kod bu nesneleri değiştirmiyor; donmuşluk bir koruma, davranış değil. |
| Varsayılan değerler | 11 | `is_method=False` (6): çağıranlar değeri hep veriyor, ya da fark yalnızca ilk parametre `self`/`cls` iken çıkıyor. Model alanları (`dynamic_sites`, `stub_methods` vb., 4) ve `Violation.tentative` (1): yapıcılar hep dolduruyor. |
| Değere göre eşdeğer | 9 | Tarjan sayacının başlangıcı ve artışı (3): yalnızca göreli sıra önemli. Döngü katman aramasındaki yedek (2): her modülün bir ataması var. Takma ad koşulunda `and`→`or`: DCC proje sınıfı üyeliğini sonra yine denetliyor. `Annotated` dilimi hep ≥ 2 elemanlı bir tuple. `rsplit(".", 2)[-1]` aynı son parçayı verir. `elif` sonrası `max(…, current + 1)`: iç çağrı bunu zaten döndürüyor. |
| Yuvarlama basamağı `4`→`5` | 9 | Değerler eşiklerle ya da 4 basamaklı gösterimle karşılaştırılıyor; beşinci basamak hiçbir kararı değiştirmiyor. (`feature_envy` oranı prompt'a gittiği için sabitlendi.) |
| Ulaşılamayan savunma dalları | 5 | `ast.unparse` çıktısı hep ayrıştırılır. `# pragma: no cover` dalı. Fonksiyon ve sınıfın hep gövdesi var. `adjacency()` her modülü anahtar yapar. `len == 1` dalı `> 1`'den önce döner. |
| `return False` → `return None` | 5 | Çağıranlar yalnızca doğruluk değerine bakıyor. |
| Katman çıkarımına bağlı | 4 | `is_tentative` ve `_tentative` yalnızca `INFERRED` kaynakla anlamlı; çıkarım henüz yok (v2.1 planı). Çıkarım gelince bu yollar test edilmeli. |
| Önek eşitliği | 1 | Eşit uzunlukta iki önek artık config'te reddediliyor; eşitlik oluşamaz. |

**Sınırlılık:** Üreteç değer ve operatör düzeyinde çalışır. Satır silme,
çağrı atlama ya da argüman değiştirme gibi daha kaba mutasyonlar yok. Skor
bu operatörlere karşı test gücünü ölçer, testlerin her hatayı yakalayacağını
değil.
