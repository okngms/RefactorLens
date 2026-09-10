# STATUS — 2026-09-09

## Sürüm
v1.0.0 PyPI'da. v2.0.0 yayına hazır: sürüm, README, şema sürümleri ve
Trusted Publishing workflow'u yerinde, `dist/` yerelde `twine check`'ten geçti.
**Tag atılmadı, PyPI'a yüklenmedi.**

## Bitenler
- v2 Aşama 0, 1, 1b, 3, 4; 5a toplama, 5b (12 vaka), FINDINGS-2.
- v2 düzeltme listesi ve `docs/SPEC-duzeltme-2.5*`; metrik sınıflandırması
  kendi koşuluyla çürütüldü, gruplama "kalıntı bırakıyor mu"ya çevrildi.
- **v2.0.0 yayın hazırlığı** (bu oturum, `docs/v2-kalan-kapsam.md §5`):
  - `__version__` 2.0.0; classifier Beta; proje URL'leri kanonik yazıma çekildi.
  - `ADVICE_SCHEMA_VERSION` 1 → 2. Gerekçe `04 §1`'de: alan eklemek sürüm
    artırmaz, ama kalibrasyon `confidence`'a dayanıyor ve v1 raporlarında bu
    alan yok — sürüm etiketi olmadan "güven verilmemiş" ile "eski format"
    ayırt edilemiyor. `experiments/v2/` ham verisi 1 taşımaya devam eder.
  - README: `<user>` → `okngms`, sekiz göreli link mutlak URL'ye (PyPI'da
    depo ağacı yok), durum satırı ve Roadmap v2, "future versions will
    suggest" bayat cümlesi düzeltildi.
  - AGENTS.md: üç kilitli karar (çıkarım beyanı ezmez; `confidence`
    opsiyoneldir ve yokluğu öneriyi düşürmez; `suspicious` davranış kapısını
    ikame etmez). STRUCTURE.md v2 dosyalarıyla, FUTURE.md K6 maddesiyle
    güncellendi.
  - `.github/workflows/publish.yml`: 3.11/3.12/3.13 matrisi, ruff + iki test
    suite'i; tag'de OIDC ile yayın, `needs: test`.
  - `tests/test_packaging.py` (7 test): placeholder yok, her link mutlak,
    sürüm tek kaynaktan, entry point ve `readme` alanı yerinde.
  - Hijyen: `ruff format` iki dosyada; ham deney verisi ruff dışına ve
    sdist dışına (387 → 143 girdi). Açılmış sdist'te iki suite de yeşil.
- Durum: 1059 paket testi, 91 fikstür testi, ruff temiz.

## Sıradaki iş
1. **PyPI'da Trusted Publisher tanımla** (elle, bir kez): owner `okngms`,
   repo `RefactorLens`, workflow `publish.yml`, environment `pypi`; GitHub'da
   aynı adla environment.
2. `git tag v2.0.0 && git push origin main --tags` → workflow yayınlar.
3. Yayın doğrulaması: temiz ortamda `pipx install refactorlens`,
   `rlens --version` 2.0.0 demeli; PyPI sayfasındaki linkler açılmalı.
4. Sonra `docs/v2-sertlestirme.md` Blok 1'den devam.

## Okunacak dokümanlar (sırayla)
AGENTS.md → bu dosya → docs/v2-sertlestirme.md
Deney protokolü: docs/v2-duzeltme-asama5.md. Metrik sınıfları:
docs/SPEC-duzeltme-2.5.md ve SPEC-duzeltme-2.5-v2.md.

## Açık kararlar / bilinen sorunlar
- **Sertleştirme yayından sonraya kaldı.** `docs/v2-sertlestirme.md` v2.0.0'ı
  beş bloğun sonrasına koyuyordu; sıra bilerek değiştirildi. Sonucu: Blok 1'in
  "metrikler gerçek projelerde nerede sapıyor" tablosu olmadan çıkıyoruz,
  README'nin Limitations bölümü hâlâ yalnızca fikstüre dayanıyor. Bloklar
  v2.1'e taşındı; kabul kriterleri değişmedi.
- Katman çıkarımı v2.1'de (beyan + import-linter ile çıkıyoruz).
- `tests/test_cli.py::test_without_a_baseline_it_says_what_to_do` terminal
  genişliğine bağımlı; workflow `COLUMNS=100` sabitliyor, testin kendisi hâlâ
  kırılgan (Blok 4).
- CI matrisi hiç koşmadı; ilk push'ta 3.11 ve 3.13'te sürpriz çıkabilir.
  Yerelde yalnızca 3.12 denendi.
- `pyproject.toml` 3.14 classifier'ı taşıyor ama matriste 3.14 yok — ya matrise
  eklenmeli ya classifier düşmeli (Blok 4).
