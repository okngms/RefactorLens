# FUTURE — kapsam dışı fikirlerin park alanı

Proje kapsamı teknik dokümanda kilitlidir. Buraya yazılan hiçbir şey projeye
eklenmez; amaç fikri kaybetmemek ama kapsamı şişirmemektir.

## Dil desteği
- **C# desteği** (v2 için birincil aday). OO metrikleri C#'ta Python'dakinden
  daha doğal hesaplanır — `null` dönen metrik sayısı düşer.
- Java desteği.

## Otomasyon
- **Auto-fix / patch uygulama.** Faz 3'te araç bilerek yalnızca öneri sunar.
  Otomatik uygulama, davranış testi zorunluluğunu ve "en dar yorum" kuralını
  yeniden düşünmeyi gerektirir.
- GitHub Action paketi.
- Git pre-commit hook entegrasyonu (Faz 3'te README notu yeterli).

## Raporlama
- **Tam `rlens history`** (çok noktalı trend özeti). Faz 3'te yerini
  `scan --compare-last` aldı. Tam sürüm için gereken tasarım kararları:
  proje kimliği, rapor isimlendirme şeması, `reports/` dizininin paylaşılabilir
  hale getirilmesi.
- **`verify`'da `rlens_version` uyarısı.** İki rapor aynı `schema_version`'ı
  taşıyıp farklı `rlens_version`'dan geliyorsa, uygulama düzeltmeleri (bkz.
  sertleştirme Blok 1: `@overload`, string annotation, `@staticmethod`) kod
  değişmeden delta üretebilir. Reddetmek değil, uyarmak. Kapsam dışı: Blok 1
  yeni özellik eklemez.
- HTML rapor çıktısı, web arayüzü, veritabanı.
- IDE eklentisi.

## Analiz
- Tip çıkarımı (inference) ile DCC/CAM doğruluğunu artırmak — muhtemelen
  üçüncü parti bir araca bağımlılık gerektirir; M1'in "yalnızca `ast`" kararına
  aykırıdır.
- Kalıtım hiyerarşisi metrikleri (DIT, NOC).
- **PARAMS'ta yalnızca-anahtar parametreler.** `*` sonrası parametreleri ayrı
  saymak `too_many_params`'ın %24.9'unu kaldırırdı (K8,
  `experiments/hardening/thresholds.md`). Tanım değişikliği, şema artışı;
  v2.2'nin dokuz maddesinden geçmeli: kaybolan kokuların gerçekten yanlış
  pozitif olduğu gösterilmeden uygulanmaz.
- Python'a özgü çok düzeyli kalite modeli: metrikleri ve kokuları tek tek
  raporlamak yerine, Python'un kendi tasarım deyimlerine (duck typing,
  `@property`, dataclass, modül düzeyi fonksiyon) göre ağırlıklandırılmış bir
  kalite modeli tanımlamak ve doğrulamak. Java için kalibre edilmiş eşiklerin
  Python'a taşınması v1/v2'nin bilinen sınırlılığı; bunu düzeltmek ayrı bir
  araştırma sorusu ve v3 çerçevesine aittir.

## Sağlayıcılar
- Çekirdek Groq + Ollama'dır. Gemini ve Anthropic adapter'ları opsiyoneldir
  (Faz 4). Diğer sağlayıcılar `providers/base.py` sözleşmesini uygulayan
  ~30 satırlık dosyalardır.

## Takım özellikleri
- Çoklu kullanıcı, paylaşılan rapor deposu, kalite kapıları (quality gates).
