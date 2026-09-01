# RefactorLens suggestions

- **Project:** `/path/to/examples/messy_project`
- **Generated:** 2026-08-29T16:25:50+00:00
- **Provider:** groq (`openai/gpt-oss-120b`)
- **Temperature:** 0.2
- **rlens:** 0.2.0

> Each suggestion states a **predicted effect** on the metrics. After applying a change, `rlens verify --advice` checks whether the prediction held.

## god:OrderManager

The class aggregates four unrelated responsibilities.

### 1. Extract order CRUD to an OrderRepository class

- **Evidence:** LCOM4, NOM, WMC, DCC
- **Predicted effect:** LCOM4 down, NOM down, WMC down, DCC up

Move _orders and _next_id into OrderRepository; delegate the eight order methods.

**Risks:** Splitting the class changes the public API.
