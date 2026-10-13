# Offline demo-parser report

Measured 13 October 2026, 09:57:56 Singapore time.

**Provider: deterministic demo parser. No OpenAI calls or model comparison took place.**

Scope: synthetic, unconfirmed text proposals only. No photographs, human sessions, payments or accepted allocations were measured. See the [method and limitations](README.md).

| Probe group | Returned / selected | Precision | Recall | Exact cases |
|---|---:|---:|---:|---:|
| Listings | 30 / 30 | 68.79% | 52.89% | 1 / 30 |
| Buyer requests | 60 / 60 | 76.49% | 64.46% | 1 / 60 |
| All probes | 90 / 90 | 74.03% | 60.54% | 2 / 90 |

Micro totals: **402 correct assertions**, **141 incorrect or extra assertions**, **262 missing reference assertions**. All 303 labelled unknown fields were left unknown or absent; this does not compensate for the missing known facts. 5 of 16 required ambiguity-warning checks were missed.

The most common limitations are missing explicit condition/location, unsupported quantities or unit wording, and keyword matches to negated or quoted goods. The parser is deliberately labelled and all proposals still require human correction and confirmation. These findings do not justify a real-model accuracy claim.

Provider input/output tokens: **0 / 0**. Provider API cost: **$0**. Trace p50/p95 are **0 / 0 rounded milliseconds**, below this trace's reporting resolution; these are not OpenAI or complete-match latency measurements.

## Reproducibility

- Dataset SHA-256: `8ae84a2c4bc8c9f59187179012cfc015c5f599b1d6b0c5400d502bca1eadf0d7`
- Application AI-module SHA-256: `d5fcd64a06b8fc4697933179e0d01ecc442e362a2acf25cd5359bf5e5c53b0d7`
- Grader SHA-256: `9f1f3351dc181d514cccc69e9d603e7a484804da85bf4599d991768b443ca69a`
- Prompt version: `reclaim-extract-v1`
- Full dataset processed: **90 / 90**.
- Requested/returned model: **none**.
- [Full predictions, differences and traces](baseline.json).

Actual OpenAI results, expert-reviewed labels, image cases, model selection evidence and buyer/seller sessions remain pending.
