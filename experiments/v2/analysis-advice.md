# Advice analysis (phase 5a)

- **Runs:** 99
- **Models:** openai/gpt-oss-120b, openai/gpt-oss-20b, qwen/qwen3.8-27b
- **Targets:** src.api.report_view:ReportView, src.domain.entities:Customer, src.services.order_service:OrderService
- **Conditions:** neither, arch-context, metric-rules, both

> This part measures **suggestion quality**, read from the text of the advice. Whether the predictions were correct requires applying them, which is part B.

## Constraint compliance

`rejected` counts suggestions that break the layer rules. `disagreements` counts suggestions claiming to respect them while the tool finds otherwise — the model's own claim is an output too.

| Condition | Runs | Suggestions | Per run | Rejected | Rate | Claims | Disagreements | Rate |
|---|---|---|---|---|---|---|---|---|
| neither | 23 | 34 | 1.478 | 0 | 0.0 | 0 | 0 | None |
| arch-context | 26 | 30 | 1.154 | 2 | 0.067 | 30 | 2 | 0.067 |
| metric-rules | 27 | 40 | 1.481 | 0 | 0.0 | 0 | 0 | None |
| both | 23 | 30 | 1.304 | 0 | 0.0 | 30 | 0 | 0.0 |

## Contract compliance

| Condition | Unlinked | Rate | Repaired | Unparseable | Predictions | With confidence | Rate |
|---|---|---|---|---|---|---|---|
| neither | 0 | 0.0 | 0 | 0 | 102 | 102 | 1.0 |
| arch-context | 0 | 0.0 | 1 | 0 | 80 | 80 | 1.0 |
| metric-rules | 0 | 0.0 | 1 | 1 | 118 | 118 | 1.0 |
| both | 0 | 0.0 | 1 | 1 | 85 | 85 | 1.0 |

## Architectural fields

Only the conditions with architectural context can produce these.

| Condition | Named a destination layer | Named smells |
|---|---|---|
| neither | 0 | 0 |
| arch-context | 30 | 30 |
| metric-rules | 0 | 0 |
| both | 30 | 30 |

### Are the named smells real?

| Condition | Claims | Wrong | Rate |
|---|---|---|---|
| arch-context | 39 | 11 | 0.282 |
| both | 36 | 5 | 0.139 |

## Per target

Aggregating across targets hides the contrast the fixture was built for. `Customer` is a sound domain entity whose LCOM4 of 4 reproduces the false positive from FINDINGS-1; `OrderService` is a genuine god class. Whether the `data_class` label changes the advice is only visible here.

| Target | Condition | Suggestions | Per run | Claimed a smell | Addressed its own | Mean confidence |
|---|---|---|---|---|---|---|
| `ReportView` | arch-context | 13 | 1.444 | 13 | 8 | 0.787 |
| `ReportView` | both | 12 | 1.5 | 12 | 11 | 0.783 |
| `ReportView` | neither | 12 | 1.333 | 0 | 0 | 0.766 |
| `ReportView` | metric-rules | 12 | 1.333 | 0 | 0 | 0.773 |
| `Customer` | arch-context | 6 | 0.667 | 6 | 6 | 0.821 |
| `Customer` | both | 6 | 0.75 | 6 | 6 | 0.825 |
| `Customer` | neither | 6 | 1.0 | 0 | 0 | 0.845 |
| `Customer` | metric-rules | 9 | 1.0 | 0 | 0 | 0.883 |
| `OrderService` | arch-context | 11 | 1.375 | 11 | 11 | 0.799 |
| `OrderService` | both | 12 | 1.714 | 12 | 12 | 0.804 |
| `OrderService` | neither | 16 | 2.0 | 0 | 0 | 0.743 |
| `OrderService` | metric-rules | 19 | 2.111 | 0 | 0 | 0.802 |

### What was actually suggested

The predicted effects sit beside the titles because the interesting question is not only what the model proposes but what it admits the proposal will cost. A suggestion to expose private fields that does not predict `DAM down` has not noticed the trade-off it is making.

**`ReportView` — arch-context**

- Extract infrastructure interactions into an application service
- Extract infrastructure interactions to an application‑layer service
- Extract a ReportService to the application layer
- Move data access and mail logic to a dedicated service
- Extract customer formatting into a separate formatter
- Introduce an OrderReportService in the application layer
- Extract mail delivery into a dedicated service
- Extract formatting logic into a dedicated Formatter class
- Introduce Application Service to mediate Infrastructure access
- Extract customer formatting to a domain or application service
- Delegate report orchestration to an application service
- Extract formatting logic into a dedicated Presentation Formatter
- Introduce Application Service to mediate Infrastructure access

  predicted: LCOM4 down ×13, DCC down ×12, DCC up ×1, NOM down ×1

**`ReportView` — both**

- Extract a ReportService to the application layer
- Separate customer formatting into its own view class
- Introduce ReportService to encapsulate repository and mailer
- Extract customer description to a formatter class
- Move infrastructure collaborators to an application service
- Extract Customer formatting to a domain helper
- Split responsibilities: separate formatting from data access
- Extract CustomerReportView and MailSummaryService
- Introduce application layer services to decouple from infrastructure
- Extract customer formatting logic to a domain or application service
- Introduce Application Service for Report Logic
- Delegate Customer Description to Domain

  predicted: LCOM4 down ×12, DCC down ×7, WMC down ×3, DCC same ×2

**`ReportView` — neither**

- Extract infrastructure coordination into a dedicated service
- Extract customer description to a dedicated presenter class
- Extract mail_summary to a dedicated EmailReport helper
- Extract responsibilities into dedicated classes
- Split ReportView into ReportFormatter and MailerService, and extract customer description
- Extract helper classes for customer description and mail summary
- Extract formatting logic to a dedicated Formatter class
- Move customer description logic to Customer or a CustomerPresenter
- Extract formatting logic into a dedicated Formatter class
- Move customer description logic to Customer or a CustomerPresenter
- Extract formatting logic into a dedicated Formatter
- Move data aggregation to a Service or Repository

  predicted: LCOM4 down ×12, DCC down ×5, NOM down ×4, DCC same ×3, DCC up ×3, CAM up ×1

**`ReportView` — metric-rules**

- Extract customer formatting into its own presenter
- Extract email‑sending responsibility to a dedicated Mailer helper
- Extract business logic to a ReportService and keep ReportView as pure presenter
- Extract formatting and mailing responsibilities into separate classes
- Extract formatting and mailing into dedicated classes
- Extract mail and customer description into dedicated services
- Extract customer formatting logic
- Separate reporting and notification responsibilities
- Extract customer formatting logic
- Separate reporting concerns
- Extract formatting logic to a dedicated Formatter class
- Move customer formatting to Customer or a CustomerFormatter

  predicted: LCOM4 down ×12, DCC down ×8, DCC same ×2, NOM down ×2, WMC down ×1, DCC up ×1

**`Customer` — arch-context**

- Add domain behavior to increase cohesion
- Replace explicit getters with a frozen dataclass and keep only behavior
- Extract tier‑related behavior to a dedicated domain value object
- Add a composite accessor to connect attributes
- Add a composite accessor to connect attributes
- Convert to a frozen dataclass and expose attributes directly

  predicted: LCOM4 down ×6, DCC up ×2, NOM down ×2, WMC down ×2, WMC up ×1, DCC same ×1

**`Customer` — both**

- Replace explicit getters with read‑only properties
- Introduce domain behavior to improve cohesion
- Replace manual boilerplate with a @dataclass
- Replace explicit getters with a dataclass
- Convert to a dataclass and remove explicit getters
- Add an aggregate method to connect accessors

  predicted: LCOM4 down ×5, NOM down ×4, WMC down ×4, DCC up ×1, LCOM4 same ×1, WMC up ×1

**`Customer` — neither**

- Replace trivial getters with public dataclass fields
- Replace explicit getters with dataclass fields or @property accessors
- Replace getters with public fields via a dataclass
- Replace explicit getters with a dataclass and a single property
- Split Customer into smaller cohesive classes
- Convert to a dataclass and remove trivial getters

  predicted: LCOM4 down ×6, NOM down ×5, WMC down ×4, DAM down ×3, DCC up ×1

**`Customer` — metric-rules**

- Replace getters with public fields via a dataclass
- Replace explicit getters with a dataclass and keep only behavior
- Replace trivial getters with a data class and public fields
- Convert to a plain dataclass and expose attributes directly
- Add a hub method that touches all attributes
- Convert to a dataclass and expose attributes directly
- Convert to a dataclass or use properties
- Convert to a Python dataclass
- Convert to a dataclass or record to reduce method count

  predicted: LCOM4 down ×9, NOM down ×8, DAM down ×5, WMC down ×5, DCC same ×2

**`OrderService` — arch-context**

- Extract four focused service classes
- Extract pricing responsibilities to a dedicated PricingService in the domain layer
- Extract responsibility‑specific services
- Split OrderService into focused services
- Split OrderService into four focused services
- Split OrderService into cohesive subservices
- Extract Pricing Logic to Domain Layer
- Extract Audit Trail to Infrastructure Layer
- Extract Notification Handling to Infrastructure Layer
- Extract Pricing and Audit components
- Move notification logic to a dedicated service

  predicted: LCOM4 down ×11, NOM down ×11, WMC down ×8, DCC up ×8, DCC down ×1

**`OrderService` — both**

- Extract Notification responsibilities to a dedicated NotificationService
- Extract Pricing logic into a PricingService
- Extract responsibility‑specific services
- Move pricing logic to a domain PricingPolicy
- Extract focused service classes from OrderService
- Extract responsibilities into dedicated services
- Extract domain concerns into dedicated services
- Split OrderService into dedicated services
- Move discount logic into DiscountPolicy
- Extract Pricing Logic into PricingService
- Extract Audit Logic into AuditService
- Extract Notification Logic into NotificationService

  predicted: LCOM4 down ×12, WMC down ×11, NOM down ×10, DCC down ×5, DCC up ×4, DCC same ×3

**`OrderService` — neither**

- Split OrderService into four focused services
- Introduce an AuditLog value object to encapsulate audit state
- Extract each component into its own service class
- Extract pricing responsibilities into a dedicated PricingService
- Extract audit functionality into an AuditLog component
- Split OrderService into dedicated services
- Split OrderService into dedicated services
- Extract validation logic into OrderValidator
- Introduce a PricingPolicy interface for discounts
- Split OrderService into dedicated component services
- Extract Pricing Logic to PricingService
- Extract Audit Logging to AuditLogger
- Extract Notification Logic to NotificationService
- Extract Pricing Logic into a dedicated component
- Extract Audit Logging into a dedicated component
- Extract Notification Dispatch into a dedicated component

  predicted: LCOM4 down ×16, NOM down ×14, DCC up ×13, WMC down ×11, DCC same ×1

**`OrderService` — metric-rules**

- Extract pricing responsibilities into a dedicated PricingService
- Separate audit logic into an AuditLog component
- Move notification handling to a NotificationFacade
- Extract component services for lifecycle, pricing, audit, and notification
- Extract component services
- Extract validation helpers from place()
- Split OrderService into dedicated services
- Extract Audit into separate AuditLog class
- Move notification logic to dedicated NotifierService
- Delegate pricing to PricingService
- Extract Pricing Logic into a PricingService
- Extract Audit Logging into an AuditLogger
- Extract Notification Handling into a NotificationService
- Extract Pricing Logic into a PricingService
- Extract Audit Logging into an AuditLogger
- Extract Notification Dispatch into a NotificationService
- Extract Pricing Logic into PricingService
- Extract Audit Logging into AuditLog
- Extract Notification Handling into NotificationService

  predicted: LCOM4 down ×18, WMC down ×17, NOM down ×15, DCC up ×6, DCC down ×4, DCC same ×1, CC down ×1, DAM same ×1


## Consistency across repetitions

Mean Jaccard similarity between the repetitions of the same (condition, model, target). A model whose own runs disagree cannot be compared with another until that variance is accounted for.

| Condition | Model | Target | n | Evidence | Prediction |
|---|---|---|---|---|---|
| arch-context | `openai/gpt-oss-120b` | `src.api.report_view:ReportView` | 3 | 1.0 | 0.556 |
| arch-context | `openai/gpt-oss-120b` | `src.domain.entities:Customer` | 3 | 0.5 | 0.5 |
| arch-context | `openai/gpt-oss-120b` | `src.services.order_service:OrderService` | 3 | 1.0 | 1.0 |
| arch-context | `openai/gpt-oss-20b` | `src.api.report_view:ReportView` | 3 | 1.0 | 1.0 |
| arch-context | `openai/gpt-oss-20b` | `src.domain.entities:Customer` | 3 | 0.556 | 0.278 |
| arch-context | `openai/gpt-oss-20b` | `src.services.order_service:OrderService` | 3 | 1.0 | 0.733 |
| arch-context | `qwen/qwen3.8-27b` | `src.api.report_view:ReportView` | 3 | 1.0 | 0.778 |
| arch-context | `qwen/qwen3.8-27b` | `src.domain.entities:Customer` | 3 | 1.0 | 1.0 |
| arch-context | `qwen/qwen3.8-27b` | `src.services.order_service:OrderService` | 2 | 1.0 | 1.0 |
| both | `openai/gpt-oss-120b` | `src.api.report_view:ReportView` | 3 | 1.0 | 0.667 |
| both | `openai/gpt-oss-120b` | `src.domain.entities:Customer` | 3 | 0.5 | 0.25 |
| both | `openai/gpt-oss-120b` | `src.services.order_service:OrderService` | 3 | 1.0 | 0.867 |
| both | `openai/gpt-oss-20b` | `src.api.report_view:ReportView` | 3 | 0.333 | 0.333 |
| both | `openai/gpt-oss-20b` | `src.domain.entities:Customer` | 3 | 0.556 | 0.5 |
| both | `openai/gpt-oss-20b` | `src.services.order_service:OrderService` | 3 | 1.0 | 0.867 |
| both | `qwen/qwen3.8-27b` | `src.api.report_view:ReportView` | 2 | 0.667 | 0.5 |
| both | `qwen/qwen3.8-27b` | `src.domain.entities:Customer` | 2 | 1.0 | 1.0 |
| neither | `openai/gpt-oss-120b` | `src.api.report_view:ReportView` | 3 | 1.0 | 1.0 |
| neither | `openai/gpt-oss-120b` | `src.domain.entities:Customer` | 3 | 0.833 | 0.833 |
| neither | `openai/gpt-oss-120b` | `src.services.order_service:OrderService` | 3 | 1.0 | 0.867 |
| neither | `openai/gpt-oss-20b` | `src.api.report_view:ReportView` | 3 | 1.0 | 0.556 |
| neither | `openai/gpt-oss-20b` | `src.domain.entities:Customer` | 3 | 0.5 | 0.5 |
| neither | `openai/gpt-oss-20b` | `src.services.order_service:OrderService` | 3 | 1.0 | 1.0 |
| neither | `qwen/qwen3.8-27b` | `src.api.report_view:ReportView` | 3 | 0.778 | 0.733 |
| neither | `qwen/qwen3.8-27b` | `src.services.order_service:OrderService` | 2 | 1.0 | 1.0 |
| metric-rules | `openai/gpt-oss-120b` | `src.api.report_view:ReportView` | 3 | 1.0 | 0.417 |
| metric-rules | `openai/gpt-oss-120b` | `src.domain.entities:Customer` | 3 | 1.0 | 1.0 |
| metric-rules | `openai/gpt-oss-120b` | `src.services.order_service:OrderService` | 3 | 0.867 | 0.756 |
| metric-rules | `openai/gpt-oss-20b` | `src.api.report_view:ReportView` | 3 | 1.0 | 1.0 |
| metric-rules | `openai/gpt-oss-20b` | `src.domain.entities:Customer` | 3 | 0.5 | 0.467 |
| metric-rules | `openai/gpt-oss-20b` | `src.services.order_service:OrderService` | 3 | 0.2 | 0.2 |
| metric-rules | `qwen/qwen3.8-27b` | `src.api.report_view:ReportView` | 3 | 1.0 | 0.55 |
| metric-rules | `qwen/qwen3.8-27b` | `src.domain.entities:Customer` | 3 | 1.0 | 1.0 |
| metric-rules | `qwen/qwen3.8-27b` | `src.services.order_service:OrderService` | 3 | 1.0 | 0.833 |

## Schema warnings

- (8×) model reported target 'module:OrderService'; using 'src.services.order_service:OrderService' instead
- (5×) model reported target 'module:src.api.report_view:ReportView'; using 'src.api.report_view:ReportView' instead
- (5×) model reported target 'module:Customer'; using 'src.domain.entities:Customer' instead
- (4×) model reported target 'module:ReportView'; using 'src.api.report_view:ReportView' instead
- (3×) model reported target 'module:src.domain.entities:Customer'; using 'src.domain.entities:Customer' instead
- (2×) model reported target 'module:src.api.report_view'; using 'src.api.report_view:ReportView' instead
- (2×) could not parse the reply even after repair: Unbalanced braces in the reply.
- (2×) model reported target 'module:src.domain.entities.Customer'; using 'src.domain.entities:Customer' instead
- (1×) unknown metric in expected_effect: FEATURE_ENVY_CANDIDATE
- (1×) model reported target 'module:src.services.order_service:OrderService'; using 'src.services.order_service:OrderService' instead
