# FINDINGS-3 — literatür bağı (taslak)

`docs/02` Aşama 6'nın "Bitti" koşulu: literatür bağı (SWE-Refactor,
EMSE 2026, SpecBench). Bu belge sonuçlardan **önce** ve sonuçlardan
bağımsız yazıldı (2026-10-18); FINDINGS-3'ün "İlgili çalışmalar" bölümüne
taşınır. Hiçbir LensBench sonucuna dayanmaz.

**Kaynak kuralı.** Her kaynak birincil sayfasından okundu (arXiv özet
sayfası ya da DOI meta verisi). Okunan düzey özettir; tam metin
okunmadı. Aşağıdaki her iddia o düzeyle sınırlıdır; tam metin gerektiren
bir karşılaştırma yapılmadı. "Hiçbiri" diye başlayan cümleler yalnızca bu
listedeki kaynaklar için geçerlidir; literatürün tamamı taranmadı.

## Kaynaklar

| # | Kaynak | Dil | Ne ölçüyor (özetten) |
|---|---|---|---|
| L1 | Xu, Yang, Chen. *SWE-Refactor: A Repository-Level Benchmark for Real-World LLM-Based Code Refactoring.* arXiv:2602.03712, 2026-02-03. | Java | 18 projeden 1 099 geliştirici refactoring'i; her örnek derleme, test ve otomatik refactoring tespitiyle doğrulanmış; 9 LLM; başarı oranı (bileşik örneklerde en iyi ajan %39.4). |
| L2 | Chen Kuang Piao, Paul, Da Silva, Moradi Dakhel, Hamdaqa, Khomh. *Refactoring with LLMs: Bridging Human Expertise and Machine Understanding.* Empirical Software Engineering 32(1), 2026, doi:10.1007/s10664-026-10925-0. Ön baskı arXiv:2510.03914. | özette belirtilmiyor | Fowler'ın 61 refactoring türü için talimat tasarımları (betimleyici / kural tabanlı / hedef odaklı); GPT-mini ve DeepSeek-V3; anlamın korunması; özette sayısal sonuç yok. |
| L3 | Hamblin ve diğ. *SpecBench: Evaluating Specification-Level Reasoning for Software Engineering LLM Agents.* arXiv:2605.30314, 2026-05-28. | — (kod yazılmaz) | Tasarım önerisindeki eksik, belirsiz, tutarsız ya da yanlış varsayımları bulma; tahminler bakımcıların geçmiş RFC eleştirileriyle puanlanır; beş depo; en iyi ajan %44.4. |
| L4 | Liu, Jiang, Zhang, Niu, Li, Liu. *An Empirical Study on the Potential of LLMs in Automated Software Refactoring.* Automated Software Engineering 32(1), 2025; arXiv:2411.04444. | Java | 20 projeden 180 refactoring; fırsat bulma (ChatGPT 28/180, Gemini 7/180; yönlendirmeyle %15.6 → %86.7); çözümlerin %63.6'sı uzmanınkiyle denk ya da iyi; güvensiz öneriler (ChatGPT 13, Gemini 9). |
| L5 | Midolo, Tramontana, Di Penta. *From Human to Machine Refactoring: Assessing GPT-4's Impact on Python Class Quality and Readability.* arXiv:2601.13139, 2026-01-19. | Python | ClassEval'den 100 sınıf, GPT-4o; davranış (birim testleri), kalite (Pylint, Flake8, SonarCloud), okunabilirlik; davranış genelde korunur, kokular azalır, okunabilirlik düşer. |

L2 notu: dergi sürümünün özetine erişilemedi (Springer oturum istiyor,
OpenAlex'te özet yok). Satırdaki içerik aynı başlık ve yazarlarla
yayımlanmış arXiv ön baskısının özetinden; iki sürümün aynı olduğu
varsayımdır.

## RefactorLens'in yeri

Ortak eksen, bir refactoring önerisinin **sonradan** değerlendirilmesidir:
L1 başarıyı (derleniyor mu, testler geçiyor mu, beklenen refactoring
yapılmış mı), L4 fırsat bulmayı ve çözüm kalitesini, L5 değişiklik sonrası
kalite ve okunabilirlik araçlarının çıktısını ölçer. L2 talimat tasarımının
etkisini inceler. Bu kaynakların hiçbiri modelden, öneriyi uygulamadan
**önce**, önerinin yapısal metrikleri hangi yöne oynatacağına dair
makineyle denetlenebilir bir tahmin istemiyor ve o tahmini ölçümle
karşılaştırmıyor. RefactorLens'in sorusu budur: `expected_effect`
(`{metric, direction}`) önceden verilir, `verify`/`loop` ölçülen deltayla
karşılaştırır; davranış kapısı geçmeyen delta sayılmaz.

L3 başka bir eksende ama yöntem olarak yakın: modelin çıktısı kod değil
bir yargıdır ve bağımsız bir referansla (bakımcı eleştirileri) puanlanır.
LensBench'te referans insan yargısı değil, aynı aracın ölçümüdür; bu
yüzden "metrik iyileşmesi tasarım iyileşmesi değildir" sınırlılığı
FINDINGS-3'te de geçerlidir (ön kayıt §7).

Dil farkı: L1 ve L4 Java, L5 Python. RefactorLens yalnızca Python'dur
(kilitli karar); LensBench hedefleri üç küçük fikstürdür, L1'in depo
düzeyi örnekleriyle ölçek olarak karşılaştırılamaz.

## FINDINGS-3'e taşınırken

- Sayılar yukarıdaki özetlerden; FINDINGS-3'e girmeden önce tam metinden
  doğrulanmalı ya da "özete göre" diye işaretlenmeli.
- L1'in bileşik refactoring bulgusu (başarısızlıkların çoğu karmaşık ve
  bileşik örneklerde) H4 (tür bazında doğruluk) ve H5 (kalıntı) ile
  yalnızca **ilişkilendirilebilir**; farklı ölçü (başarı vs tahmin
  isabeti), farklı dil.
</content>
</invoke>
<invoke name="Bash">
<parameter name="command">cd /c/myProjects/RefactorLens && .venv/Scripts/python.exe - <<'EOF'
from pathlib import Path
p = Path("docs/STATUS.md")
t = p.read_text(encoding="utf-8")
t = t.replace("# STATUS — 2026-10-17", "# STATUS — 2026-10-18", 1)
b = "## Bitenler\n"
t = t.replace(b, b + """- **FINDINGS-3 literatür bağı taslağı (2026-10-18).** `docs/findings-3-literatur.md`:
  SWE-Refactor (arXiv:2602.03712), EMSE 2026 (doi:10.1007/s10664-026-10925-0;
  özet ön baskıdan, arXiv:2510.03914), SpecBench (arXiv:2605.30314), ayrıca
  Liu ve diğ. (ASE 2025) ve Midolo ve diğ. (Python, arXiv:2601.13139). Her
  kaynak birincil sayfasından, özet düzeyinde okundu; tam metin okunmadı.
  Sonuçlardan bağımsız; FINDINGS-3'ün ilgili çalışmalar bölümüne taşınacak.
  LensBench koşusu sürüyor (2026-10-18 00:06: 120b 38, 20b 45, Gemini 6).
""", 1)
p.write_text(t, encoding="utf-8")
EOF
grep -n "lensbench-v1-onkayit.md" STRUCTURE.md | head -3