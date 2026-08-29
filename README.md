# RefactorLens

> **Durum: Faz 0 tamamlandı.** Paket kuruluyor ve `rlens` komutu çalışıyor, ancak
> metrik motoru henüz yazılmadı — `rlens scan` şu an çıkış kodu 3 ile
> "henüz uygulanmadı" der. Kullanılabilir ilk sürüm Faz 2'de yayınlanacak.

RefactorLens is a metric-grounded AI code review CLI: it computes
object-oriented design metrics from your Python codebase, uses them as evidence
to generate LLM refactoring suggestions, and then checks whether the model's
own predicted effect actually happened.

## Neden farklı

Sıradan "AI'ya kodunu göster" araçlarından iki katmanla ayrılır:

1. **Metrik temelli istem (metric-grounded prompting)** — modele ham kod tek
   başına verilmez. Önce statik analizle hesaplanan metrikler kanıt olarak
   sunulur ve her önerinin bir metriğe bağlanması zorunlu tutulur.
2. **Ölçüm döngüsü (verify loop)** — model her öneride ölçülebilir bir
   **tahmin** vermek zorundadır ("bu değişiklik LCOM4'ü düşürür, DCC'ye
   dokunmaz"). Değişiklik uygulandıktan sonra araç iki soruyu birden yanıtlar:
   kalite gerçekten arttı mı, ve **modelin tahmini tuttu mu**.

## Yol haritası

| Faz | İçerik | Sürüm |
|---|---|---|
| 0 | Paket iskeleti, config, test zemini | — |
| 1 | Analiz motoru (`scan`) | — |
| 2 | **PyPI yayını** | v0.1.0 |
| 3 | AI önerileri (`advise`) | v0.2.0 |
| 4 | Ölçüm döngüsü (`verify`) | v0.3.0 |
| 5 | Deney ve bulgular | v1.0.0 |

Kapsam dışı fikirler: [FUTURE.md](FUTURE.md).

## Kurulum (geliştirme)

```bash
git clone <repo>
cd refactorlens
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
rlens --version
```

Faz 2'den sonra önerilen kurulum `pipx install refactorlens` olacaktır —
RefactorLens bir kütüphane değil, CLI aracıdır.

## Testler

İki ayrı takım vardır:

```bash
pytest tests                        # paketin kendi testleri
pytest examples/messy_project/tests # örnek projenin davranış testleri
```

`examples/messy_project` bilerek kötü tasarlanmış bir örnek projedir
(bkz. `examples/messy_project/SMELLS.md`). Davranış testleri, refactoring
önerileri uygulandığında kodun hâlâ çalıştığını kanıtlar: **davranış testleri
geçmeden hiçbir metrik delta raporu geçerli sayılmaz.**

## Gizlilik

`scan` hiçbir veri göndermez. `advise` (Faz 3) kullanıldığında seçilen kod
parçaları yapılandırılan LLM sağlayıcısına gönderilir; hassas kod için lokal
çalışan Ollama önerilir.

## Güvenlik

Araç hedef kodu **çalıştırmaz**, yalnızca `ast` ile ayrıştırır.

## Lisans

MIT
