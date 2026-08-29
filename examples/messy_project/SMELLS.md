# messy_project — kasıtlı koku envanteri

Bu dosya fikstürün **sözleşmesidir**. Buradaki her sayı `tests/test_class_metrics.py`
ve `tests/test_func_metrics.py` içinde altın değer olarak sabitlenmiştir; fikstür
değişirse testler kırılır.

## Sınıf düzeyi — ölçülen değerler

| Sınıf | Dosya | NOM | WMC | LCOM4 | DCC | DAM | CAM |
|---|---|---|---|---|---|---|---|
| `OrderManager` | `god.py` | 25 | 49 | **4** | **8** | 1.0 | `null` |
| `ReportBuilder` | `reporting.py` | 6 | 7 | 2 | 0 | 1.0 | `null` |
| `Customer` | `models.py` | 6 | 6 | 3 | 0 | 0.2 | 1.0 |
| `Product` | `models.py` | 4 | 5 | 2 | 0 | 0.0 | 1.0 |
| `OrderLine` | `models.py` | 3 | 3 | 1 | 1 | 0.0 | 1.0 |
| `Order` | `services.py` | 4 | 6 | 2 | 2 | 0.0 | `null` |
| `Invoice` | `services.py` | 1 | 1 | 1 | 0 | 0.0 | `null` |
| `AuditEntry` | `services.py` | 1 | 1 | 1 | 0 | 0.0 | `null` |
| `EmailNotifier` | `services.py` | 1 | 1 | 1 | 0 | 0.0 | 1.0 |
| `ShippingCalculator` | `services.py` | 1 | 2 | 1 | 0 | 0.0 | 1.0 |

### `OrderManager` — ana denek
Dört ayrık sorumluluk tek sınıfta. Bileşenler birbirini **hiç çağırmaz**; bu
bilinçlidir, yoksa bileşenler birleşir ve fikstür amacını kaybeder:

1. `_orders`, `_next_id` → `place_order`, `get_order`, `cancel_order`, `order_count`, `orders_for`, `line_count`, `mark_paid`, `unpaid_orders`
2. `_tax_rate`, `_discount_rules` → `set_discount`, `discount_for`, `bulk_discount`, `set_tax_rate`, `apply_tax`, `total_with_tax`, `shipping_for`
3. `_log` → `log_event`, `history`, `last_event`, `log_size`, `clear_log`
4. `_smtp_host`, `_sent` → `configure_smtp`, `notify`, `sent_count`, `outbox`, `reset_outbox`

DCC = 8: `Customer`, `Product`, `OrderLine`, `Order`, `Invoice`, `AuditEntry`,
`EmailNotifier`, `ShippingCalculator`.

> **Dikkat:** Fikstüre yeni metot eklerken iki bileşenin attribute'una birden
> dokunmayın; LCOM4 sessizce 4'ten 3'e düşer ve altın değer testleri nedeni
> anlaşılmadan kırılır.

### LCOM4 hakkında dürüst bir not
`models.py` bilerek **temiz** yazılmıştır, ancak LCOM4 değerleri 1 değildir.
`Customer`'ın her alanı için ayrı erişimcisi vardır (`rename` → `name`,
`promote` → `tier`, `add_note` → `_notes`) ve bu metotlar birbirine dokunmaz;
LCOM4 bunu üç ayrı sorumluluk sayar.

Bu, LCOM4'ün literatürde bilinen zayıflığıdır: **veri taşıyıcı sınıfları
kohezyonsuz gösterir.** Sınıf kötü tasarlanmış değildir.

Fikstürü metriği memnun edecek şekilde değiştirmiyoruz — bu tam olarak aracın
uyardığı Goodhart tuzağı olurdu. Sınırlılık README'nin "Metric Definitions &
Adaptations" bölümünde belgelenecektir.

Temiz ile kirli arasındaki asıl ayrım LCOM4'te değil **WMC ve DCC'de** görünür:
`Customer` 6 / 0, `OrderManager` 49 / 8.

## Fonksiyon düzeyi — ölçülen değerler (`utils.py`)

| Fonksiyon | CC | Parametre | İç içelik | Aşan eşik |
|---|---|---|---|---|
| `classify_order` | **15** | **7** | 1 | CC > 10, params > 5 |
| `deep_transform` | 8 | 1 | **7** | nesting > 4 |
| `build_shipping_label` | 2 | **7** | 0 | params > 5 |

`classify_order` yüksek karmaşıklığa rağmen **düz**dür (iç içelik 1); ardışık
`if` zinciri derinlik üretmez. İki metriğin farklı şeyler ölçtüğünün kanıtı.

## CAM kapsama vakaları
Fikstür CAM'in **her iki yolunu** da kapsar:
- **Hesaplanır:** `models.py` (annotation kapsamı %100)
- **`null` döner:** `god.py` (kapsam %0 → `no_annotated_parameters`) ve
  `reporting.py` (kapsam %33 → `insufficient_annotations`)

## Değiştirme kuralı
Bu tablodaki bir sayıyı değiştiren her fikstür düzenlemesi, aynı commit'te altın
değer testlerini de günceller. Fikstür sessizce kaymamalıdır.
