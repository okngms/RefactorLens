# Prediction accuracy (phase 5, part B)

- **Cases:** 6

> Each case applies **one** suggestion under the narrowest possible interpretation, always repetition 1. Cases whose behaviour tests fail are marked `broken`: their metric delta is void, because a refactoring that improves the numbers while breaking the code is a regression.

| Model | Target | Status | Hits | Misses | Unverifiable | Accuracy |
|---|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | `god:OrderManager` | ok | 1 | 3 | 0 | 25% |
| `openai/gpt-oss-120b` | `utils:classify_order` | ok | 1 | 0 | 1 | 100% |
| `openai/gpt-oss-20b` | `god:OrderManager` | broken | 4 | 0 | 0 | 100% |
| `openai/gpt-oss-20b` | `utils:classify_order` | ok | 2 | 0 | 0 | 100% |
| `qwen/qwen3.8-27b` | `god:OrderManager` | ok | 1 | 3 | 0 | 25% |
| `qwen/qwen3.8-27b` | `utils:classify_order` | ok | 1 | 1 | 0 | 50% |

## Overall (valid cases only)

- Verifiable predictions: 13
- Correct: 6
- **Accuracy: 46%**

## Per-metric breakdown

| Metric | Predicted | Correct | Accuracy |
|---|---|---|---|
| CC | 3 | 3 | 100% |
| DCC | 2 | 0 | 0% |
| LCOM4 | 2 | 0 | 0% |
| LOC | 1 | 0 | 0% |
| NOM | 2 | 0 | 0% |
| PARAMS | 1 | 1 | 100% |
| WMC | 2 | 2 | 100% |

## Broken cases

- `openai/gpt-oss-20b` / `god:OrderManager`: 42 failed, 49 passed in 0.56s
