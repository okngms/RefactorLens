# messy_project — kasıtlı koku envanteri

Bu dosya fikstürün **sözleşmesidir**. Faz 1'de her metrik için altın değer
elle hesaplanırken buradaki beklentiler doğrulanır; tutmuyorsa ya fikstür ya da
metrik hatalıdır. Kesin sayılar Faz 1'de bu tabloya işlenir.

## Sınıf düzeyi

| Sınıf | Dosya | Beklenen davranış | Neden burada |
|---|---|---|---|
| `OrderManager` | `god.py` | LCOM4 = 4, DCC = 8, NOM = 25, CAM = `null` | Ana denek. Dört ayrık sorumluluk, sekiz sınıfa bağımlılık, sıfır annotation. |
| `ReportBuilder` | `reporting.py` | LCOM4 = 2, CAM = `null` (kapsam ≈ 0.33 < 0.7) | Gri bölge: kısmi annotation. CAM eşiğinin gerçekten çalıştığını kanıtlar. |
| `Customer` | `models.py` | LCOM4 = 1, CAM hesaplanır | Temiz referans. Araç iyi kodu "sorunlu" işaretlememeli. |
| `Product` | `models.py` | LCOM4 = 1, CAM hesaplanır | Temiz referans. |
| `OrderLine` | `models.py` | LCOM4 = 1, DCC = 1 | Düşük coupling referansı. |
| `Order`, `Invoice`, `AuditEntry`, `EmailNotifier`, `ShippingCalculator` | `services.py` | Hepsi küçük ve kohezyonlu | Tek başlarına temiz; `OrderManager`'ın DCC'sini yükseltmek için varlar. |

### `OrderManager`'ın LCOM4 bileşenleri
Dört bileşen birbirini **hiç çağırmaz** — bu bilinçlidir, yoksa bileşenler
birleşir ve fikstür amacını kaybeder:

1. `_orders`, `_next_id` → `place_order`, `get_order`, `cancel_order`, `order_count`, `orders_for`, `line_count`, `mark_paid`, `unpaid_orders`
2. `_tax_rate`, `_discount_rules` → `set_discount`, `discount_for`, `bulk_discount`, `set_tax_rate`, `apply_tax`, `total_with_tax`, `shipping_for`
3. `_log` → `log_event`, `history`, `last_event`, `log_size`, `clear_log`
4. `_smtp_host`, `_sent` → `configure_smtp`, `notify`, `sent_count`, `outbox`, `reset_outbox`

> **Dikkat:** Fikstüre yeni bir metot eklerken iki bileşenin attribute'una
> birden dokunmayın; LCOM4 sessizce 4'ten 3'e düşer ve altın değer testleri
> nedeni anlaşılmadan kırılır.

## Fonksiyon düzeyi (`utils.py`)

| Fonksiyon | Koku | Eşik |
|---|---|---|
| `deep_transform` | 5 seviye iç içelik | `max_nesting.warn = 4` |
| `build_shipping_label` | 7 parametre | `max_params.warn = 5` |
| `classify_order` | yüksek cyclomatic complexity | `cyclomatic_complexity.warn = 10` |

## CAM kapsama vakaları
Fikstür, CAM'in **her iki yolunu** da kapsar:
- **Hesaplanır:** `models.py` (annotation kapsamı %100)
- **`null` döner:** `god.py` (kapsam %0) ve `reporting.py` (kapsam ≈ %33)

## Değiştirme kuralı
Bu dosyadaki bir beklentiyi değiştiren her fikstür düzenlemesi, aynı commit'te
Faz 1 altın değer testlerini de günceller. Fikstür sessizce kaymamalıdır.
