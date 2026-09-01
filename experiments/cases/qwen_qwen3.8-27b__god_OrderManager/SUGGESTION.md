# Case: god:OrderManager

- **Model:** `qwen/qwen3.8-27b`
- **Repetition:** 1

> Apply **one** suggestion, under the narrowest possible interpretation.
> Improve nothing the text does not explicitly ask for.

## Diagnosis

The class exhibits a classic God Object pattern, evidenced by a high LCOM4 (4) indicating four distinct clusters of methods that operate on disjoint sets of attributes. The high NOM (25) and WMC (49) reflect a broad scope of responsibility, while the DCC (8) shows tight coupling to numerous external classes. The code structure explicitly groups methods into four logical components: order management, pricing, audit logging, and notification, which are currently forced into a single class.

## 1. Extract Pricing and Tax Logic

- **Evidence:** LCOM4, NOM, WMC
- **Predicted effect:** LCOM4 down, NOM down, WMC down, DCC up

Create a new class `PricingEngine` that encapsulates `_tax_rate`, `_discount_rules`, and the methods `set_discount`, `discount_for`, `bulk_discount`, `set_tax_rate`, `apply_tax`, `total_with_tax`, and `shipping_for`. `OrderManager` should hold an instance of `PricingEngine` and delegate pricing calculations to it. This removes the pricing cluster from `OrderManager`, reducing its method count and complexity while increasing the number of distinct classes referenced (DCC) due to the new dependency.

## 2. Extract Audit Logging

- **Evidence:** LCOM4, NOM, WMC
- **Predicted effect:** LCOM4 down, NOM down, WMC down, DCC up

Create a new class `AuditLogger` that encapsulates `_log` and the methods `log_event`, `history`, `last_event`, `log_size`, and `clear_log`. `OrderManager` should hold an instance of `AuditLogger` and delegate logging calls to it. This isolates the audit trail from the core order management logic, further reducing the cohesion issues in `OrderManager`.

## 3. Extract Notification Service

- **Evidence:** LCOM4, NOM, WMC
- **Predicted effect:** LCOM4 down, NOM down, WMC down, DCC up

Create a new class `NotificationService` that encapsulates `_smtp_host`, `_sent`, and the methods `configure_smtp`, `notify`, `sent_count`, `outbox`, and `reset_outbox`. `OrderManager` should hold an instance of `NotificationService` and delegate email sending to it. This removes the notification cluster, leaving `OrderManager` focused solely on order lifecycle management.

## Risks

Refactoring will increase the number of classes in the system and may introduce new dependencies (DCC up). Callers of `OrderManager` methods that are moved to new classes will need to be updated to access the new components, either through delegation in `OrderManager` or by directly instantiating the new classes. This requires careful coordination to maintain backward compatibility or to update all usage sites.
