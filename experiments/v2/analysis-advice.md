# Advice analysis (phase 5a)

- **Runs:** 36
- **Models:** openai/gpt-oss-120b
- **Targets:** src.api.report_view:ReportView, src.domain.entities:Customer, src.services.order_service:OrderService
- **Conditions:** neither, arch-context, metric-rules, both

> This part measures **suggestion quality**, read from the text of the advice. Whether the predictions were correct requires applying them, which is part B.

## Constraint compliance

`rejected` counts suggestions that break the layer rules. `disagreements` counts suggestions claiming to respect them while the tool finds otherwise — the model's own claim is an output too.

| Condition | Runs | Suggestions | Per run | Rejected | Rate | Claims | Disagreements | Rate |
|---|---|---|---|---|---|---|---|---|
| neither | 9 | 11 | 1.222 | 0 | 0.0 | 0 | 0 | None |
| arch-context | 9 | 9 | 1.0 | 0 | 0.0 | 9 | 0 | 0.0 |
| metric-rules | 9 | 12 | 1.333 | 0 | 0.0 | 0 | 0 | None |
| both | 9 | 14 | 1.556 | 0 | 0.0 | 14 | 0 | 0.0 |

## Contract compliance

| Condition | Unlinked | Rate | Repaired | Unparseable | Predictions | With confidence | Rate |
|---|---|---|---|---|---|---|---|
| neither | 0 | 0.0 | 0 | 0 | 35 | 35 | 1.0 |
| arch-context | 0 | 0.0 | 0 | 0 | 25 | 25 | 1.0 |
| metric-rules | 0 | 0.0 | 0 | 0 | 40 | 40 | 1.0 |
| both | 0 | 0.0 | 0 | 0 | 37 | 37 | 1.0 |

## Architectural fields

Only the conditions with architectural context can produce these.

| Condition | Named a destination layer | Named smells |
|---|---|---|
| neither | 0 | 0 |
| arch-context | 9 | 9 |
| metric-rules | 0 | 0 |
| both | 14 | 14 |

### Are the named smells real?

| Condition | Claims | Wrong | Rate |
|---|---|---|---|
| arch-context | 14 | 4 | 0.286 |
| both | 18 | 2 | 0.111 |

## Per target

Aggregating across targets hides the contrast the fixture was built for. `Customer` is a sound domain entity whose LCOM4 of 4 reproduces the false positive from FINDINGS-1; `OrderService` is a genuine god class. Whether the `data_class` label changes the advice is only visible here.

| Target | Condition | Suggestions | Per run | Claimed a smell | Addressed its own | Mean confidence |
|---|---|---|---|---|---|---|
| `ReportView` | arch-context | 3 | 1.0 | 3 | 2 | 0.758 |
| `ReportView` | both | 6 | 2.0 | 6 | 6 | 0.791 |
| `ReportView` | neither | 3 | 1.0 | 0 | 0 | 0.775 |
| `ReportView` | metric-rules | 3 | 1.0 | 0 | 0 | 0.743 |
| `Customer` | arch-context | 3 | 1.0 | 3 | 3 | 0.771 |
| `Customer` | both | 3 | 1.0 | 3 | 3 | 0.8 |
| `Customer` | neither | 3 | 1.0 | 0 | 0 | 0.859 |
| `Customer` | metric-rules | 3 | 1.0 | 0 | 0 | 0.854 |
| `OrderService` | arch-context | 3 | 1.0 | 3 | 3 | 0.796 |
| `OrderService` | both | 5 | 1.667 | 5 | 5 | 0.778 |
| `OrderService` | neither | 5 | 1.667 | 0 | 0 | 0.758 |
| `OrderService` | metric-rules | 6 | 2.0 | 0 | 0 | 0.781 |

### What was actually suggested

The predicted effects sit beside the titles because the interesting question is not only what the model proposes but what it admits the proposal will cost. A suggestion to expose private fields that does not predict `DAM down` has not noticed the trade-off it is making.

**`ReportView` — arch-context**

- Extract infrastructure interactions into an application service
- Extract infrastructure interactions to an application‑layer service
- Extract a ReportService to the application layer

  predicted: LCOM4 down ×3, DCC down ×2, DCC up ×1

**`ReportView` — both**

- Extract a ReportService to the application layer
- Separate customer formatting into its own view class
- Introduce ReportService to encapsulate repository and mailer
- Extract customer description to a formatter class
- Move infrastructure collaborators to an application service
- Extract Customer formatting to a domain helper

  predicted: LCOM4 down ×6, DCC down ×3, WMC down ×1, DCC same ×1

**`ReportView` — neither**

- Extract infrastructure coordination into a dedicated service
- Extract customer description to a dedicated presenter class
- Extract mail_summary to a dedicated EmailReport helper

  predicted: LCOM4 down ×3, DCC down ×3

**`ReportView` — metric-rules**

- Extract customer formatting into its own presenter
- Extract email‑sending responsibility to a dedicated Mailer helper
- Extract business logic to a ReportService and keep ReportView as pure presenter

  predicted: LCOM4 down ×3, DCC down ×2, DCC same ×1, WMC down ×1

**`Customer` — arch-context**

- Add domain behavior to increase cohesion
- Replace explicit getters with a frozen dataclass and keep only behavior
- Extract tier‑related behavior to a dedicated domain value object

  predicted: LCOM4 down ×3, DCC up ×2, NOM down ×1, WMC down ×1

**`Customer` — both**

- Replace explicit getters with read‑only properties
- Introduce domain behavior to improve cohesion
- Replace manual boilerplate with a @dataclass

  predicted: LCOM4 down ×2, NOM down ×2, WMC down ×2, DCC up ×1, LCOM4 same ×1

**`Customer` — neither**

- Replace trivial getters with public dataclass fields
- Replace explicit getters with dataclass fields or @property accessors
- Replace getters with public fields via a dataclass

  predicted: LCOM4 down ×3, DAM down ×3, NOM down ×3, WMC down ×2

**`Customer` — metric-rules**

- Replace getters with public fields via a dataclass
- Replace explicit getters with a dataclass and keep only behavior
- Replace trivial getters with a data class and public fields

  predicted: LCOM4 down ×3, DAM down ×3, NOM down ×3, WMC down ×3

**`OrderService` — arch-context**

- Extract four focused service classes
- Extract pricing responsibilities to a dedicated PricingService in the domain layer
- Extract responsibility‑specific services

  predicted: LCOM4 down ×3, NOM down ×3, WMC down ×3, DCC up ×3

**`OrderService` — both**

- Extract Notification responsibilities to a dedicated NotificationService
- Extract Pricing logic into a PricingService
- Extract responsibility‑specific services
- Move pricing logic to a domain PricingPolicy
- Extract focused service classes from OrderService

  predicted: LCOM4 down ×5, NOM down ×4, WMC down ×4, DCC up ×4, DCC down ×1

**`OrderService` — neither**

- Split OrderService into four focused services
- Introduce an AuditLog value object to encapsulate audit state
- Extract each component into its own service class
- Extract pricing responsibilities into a dedicated PricingService
- Extract audit functionality into an AuditLog component

  predicted: LCOM4 down ×5, NOM down ×4, WMC down ×4, DCC up ×4, DCC same ×1

**`OrderService` — metric-rules**

- Extract pricing responsibilities into a dedicated PricingService
- Separate audit logic into an AuditLog component
- Move notification handling to a NotificationFacade
- Extract component services for lifecycle, pricing, audit, and notification
- Extract component services
- Extract validation helpers from place()

  predicted: WMC down ×6, LCOM4 down ×5, NOM down ×5, DCC up ×3, DCC same ×1, CC down ×1


## Consistency across repetitions

Mean Jaccard similarity between the repetitions of the same (condition, model, target). A model whose own runs disagree cannot be compared with another until that variance is accounted for.

| Condition | Model | Target | n | Evidence | Prediction |
|---|---|---|---|---|---|
| arch-context | `openai/gpt-oss-120b` | `src.api.report_view:ReportView` | 3 | 1.0 | 0.556 |
| arch-context | `openai/gpt-oss-120b` | `src.domain.entities:Customer` | 3 | 0.5 | 0.5 |
| arch-context | `openai/gpt-oss-120b` | `src.services.order_service:OrderService` | 3 | 1.0 | 1.0 |
| both | `openai/gpt-oss-120b` | `src.api.report_view:ReportView` | 3 | 1.0 | 0.667 |
| both | `openai/gpt-oss-120b` | `src.domain.entities:Customer` | 3 | 0.5 | 0.25 |
| both | `openai/gpt-oss-120b` | `src.services.order_service:OrderService` | 3 | 1.0 | 0.867 |
| neither | `openai/gpt-oss-120b` | `src.api.report_view:ReportView` | 3 | 1.0 | 1.0 |
| neither | `openai/gpt-oss-120b` | `src.domain.entities:Customer` | 3 | 0.833 | 0.833 |
| neither | `openai/gpt-oss-120b` | `src.services.order_service:OrderService` | 3 | 1.0 | 0.867 |
| metric-rules | `openai/gpt-oss-120b` | `src.api.report_view:ReportView` | 3 | 1.0 | 0.417 |
| metric-rules | `openai/gpt-oss-120b` | `src.domain.entities:Customer` | 3 | 1.0 | 1.0 |
| metric-rules | `openai/gpt-oss-120b` | `src.services.order_service:OrderService` | 3 | 0.867 | 0.756 |
