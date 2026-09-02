# layered_project — deliberate architecture violations and smells

The contract for this fixture. Every number here was **measured**, not estimated,
and each is asserted somewhere in `tests/`. If the fixture changes, these values
change with it in the same commit.

Companion to `examples/messy_project`, which has bad metrics and no architecture.
This one has bad metrics **and** a layer structure, so that v2 can be tested on
the thing it exists for: whether the same number means different things in
different places.

---

## Layers

Declared in `rlens.yaml` under `arch.layers`, so inference does not run.

```
src/
├── api/        presentation    order_controller.py, report_view.py
├── services/   application     order_service.py, pricing_service.py
├── domain/     domain          entities.py, policies.py
├── infra/      infrastructure  order_repository.py, email_client.py
└── shared/     (not declared)  helpers.py, registry.py
```

Allowed direction: `presentation → {application, domain}`, `application →
{domain}`, `infrastructure → {domain}`, `domain → {}`.

`shared/` matches no directory convention, carries no class suffix, and sits in
an import cycle so its topological depth is undefined. **Layer inference is
expected to report `unknown` here.** A tool that guesses a layer for these two
modules is guessing, and the fixture exists to catch that.

---

## Violations

| Code | Where | What |
|---|---|---|
| `LV-DIR` | `domain/policies.py` → `infra/order_repository.py` | Domain imports infrastructure. The classic inversion: `DiscountPolicy.loyalty_bonus` queries the repository directly. |
| `LV-SKIP` | `api/report_view.py` → `infra/{order_repository,email_client}.py` | Presentation reaches past application straight into infrastructure. Two edges from one module. |
| `LV-SKIP` | `api/order_controller.py` → `infra/order_repository.py` | The import that makes the leak below possible. |
| `LV-CYCLE` | `shared/helpers.py` ↔ `shared/registry.py` | A real import cycle (SCC of size 2). Built with `import x` and deferred attribute access, so it works at runtime — the cycle is structural, not a crash. |
| `LV-LEAK` | `api/order_controller.py` | `repository()` returns `OrderRepository` in its annotated public signature. Direction is legal; the infrastructure *type* leaks upward. Only detectable because the annotation is there. |

**Six violations in total**, measured: one `LV-DIR`, three `LV-SKIP`, one
`LV-CYCLE`, one `LV-LEAK`.

`order_controller` carries both `LV-SKIP` and `LV-LEAK`, and that is correct
rather than double-counting: annotating a return type requires importing it, so
a leak almost always travels with an import violation. They are separate
findings with separate fixes — stop importing the type, or stop exposing it.

---

## Smells

| Label | Where | Measured | Rule |
|---|---|---|---|
| `god_class` | `services.order_service:OrderService` | NOM 26, WMC 56, LCOM4 5 | NOM≥20 ∧ WMC≥50 ∧ LCOM4≥3 |
| `data_class` | `domain.entities:Customer` | NOM 5, WMC 5, DAM 1.0, 4 of 5 accessors | NOM≤5 ∧ WMC≤NOM+2 ∧ DAM≥0.5 ∧ accessors≥0.7 |
| `feature_envy_candidate` | `api.report_view:ReportView.describe_customer` | 4 accesses to `Customer`, 1 to own state | ratio ≥ 2 |

### Why `Customer` is the important one

Its LCOM4 is **4**. Under v1's rules that reads as badly uncohesive, and
FINDINGS-1 documented this as a known weakness: LCOM4 punishes data holders that
have one accessor per field.

`Customer` is not badly designed. It is five accessors over four private fields —
exactly what a domain entity should look like. The `data_class` label exists to
say so, and this fixture is where that claim gets tested. If v2 still presents
`Customer` as a cohesion problem, the label is not doing its job.

### Why `OrderService` has no violation

It is a god class by every metric — NOM 26, WMC 56, LCOM4 5 — and its imports
are **entirely legal**: it imports `domain` only. The repository and the mailer
arrive through the constructor without type annotations, so the application
layer never binds to a concrete infrastructure type.

This is the fixture's central claim, and it was wrong in the first draft. The
constructor originally annotated `repository: OrderRepository`, which required
importing `infra` and produced two `LV-SKIP` violations. Measuring the fixture
is what caught it. Metrics bad, architecture clean — but only after the code
actually matched the claim.

`messy_project` cannot make this distinction — it has no layers. That is the
whole point of adding this fixture: the two failure modes are separable, and a
tool that conflates them is not architecture-aware, only metric-aware.

---

## Full measurements

| Class | NOM | WMC | LCOM4 | DCC | DAM | CAM |
|---|---|---|---|---|---|---|
| `services.order_service:OrderService` | 26 | 56 | 5 | 4 | 1.00 | — |
| `domain.entities:Customer` | 5 | 5 | 4 | 0 | 1.00 | — |
| `domain.entities:Order` | 3 | 5 | 2 | 2 | 0.00 | — |
| `domain.policies:DiscountPolicy` | 2 | 5 | 2 | 1 | 1.00 | 0.50 |
| `infra.order_repository:OrderRepository` | 4 | 5 | 1 | 1 | 1.00 | 0.50 |
| `api.report_view:ReportView` | 4 | 4 | 2 | 2 | 1.00 | — |
| `api.order_controller:OrderController` | 3 | 3 | 2 | 2 | 1.00 | — |
| `shared.registry:Registry` | 3 | 3 | 1 | 0 | 1.00 | 1.00 |
| `infra.email_client:EmailClient` | 2 | 2 | 1 | 0 | 0.50 | 1.00 |
| `services.pricing_service:PricingService` | 2 | 2 | 1 | 1 | 1.00 | 1.00 |
| `domain.entities:OrderLine` | 1 | 1 | 1 | 0 | 0.00 | — |

`—` means CAM was not computed: annotation coverage below the threshold, or no
annotated parameters. Several classes annotate their constructors but not their
methods, which is what most real Python looks like.

---

## Import graph

11 project-internal edges across 10 modules, nothing unresolved.

| Module | Ca | Ce | Instability | Depth |
|---|---|---|---|---|
| `api.order_controller` | 0 | 2 | 1.00 | 0 |
| `api.report_view` | 0 | 2 | 1.00 | 0 |
| `services.order_service` | 1 | 2 | 0.67 | 1 |
| `services.pricing_service` | 0 | 1 | 1.00 | 0 |
| `domain.policies` | 2 | 1 | 0.33 | 2 |
| `domain.entities` | 2 | 0 | 0.00 | 3 |
| `infra.order_repository` | 3 | 1 | 0.25 | 3 |
| `infra.email_client` | 1 | 0 | 0.00 | 1 |
| `shared.helpers` | 1 | 1 | 0.50 | 0 |
| `shared.registry` | 1 | 1 | 0.50 | 0 |

The values behave as a layered design predicts: `domain.entities` is maximally
stable (imports nothing, is imported by others), the presentation modules are
maximally unstable. Every module importing `infra.order_repository` does so in
violation — one `LV-DIR` and two `LV-SKIP`.

## Behaviour tests

71 tests in `tests/`, covering every public method of every class.

Same rule as `messy_project`: **no metric delta counts unless these pass.** A
suggestion that improves the layer structure while breaking the code is a
regression, and FINDINGS-1 contains a real case where exactly that happened.

Two of them assert the deliberate defects behaviourally rather than statically:

- `test_repository_is_exposed` — the leak is real, an infrastructure object
  genuinely crosses the boundary.
- `test_circular_import_works_at_runtime` — the cycle is structural, not a
  runtime error, so it cannot be dismissed as broken code.

---

## Changing this fixture

Every value above is asserted in the test suite. Adding a method to
`OrderService` can push it past a smell threshold; adding an import can create a
violation that is not listed here. Update this file in the same commit, or the
golden tests will fail for reasons nobody can trace.

Particularly delicate: `OrderService` sits at WMC 56 against a threshold of 50.
Removing complexity from it can silence the `god_class` label.

Equally delicate: annotating `OrderService.__init__` with concrete
infrastructure types reintroduces two `LV-SKIP` violations and destroys the
"bad metrics, clean architecture" case the fixture exists to demonstrate.
