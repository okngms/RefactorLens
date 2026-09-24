# Gerçek projede dayanıklılık ve süre (sertleştirme Blok 2)

`docs/v2-sertlestirme.md` Blok 2. Betik: `robustness.py`. Çıktılar:
`results/robustness.json` (tekrar üretilebilir), `results/robustness-timing.json`
(ortama bağlı), `results/robustness-tables.md` (proje başına tablo).

Korpus: `corpus.txt`'teki 26 proje, dört tür. Her projede üç komut **CLI
olarak**, alt süreçte koşuldu: `rlens scan`, `rlens arch`,
`rlens advise --dry-run`. Config proje başına açıkça yazıldı (config tuzağı,
`corpus.py`). Makine: Windows 11, 8 mantıksal işlemci, Python 3.14.

## 1. Çökme ve atlanan dosya (madde 1)

| | Sonuç |
|---|---|
| Çıkış kodu | 26 projede üç komut da 0 |
| `skipped_files` | 0 dosya (encoding, sözdizimi sürümü, ikili dosya: hiçbiri) |

Korpusun commit'leri sabit ve hepsi Python 3.14 ile ayrıştırılabiliyor; bu
bir dayanıklılık kanıtı değil, bu korpusta sorun çıkmadığının kaydı.
Bozuk dosyanın komutu düşürmediği `tests/test_cli.py` ve `test_parser.py`'de
zaten sabit.

## 2. Süre (madde 2)

En büyük dört proje, uçtan uca (süreç başlangıcı dahil), saniye:

| Proje | scan | arch | advise --dry-run |
|---|---:|---:|---:|
| yt-dlp | 25.5 | 5.7 | 19.2 |
| saleor | 17.5 | 6.1 | 14.1 |
| netbox | 17.0 | 5.4 | 13.3 |
| mypy | 10.9 | 2.3 | 10.4 |

Hedef (en büyük projede `scan` < 30 sn) **sağlanıyor ama geniş payla değil.**
yt-dlp'nin `scan` süresi aynı gün beş ölçümde 23.3–29.9 sn arasında oynadı.
İlk koşuda 35.0 sn ölçüldü; o sırada makinede test takımı da koşuyordu,
tek başına tekrarlandığında 23–25 sn çıktı. Bu yüzden tabloya boş makinede
yapılan son koşu yazıldı.

**Nereye gidiyor (yt-dlp, 2323 sınıf, aşama aşama):** `scan_project` 18.6
sn, terminal render 2.9 sn, JSON yazımı 0.1 sn. Profil (cProfile, oranlar):
zamanın çoğu `measure_class` içinde, AST'nin her metrik için yeniden
gezilmesinde (`ast.iter_child_nodes` 26 milyon çağrı). Ayrıştırma (parse)
darboğaz değil.

**Yapılan:** `data_class` tespiti, sınıfın public arayüzünü her sınıf için
ikinci kez kuruyordu; artık yalnızca sayısal koşulları (NOM ≤ 5, WMC, DAM)
geçen sınıfta kuruyor. Sonuç aynı: korpus envanteri
(`corpus-inventory.json`, koku sayıları dahil) yeniden üretildi, git'teki
dosyayla birebir. Kazanç küçük: 19.2 → 18.6 sn.

**Yapılmayan ve neden:**

- **Dosya hash'li tarama önbelleği.** Bir dosyanın ölçümü yalnızca o dosyaya
  bağlı değil: DCC projenin tüm sınıf adlarına (`project_classes`), import
  takma adları proje modül kümesine, katman ve Ca/Ce tüm import grafiğine
  bağlı (`analysis/scanner.py`, iki geçiş). Dosya başına önbellek, başka bir
  dosyada sınıf eklendiğinde bayat DCC döndürür. Doğru bir önbellek bu
  proje-geneli girdileri de anahtara katmalı; bu da neredeyse her değişiklikte
  tümünü geçersiz kılar. Parse tek başına önbelleklenebilir ama darboğaz
  parse değil.
- **Paralel ölçüm.** Sınıf ve fonksiyon ölçümü, proje-geneli sözlükler
  hazırlandıktan sonra modül başına bağımsız; süreç havuzuyla paralel
  çalışabilir. Hedef sağlandığı için bu blokta yapılmadı. Korpus büyür ya da
  hedef bir kez aşılırsa ilk yapılacak iş bu (FUTURE.md, profil sayılarıyla).

## 3. Katmansız proje (madde 3)

Beyan ve import-linter yokken `arch`: tüm modüller `unknown`, kenar ihlali
yok, döngüler ve Ca/Ce yine raporlanıyor. Bu zaten böyleydi; uçtan uca test
yoktu. Eklendi: `tests/test_cli.py::TestUndeclaredLayers` (4 test, Ca/Ce elle
hesaplandı). Not metni kullanıcıya ne yapacağını söylüyor: yalnızca döngüler
denetlendi; katman kuralları için `rlens.yaml`'da `arch.layers` ya da bir
import-linter katman sözleşmesi.

## 4. `advise` prompt boyutu ve kesme politikası (madde 4)

Politika (`advise/context.py`):

1. Hedefin tam kaynağı gönderilir. Bağımlı sınıfların yalnızca imzaları
   eklenir.
2. Bağlam **`min(advise.max_context_tokens, budget.max_tokens_per_call)`**
   bütçesiyle kurulur.
3. Bütçe aşılırsa önce bağımlı imzalar atılır, sonra hedef sınıfın en uzun
   metot gövdeleri kısaltılır (imzalar korunur).
4. Hâlâ aşılıyorsa (sınıfın iskeleti tek başına büyük) ya da hedef bir
   fonksiyonsa, çağrı yapılmaz: `--dry-run` ve gerçek koşu hedefin
   atlandığını söyler, rapor kısmi olduğunu yazar. Fonksiyon gövdesi
   kısaltılmaz: yarım bir fonksiyona verilen öneri havada kalır.
5. Kısaltılan her şey hem prompt'ta hem raporda listelenir.

**Bulunan iki hata:**

- **Varsayılanlar kendi içinde tutarsızdı.** Bağlam 12000 token bütçesiyle
  kuruluyor, çağrı tavanı 4000'di; aradaki boyutta kurulan her bağlam hiç
  sorulmadan atlanıyordu ve kırpma o aralıkta hiç çalışmıyordu. 2. kural bunu
  düzeltir. İki ayar da kullanıcıda kaldı; varsayılan değerler değişmedi.
- **Bütçe, gönderilen metni ölçmüyordu.** İmzalar atılırken imza bloğunun
  başlık satırı ve ayırıcıları hesaba katılmıyordu; httpx `BaseClient`
  bağlamı 4013 token çıktı ve atlandı. Artık kontrol ve gönderilen metin aynı
  fonksiyondan (`assemble`) geliyor. Değişmez testle sabit: bağlam ya sığar ya
  da kısaltılacak bir şey kalmamıştır (`test_context.py::TestBudgetInvariant`,
  68 bütçe).

**Etki** (74 hedef, 26 proje, varsayılan config):

| | Önce | Sonra |
|---|---:|---:|
| Gerçek koşuda atlanacak prompt | 31 | 10 |
| En az bir hedefi atlanan proje | 17 | 8 |
| Tüm hedefleri atlanan proje | 5 | 1 (pandas) |

Kalan 10'un 9'u sınıf iskeleti tavanı aşan sınıflar (pandas `DataFrame`
27858, `NDFrame` 18216, `Index` 13080; yt-dlp `InfoExtractor` 13418; mypy
`SemanticAnalyzer` 12224; saleor, flask, rich, pydantic birer sınıf, 4565–6083),
biri fonksiyon (whisper `transcribe`, 5305). "Önce" sütunu aynı betiğin
düzeltmeden önceki koşusu: `results/robustness-before-context-fix.json`
(kayıt; bugünkü kodla yeniden üretilemez).

Deney fikstürleri etkilenmez: en büyük prompt `messy_project`'te ~1747,
`layered_project`'te ~1590 token; iki sınırın da altında. Deney betikleri
(`run_advice*.py`) bağlamı kendi bütçesiyle kurar.

**Sınırlılık:** token tahmini karakter/4; gerçek tokenizer'a göre sapar.
Sayılar tahmin üzerinden, faturalandırılan token değil.
