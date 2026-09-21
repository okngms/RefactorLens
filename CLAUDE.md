@AGENTS.md

## Oturum akışı (Claude Code)

1. `docs/STATUS.md`'yi oku. "Sıradaki iş" ve "Okunacak dokümanlar"ı söyler;
   yalnızca onları oku. Kodu tümüyle okuma; iş için gereken modülleri oku.
2. Yapacaklarını madde madde listele, onay bekleme, kodlamaya geç.
3. Her değişiklik testiyle gelir. Şu dördü yeşil olmadan iş bitmiş sayılmaz:
   `ruff check .`, `ruff format --check .`, `pytest tests`,
   `pytest examples/messy_project/tests`.
4. Oturum sonunda `docs/STATUS.md`'yi güncelle (bitenler, sıradaki iş, açık
   sorunlar). **Commit ve push yapma**; kullanıcı yapar. Bunun yerine kısa bir
   özet ver: değişen dosyalar, ne yapıldığı ve neden, test sonucu, ve tek
   satırlık İngilizce commit mesajı önerisi.

## Kurallar

- AGENTS.md'deki kilitli kararlar ve invariant'lar tartışmaya açılmaz.
- Kapsam dışı fikir `FUTURE.md`'ye yazılır, uygulanmaz. Aktif sürüm kapsamı ve
  sıradaki iş `docs/STATUS.md`'nin gösterdiği dokümandır.
- Deney protokolü başladıktan sonra `prompts.py`, `smells.py` kanıt alanları ve
  `validate_constraints` değişmez.
- Metrik anlamını değiştiren her karar `docs/v2-tanim-kararlari.md`'ye gerekçe,
  maliyet ve ölçülmüş etkiyle yazılır; alan anlamı değişirse `schema_version`
  artar (`docs/04` §1).
- Belgeye yazılan her sayı bir çıktıyla doğrulanır. Kodu okumadan "çünkü ..."
  diye yorum yazılmaz; doğrulanmamışsa "incelenmedi" denir.
- Türkçe yaz; kod, tanımlayıcılar ve commit mesajları İngilizce.

## Ortam

- Sertleştirme betikleri (`experiments/hardening/`) referans projelere ihtiyaç
  duyar: `python experiments/hardening/corpus.py fetch` (bir kez, ~850 MB,
  `.cache/` git dışıdır). Karşılaştırma betikleri ayrıca
  `pip install radon==6.0.1 cohesion==1.2.0` ister; ikisi paket bağımlılığı
  değildir, testler onlarsız da geçer (10 test atlanır).
- Bu depoda alt dizin taramak (`rlens scan src/rlens`) kökteki `rlens.yaml`
  yüzünden 0 dosya bulur; kendini taramak için kökten `rlens scan .` kullan.
