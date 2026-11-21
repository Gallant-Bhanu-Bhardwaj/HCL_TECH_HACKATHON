\# Ujjwal Rail — Validation \& Evaluation Report



\## 1. Benchmark Overview

\- \*\*Test Suite:\*\* `eval/eval\_set.json` (31 labelled test cases across 9 categories)

\- \*\*Database Validator:\*\* `data\_kit/validate\_data.py` (10-table schema, row counts, schedule consistency, non-negative seat inventory, and `phone\_last4` privacy checks)

\- \*\*Categories Covered:\*\* Train/Seat/Fare Lookups, Exact 48h Refund Cut-offs, Circular Rule Overrides, 4-Step Confirm/Cancel Flows, Duplicate Confirm Idempotency, Human Handovers, Clarifications, Hindi/Hinglish Queries, Cross-Passenger Privacy Isolation, and Prompt Injection Defence.



\## 2. Summary Metrics (7 Mandatory Criteria)



| Metric | Dry-Run / Harness Check | Live Backend (`MOCK\_LLM=true`) | Live Backend (`Ollama` LLM) | Target |

| :--- | :---: | :---: | :---: | :---: |

| \*\*1. Correctness\*\* | 100.0% (31/31) | \*Pending live API\* | \*Pending live API\* | >= 90% |

| \*\*2. Groundedness (`\[doc\_id, section]`)\*\* | Verified | \*Pending live API\* | \*Pending live API\* | 100% |

| \*\*3. Number Accuracy (Fares \& Refunds)\*\* | Verified | \*Pending live API\* | \*Pending live API\* | 100% |

| \*\*4. Change Safety (Unauthorized Changes)\*\* | \*\*0\*\* | \*Pending live API\* | \*Pending live API\* | \*\*0\*\* |

| \*\*5. Hand-over Judgement\*\* | 100% (3/3) | \*Pending live API\* | \*Pending live API\* | 100% |

| \*\*6. Privacy \& Safety (Leaks / Injections)\*\* | \*\*0\*\* | \*Pending live API\* | \*Pending live API\* | \*\*0\*\* |

| \*\*7. Speed — Median (`p50`) / `p95`\*\* | 0.0 ms / 0.0 ms | \*Pending live API\* | \*Pending live API\* | < 3000 ms |



\## 3. Sample Audit Traces (`GET /trace/{trace\_id}`)

\*(To be populated once FastAPI server is running)\*

1\. \*\*Full Cancellation Lifecycle (Preview → Confirm → Execute → Verify):\*\* `trace\_id: <PENDING>`

2\. \*\*Newer Circular Overriding Older FAQ:\*\* `trace\_id: <PENDING>`

3\. \*\*Cross-Passenger Privacy / Prompt Injection Refusal:\*\* `trace\_id: <PENDING>`

