# Advice analysis (phase 5, part A)

- **Runs:** 27
- **Models:** openai/gpt-oss-120b, openai/gpt-oss-20b, qwen/qwen3.8-27b
- **Targets:** god:OrderManager, utils:classify_order, utils:deep_transform

> This part measures **contract compliance and consistency**, not whether the predictions were correct. Checking correctness requires applying the suggestions, which is part B.

## Contract compliance

`unlinked` counts suggestions naming no metric — the rule the prompt makes mandatory. `repaired` counts replies that were not valid JSON on the first attempt.

| Model | Runs | Suggestions | Per run | Unlinked | Unlinked rate | With prediction | Repaired | Unstructured |
|---|---|---|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | 9 | 12 | 1.33 | 0 | 0.0 | 12 | 0 | 0 |
| `openai/gpt-oss-20b` | 9 | 9 | 1.0 | 0 | 0.0 | 9 | 0 | 0 |
| `qwen/qwen3.8-27b` | 9 | 17 | 1.89 | 0 | 0.0 | 17 | 0 | 0 |

## Consistency across repetitions

Mean Jaccard similarity between the repetitions of the same (model, target) pair. 1.0 means every run cited the same metrics; 0.0 means no overlap at all.

A model whose own runs disagree cannot be meaningfully compared with another model until that variance is accounted for.

| Model | Target | n | Evidence agreement | Prediction agreement | Suggestions per run |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | `god:OrderManager` | 3 | 1.0 | 1.0 | [1, 1, 1] |
| `openai/gpt-oss-120b` | `utils:classify_order` | 3 | 0.833 | 0.833 | [2, 2, 2] |
| `openai/gpt-oss-120b` | `utils:deep_transform` | 3 | 0.639 | 0.55 | [1, 1, 1] |
| `openai/gpt-oss-20b` | `god:OrderManager` | 3 | 0.833 | 0.833 | [1, 1, 1] |
| `openai/gpt-oss-20b` | `utils:classify_order` | 3 | 0.611 | 0.611 | [1, 1, 1] |
| `openai/gpt-oss-20b` | `utils:deep_transform` | 3 | 0.667 | 0.639 | [1, 1, 1] |
| `qwen/qwen3.8-27b` | `god:OrderManager` | 3 | 0.833 | 0.733 | [3, 3, 3] |
| `qwen/qwen3.8-27b` | `utils:classify_order` | 3 | 0.778 | 0.778 | [2, 2, 1] |
| `qwen/qwen3.8-27b` | `utils:deep_transform` | 3 | 1.0 | 1.0 | [1, 1, 1] |

## Prediction profile

Which metrics models predict, and in which direction.

**`openai/gpt-oss-120b`**

- DCC up: 8
- LCOM4 down: 6
- CC down: 6
- WMC down: 3
- NOM down: 3
- PARAMS down: 3
- NESTING down: 3
- LOC same: 1

**`openai/gpt-oss-20b`**

- CC down: 6
- WMC down: 3
- DCC down: 3
- LCOM4 down: 3
- PARAMS down: 3
- NESTING down: 3
- NOM down: 2
- DCC up: 2
- LOC same: 2
- LOC down: 1

**`qwen/qwen3.8-27b`**

- CC down: 6
- WMC down: 3
- NOM down: 3
- LCOM4 down: 3
- PARAMS down: 3
- NESTING down: 3
- DCC up: 2
- LOC same: 2
- DCC down: 1

## Trade-off acknowledgement

A suggestion predicting both `up` and `down` admits it will make some metric worse. One predicting only improvements is either right or optimistic — part B decides which.

| Model | Suggestions with a direction | Acknowledging a trade-off | Rate |
|---|---|---|---|
| `openai/gpt-oss-120b` | 12 | 9 | 0.75 |
| `openai/gpt-oss-20b` | 9 | 2 | 0.222 |
| `qwen/qwen3.8-27b` | 17 | 6 | 0.353 |

## Schema warnings

- (6×) model reported target 'module:OrderManager'; using 'god:OrderManager' instead
- (1×) model reported target 'module:utils'; using 'utils:classify_order' instead
