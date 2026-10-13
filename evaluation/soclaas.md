# Connected SOCLAAS development evaluation

Measured 13 October 2026, 14:11:07 Singapore time.

Requested model: **default**. Returned model: **qwen3.6:35b**. Prompt version: **reclaim-extract-v5**.

Scope: 30 Codex-authored synthetic listings and 60 synthetic buyer requests. Repeated probes informed pickup-place schema clarification, so these are development/regression results, not an untouched held-out evaluation. Scores concern unconfirmed text proposals. No independent human labeller, real photographs, accepted allocations, payments or human sessions were evaluated. See the [method and limitations](README.md).

| Probe group | Returned / attempted | Precision | Recall | Exact cases |
| --- | ---: | ---: | ---: | ---: |
| Listings | 30 / 30 | 96.79% | 93.78% | 21 / 30 |
| Buyer requests | 60 / 60 | 96.32% | 95.44% | 49 / 60 |
| All probes | 90 / 90 | 96.48% | 94.88% | 70 / 90 |

Micro totals: **630 correct assertions**, **23 incorrect or extra assertions**, **34 missing reference assertions**. All 303 labelled unknowns were left unknown or absent; this does not compensate for omitted known facts. 6 of 16 required ambiguity-warning checks were missed.

Trace p50/p95: **1536 / 2986 ms**. Measured input/output tokens: **86557 / 15729**. Cost is **unmeasured**; provider billing remains authoritative.

The proposed 95% usable-fact precision target is not established by this development result. Precision is not complete-request correctness; missing facts and ambiguity warnings still need correction. Fresh independent labels, representative real photos and human sessions remain necessary. These scores are not a guarantee about future calls or user outcomes.

The earlier offline parser report is a historical pipeline comparison, not an experiment isolating only the model: the connected adapter and prompt also changed. No alternative model was selected or compared; the user-requested default alias remains configured.

## Reproducibility

- Dataset SHA-256: `8ae84a2c4bc8c9f59187179012cfc015c5f599b1d6b0c5400d502bca1eadf0d7`
- Application AI-module SHA-256: `9b7c91b28b3f744aab118e2fe7fb7cb6efcf3470f58303da789e36acb94a1ca5`
- Grader SHA-256: `d3bb2f7bc265f567bc46f375db76762f3eecab387d2bcd9ce2dbc02997120da8`
- Schema SHA-256 at curation: `63dd28b065709637430a95c453218a28312cb85d55cbe060d6b27b74e7456b9e`
- [Full predictions, differences, response IDs and measured traces](soclaas.json).
