# STATUS — 2026-09-09

## Sürüm
v1.0.0 PyPI'da. v2.0 geliştirme aşamasında.

## Bitenler
- v2 Aşama 0 (fikstür, config, bütçe/önbellek), 1 (grafik, beyanlı katman, ihlaller),
  1b (`rlens arch`, import-linter), 3 (kokular, arayüz, scan entegrasyonu),
  4 (mimari bağlam, `rejected`, confidence, Brier/ECE, Goodhart, deltalar).
- 5a toplama betiği (`experiments/run_advice_v2.py`) hazır, hedefler sabitlenmiş, koşulmadı.

## Sıradaki iş
`docs/v2-duzeltme-listesi.md` — sırayla D1, D2, D5, D3; sonra prompt dondurulur
(prompt_hash kaydı), 5a başlar. D4, D6 5a koşarken.

## Okunacak dokümanlar (sırayla)
AGENTS.md → bu dosya → docs/v2-duzeltme-listesi.md → docs/v2-kalan-kapsam.md
Deney protokolü: docs/v2-duzeltme-asama5.md. Metrik sınıfları: docs/SPEC-duzeltme-2.5.md.

## Açık kararlar / bilinen sorunlar
- Katman çıkarımı v2.1'e ertelendi; v2.0 beyan + import-linter ile çıkar.
- `tests/test_cli.py::test_without_a_baseline_it_says_what_to_do` terminal genişliğine bağımlı (flaky).
- 4 fikstür test dosyası `ruff format` dışında.
- README, `__version__`, `<user>` placeholder v2.0.0 yayın listesinde.

"Sıradaki iş: 5b ve FINDINGS-2 tamamlandıysa `docs/v2-sertlestirme.md` Blok 1'den başla; v3'e bu doküman kapanmadan geçilmez."