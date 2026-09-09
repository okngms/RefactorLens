# v2 Sertleştirme — Yeni Özellik Öncesi Mevcut Sistemi Güçlendirme
### Uygulama zamanı: 5b ve FINDINGS-2 tamamlandıktan sonra, v2.0.0 yayınından önce, v3'ten önce

> **Amaç:** Yeni özellik eklemeden, bugün çalışan sistemi (scan/arch/advise/verify) gerçek projelerde doğru, dayanıklı ve anlaşılır hale getirmek. Çıktı: v2.0.0 yayını ve FINDINGS'lerin "Limitations" bölümlerinin tahminden ölçüme dönmesi.
> **Kilitli ilkeler değişmez.** Bu doküman metrik **tanımlarını** değiştirmez; yalnızca hatalı **uygulamaları** düzeltir ve farkları belgeler. Bir tanım değişikliği gerekirse `docs/04`'e işlenir, `schema_version` artar ve ayrı karar olarak kaydedilir.
> **Kapsam kilidi:** Buradaki beş bloğun dışına çıkılmaz; bulunan yeni fikir `FUTURE.md`'ye gider.

---

## Blok 1 — Metrik doğruluğu (en yüksek öncelik)

**Neden:** Metrikler iki fikstürde altın değerlerle doğrulandı; gerçek kodda nerede yanıldıkları bilinmiyor. Tez, "metrik uyarlamalarımız şu koşullarda şu kadar sapıyor" diyebilmeli.

**İş:**
1. **Referans proje seti** (`experiments/hardening/projects.txt`): boyut ve stil çeşitliliğiyle 10-15 açık kaynak Python projesi, **commit hash'iyle dondurulmuş**. Öneri: `requests`, `httpx`, `rich`, `pydantic` (v2 çekirdek), `fastapi`, `attrs`, `click`, `flask`, `sqlalchemy/orm` (alt paket), `black`, `mypy` (alt paket), `pandas/core/frame.py` çevresi. Seçim kriteri ve gerekçesi dosyada.
2. **Çapraz doğrulama:**
   - CC: `radon cc -j` çıktısıyla fonksiyon bazında birebir karşılaştırma (`experiments/hardening/compare_radon.py`). Her fark için: tanım farkı mı (`04 §2.3`'e göre beklenen) yoksa hata mı, sınıflandırılır.
   - Kohezyon: `cohesion` aracı ile sınıf bazında sıralama korelasyonu (Spearman); büyük sapmalar elle incelenir.
   - Kuplaj (DCC): otomatik referans yok; her projeden rastgele 3-4 sınıf, toplam **30-50 sınıf elle** sayılır, DCC'nin isim çözümleme hataları (yanlış pozitif/negatif) kategorilenir.
   - CAM: annotation kapsamı dağılımı raporlanır (projelerin yüzde kaçında CAM hesaplanabiliyor).
3. **Şüpheli noktalar özellikle test edilir** (her biri için `tests/test_metric_edges.py`'ye en az bir test):
   - DCC: yerel değişken/parametre adının bir sınıf adıyla çakışması; `import x as y`; `from . import` göreli importlar; string annotation (`"Order"`); `typing.TYPE_CHECKING` altındaki importlar.
   - LCOM4: `@property`; sınıf-düzeyi attribute'lar; `@dataclass`, `NamedTuple`, `Enum`, `TypedDict`'in otomatik `__init__`'i; `__slots__`; iç içe sınıf/fonksiyon.
   - CC: `match/case`, `async for/with`, iç içe comprehension, `try/finally`, dekoratörlü fonksiyon, `lambda`.
   - NOM/WMC: `@staticmethod`/`@classmethod`, `@overload` (çift sayım riski), `Protocol` ve `ABC` sınıfları, `__post_init__`.
   - `interface.py`: `__slots__` (D6), `@property` setter'ları, sınıf attribute'ı vs instance attribute'ı.
4. **Fark tablosu** (`experiments/hardening/metric-accuracy.md`): metrik × hata kategorisi × sıklık; hangi farkların tanım gereği olduğu, hangilerinin düzeltildiği, hangilerinin bilinen sınırlılık olarak kaldığı.

**Kabul:** Referans setinde CC'nin radon ile farkı yalnızca belgelenmiş tanım farklarından oluşur (sınıflandırılmamış fark 0); DCC elle sayımda yanlış pozitif/negatif oranı raporlanmış ve README "Limitations"a işlenmiş; şüpheli nokta testleri yeşil; fark tablosu commit'li.

---

## Blok 2 — Gerçek projede dayanıklılık ve hız

**Neden:** Fikstürler küçük; gerçek projelerde parse hataları, süre ve boş-katman senaryosu görülmedi.

**İş:**
1. Referans setinde `scan`, `arch`, `advise --dry-run` koşulur; çökmeler, `skipped_files` nedenleri (encoding, sözdizimi sürümü, ikili dosya) ve süreler kaydedilir (`experiments/hardening/robustness.md`).
2. **Performans:** parse ve import grafiği için dosya hash'i tabanlı önbellek (`.rlens-cache/scan/`), `concurrent.futures` ile paralel parse; hedef: en büyük referans projede `scan` < 30 sn (ölçülüp yazılır). Önbellek geçersizleme kuralı: dosya hash'i veya `rlens_version` değişince.
3. **Katmansız proje senaryosu:** beyan ve import-linter yokken `arch` çıktısı anlamlı mı — tüm modüller `unknown`, ihlal yok, ama döngüler ve Ca/Ce yine raporlanmalı; kullanıcıya "katman beyanı için `rlens.yaml`'a `arch.layers` ekleyin" yönlendirmesi.
4. Büyük sınıflarda `advise` prompt boyutu: kesme politikası var mı, yoksa tanımlanır (hedef kod tam, bağımlı imzalar en fazla N, kesildiyse prompt'ta ve raporda belirtilir).

**Kabul:** Referans setinin tamamı çökmeden taranır; `skipped_files` nedenleri sınıflandırılmış; süre tablosu var; önbellek hit testi yeşil; katmansız senaryo testi yeşil; prompt kesme politikası belgelenmiş ve test edilmiş.

---

## Blok 3 — Dogfooding: aracı kendi koduna uygula

**Neden:** Gerçek kullanıcı deneyimi ancak gerçek kullanımda görülür; README'nin en inandırıcı örneği kendi kodumuzdur; v3 `apply` için ilk gerçek deneme alanı.

**İş:**
1. Kök `rlens.yaml`: RefactorLens'in kendi katman beyanı (öneri: `cli` → presentation; `advise`, `verify` → application; `analysis` → domain; `llm`, `integrations`, `report` → infrastructure). Beyan tartışılabilir; tartışma `docs/self-architecture.md`'ye yazılır.
2. `rlens scan .`, `rlens arch .` çıktıları `experiments/hardening/self/` altına; kokular ve ihlaller listelenir.
3. En az **3 hedef** için tam döngü: `advise` → elle uygulama → `verify` (davranış kapısı = kendi 992 testi). Sonuçlar mini-FINDINGS olarak `docs/self-architecture.md`'ye.
4. Kullanım sırasında çıkan her pürüz (kafa karıştıran mesaj, eksik bilgi, yanlış varsayılan) `experiments/hardening/friction.md`'ye; her biri ya bu blokta düzeltilir ya FUTURE'a gider.

**Kabul:** Kendi ihlal/koku listesi var; 3 döngü tamamlanmış ve `verify` raporları commit'li; README'ye "RefactorLens on itself" bölümü; friction listesindeki her madde kararlı.

---

## Blok 4 — Test ve hijyen

**İş:**
1. Bilinenler: terminal genişliğine bağımlı CLI testi (`COLUMNS` sabitle veya satır sonu bağımsız assert); 4 fikstür dosyasında `ruff format`; ihlal tablosundaki başlıksız `tentative` sütunu; D3–D6'dan açık kalanlar.
2. **Property-based testler** (`hypothesis`, `tests/test_properties.py`): metot eklemek NOM'u düşürmez; metoda `self.x` erişimi eklemek LCOM4'ü artırmaz; parametre eklemek PARAMS'ı tam 1 artırır; boş sınıfın metrikleri tutarlı (`nom=0`, `lcom4=null`, `wmc=0`); iki modül arasına import eklemek Ce/Ca'yı tam 1 artırır; rapor `to_dict → from_dict` round-trip kayıpsız.
3. **Kendi testine mutation testing:** `mutmut run --paths-to-mutate src/rlens/analysis` ; hayatta kalan mutantlar incelenir, ya test eklenir ya "eşdeğer mutant" olarak belgelenir. Skor `experiments/hardening/mutation.md`'ye. (v3'te başkasının testlerini ölçecek aracın kendi test gücünü bilmesi tutarlılık gereğidir.)
4. CI: Python 3.11/3.12/3.13 matrisi; `ruff format --check` CI'da; Trusted Publishing için `pypi.yml` workflow'u (tag'de yayın).

**Kabul:** Test seti tüm matriste yeşil; property testleri var; analysis paketinde mutation skoru ölçülmüş (hedef ≥ %80, altındaysa neden yazılı); flaky test yok; Trusted Publishing çalışır (TestPyPI'da denenmiş).

---

## Blok 5 — Rapor, kullanım ve dokümantasyon

**İş:**
1. **Hedef adlandırma tek kural:** rapor, terminal, `advise --target`, `verify --applied` hepsi aynı biçimi kullanır (öneri: kök-göreli tam ad `services.order_service:OrderService`; `src/` layout tespit edilirse önek otomatik kırpılır ve raporda `root_package` alanı yazılır). Test: üç komut aynı adı kabul eder.
2. Config hata mesajları: hangi anahtar, hangi bölümde, neden geçersiz, geçerli seçenekler neler. Test: 5 tipik hatalı config için mesaj snapshot'ı.
3. `rlens` çıktısı `--format json|markdown|table` (mevcut dosya raporlarını stdout'a da verebilme; yeni hesaplama yok).
4. **README v2'ye göre yeniden yazılır:** `arch`, kokular, katman eşikleri, mimari bağlam, `confidence`/kalibrasyon, `suspicious` ve `moved` ayrımı, ihlal alias tablosu ve Arcan ilişkisi, `--no-arch`'ın gerçekte ne kapattığı (D4), "Limitations" Blok 1 tablosundan beslenir, "RefactorLens on itself", `<user>` → `okngms`, göreli linkler → mutlak. Roadmap: v2.1 çıkarım, v3, v4 tek satır.
5. `AGENTS.md`/`STRUCTURE.md`/`docs/04` güncellenir (önbellek dizini, yeni testler, `root_package`).

**Kabul:** README bir yabancı tarafından Quickstart'tan `verify`'a kadar takip edilebilir; adlandırma testi yeşil; config hata snapshot'ları yeşil; `docs/04` ve STRUCTURE güncel.

---

## Sıralama, süre, çıkış

```
Blok 1 (2-3 oturum) → Blok 3 (1-2) → Blok 2 (1-2) → Blok 4 (1-2) → Blok 5 (1)
→ v2.0.0 yayını → docs/02 (v3) FINDINGS-2 bulgularına göre revize → v3 başlar
```
- Blok 3, Blok 2/4/5'in pürüzlerini doğal yoldan çıkardığı için 1'den hemen sonra gelir.
- Toplam 6-10 yan zamanlı oturum.
- **Çıkış kriteri:** beş bloğun kabul kriterleri sağlandı, `docs/STATUS.md` "v2.0.0 yayınlandı" diyor, FINDINGS-1/2'nin Limitations bölümleri Blok 1 tablosuna atıf veriyor.


