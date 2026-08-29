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
- HTML rapor çıktısı, web arayüzü, veritabanı.
- IDE eklentisi.

## Analiz
- Tip çıkarımı (inference) ile DCC/CAM doğruluğunu artırmak — muhtemelen
  üçüncü parti bir araca bağımlılık gerektirir; M1'in "yalnızca `ast`" kararına
  aykırıdır.
- Kalıtım hiyerarşisi metrikleri (DIT, NOC).
- Modül/paket düzeyi coupling metrikleri.

## Sağlayıcılar
- Çekirdek Groq + Ollama'dır. Gemini ve Anthropic adapter'ları opsiyoneldir
  (Faz 4). Diğer sağlayıcılar `providers/base.py` sözleşmesini uygulayan
  ~30 satırlık dosyalardır.

## Takım özellikleri
- Çoklu kullanıcı, paylaşılan rapor deposu, kalite kapıları (quality gates).
