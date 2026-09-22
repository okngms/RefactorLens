<!-- Üretildi: experiments/hardening/pysmell_labels.py. Elle düzenlemeyin. -->

PySmell `233afeb`, `manual inspection/`. Hata sınırı: max(1, ⌈0.02·N⌉).

| Koku | N | pozitif | metrikler | en iyi tek eşik (hata) | en iyi iki eşik (hata) | sınır | okuma |
|---|---:|---:|---|---|---|---:|---|
| ComplexContainerComprehension | 300 | 22 | NOC, NOFF, NOO | `NOO >= 22` (19) | `NOC >= 86 and NOO >= 22` (10) | 6 | bağımsız yargı |
| LargeClass | 300 | 11 | CLOC | `CLOC >= 37` (1) | - | 6 | tek eşiği kodluyor |
| LongBaseClassList | 300 | 0 | NBC | `NBC >= 2` (300) | - | 6 | yetersiz pozitif |
| LongLambdaFunction | 200 | 16 | NOC, PAR, NOO | `NOO >= 17` (11) | `NOC >= 72 and NOO >= 15` (4) | 4 | kuralı kodluyor |
| LongMessageChain | 300 | 36 | LMC | `LMC >= 4` (7) | - | 6 | bağımsız yargı |
| LongMethod | 300 | 2 | MLOC | `MLOC >= 53` (0) | - | 6 | yetersiz pozitif |
| LongParameterList | 300 | 31 | PAR | `PAR >= 5` (13) | - | 6 | bağımsız yargı |
| LongScopeChaining | 69 | 6 | DOC | `DOC >= 3` (63) | - | 2 | yetersiz pozitif |
| LongTernaryConditionalExpression | 201 | 11 | NOC, NOL | `NOL >= 3` (7) | `NOC >= 98 or NOL >= 3` (5) | 5 | kuralı kodluyor |
| MultiplyNestedContainer | 300 | 15 | LEC, DNC, NCT | `DNC >= 3` (2) | `DNC >= 3 and NCT >= 2` (2) | 6 | tek eşiği kodluyor |

## Sonradan eklenen analiz — PySmell'in kendi dedektör kuralları

Ön kayıtta yok. `detector.py`'deki genel eşikler satırlara uygulandı. Sütun ≠ kural: CSV'deki dedektör sütununun kuraldan ayrıldığı satır. Kural ≠ elle: kuralın elle verilen etiketten ayrıldığı satır.

| Koku | experience: sütun ≠ kural | experience: kural ≠ elle | statistics: sütun ≠ kural | statistics: kural ≠ elle |
|---|---:|---:|---:|---:|
| ComplexContainerComprehension | 32 | 219 | 12 | 25 |
| LargeClass | 16 | 14 | 0 | 6 |
| LongBaseClassList | 0 | 0 | 0 | 300 |
| LongLambdaFunction | 5 | 83 | 0 | 4 |
| LongMessageChain | 0 | 36 | 0 | 7 |
| LongMethod | 35 | 17 | 0 | 34 |
| LongParameterList | 0 | 13 | 0 | 68 |
| LongScopeChaining | 0 | 63 | 0 | 6 |
| LongTernaryConditionalExpression | 49 | 172 | 0 | 5 |
| MultiplyNestedContainer | 0 | 15 | 0 | 8 |
