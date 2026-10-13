# Reclaim text evaluation

This is a preparation benchmark for the supplied plan's model-evaluation phase. It contains **30 synthetic listing descriptions and 60 synthetic buyer requests**, split evenly across furniture, creator equipment and sealed bulk goods. Descriptions, fictional brands and reference labels were authored by Codex for Reclaim; no real sellers, buyers or external listing dataset supplied this evidence.

The labels were written from each description and frozen in `cases.jsonl` separately from the unchanged runtime prompt. They are never included in an AI request. No independent human labeller has reviewed them. This is **not** the plan's completed human-reviewed held-out evaluation, photo validation or usability/economics research.

The cases cover quantities, condition, centimetre normalization, dollar budgets, sealed goods, model/connector/compatibility attributes, explicit unknowns, negated goods, acceptable substitutions and quoted malicious instructions. The [official OpenAI evaluation guide](https://developers.openai.com/api/docs/guides/evaluation-best-practices) recommends task-specific metrics and human calibration; expert review and representative real cases are still required here.

## Run the offline baseline

From the repository root, after README's dependency setup:

```sh
PYTHONPATH=backend .venv/bin/python -m unittest discover -s evaluation/tests -q
PYTHONPATH=backend .venv/bin/python -m reclaim.evaluation \
  --provider baseline --output artifacts/raw/ai-evaluation-baseline.json
```

Baseline mode forces an empty API key, even if `.env` has one. It uses the labelled deterministic demo parser and makes **no OpenAI calls**. The checked-in [baseline report](baseline.json) records the actual predictions, per-case differences, trace metadata and file hashes. Its generated summary is in [baseline.md](baseline.md).

## Run a connected model

Set `OPENAI_API_KEY` in the ignored `.env` as described in `docs/provider-setup.md`. Start with three cases, inspect the successful Responses IDs and returned model, then run the full set:

```sh
PYTHONPATH=backend .venv/bin/python -m reclaim.evaluation \
  --provider openai --model gpt-4.1-mini-2025-04-14 --limit 3 \
  --output artifacts/raw/ai-evaluation-smoke.json

PYTHONPATH=backend .venv/bin/python -m reclaim.evaluation \
  --provider openai --model gpt-4.1-mini-2025-04-14 \
  --output artifacts/raw/ai-evaluation-openai.json
```

For a comparison, repeat `--model` with another explicit pinned model available in the API project. A full run makes up to 90 requests **per model** and uses the provider's metered API. The runner does not choose another model or call the API automatically. It stops after three consecutive unavailable responses, retains failed-case outcomes, reports incomplete scope, and exits unsuccessfully if any attempted response failed. It writes results to ignored files by default.

Use the report's scores and scope for the quality decision; exit status zero records completed requested calls and report creation. It does not apply an accuracy threshold.

Review the application's seller/buyer experience and photograph extraction separately. Do not replace the app's model setting based on an incomplete report or a precision score alone.

## What the numbers mean

- **Precision:** correct non-unknown field assertions / all proposed non-unknown assertions. Wrong values and invented extra goods/attributes count as false positives.
- **Recall:** correct non-unknown field assertions / all non-unknown reference assertions. A wrong value also leaves a missing reference assertion.
- **Exact cases:** all scored assertions match, no extra assertion exists, a response was returned, and every required ambiguity-warning check passes. Identical seller inventory records can combine their quantities; duplicate buyer needs remain an error because buyer confirmation requires unique item types.
- **Unknown abstentions:** labelled unknown fields left unknown or absent. Read this together with recall: omitting an entire item also omits its known facts.
- **Warnings:** explicit regular-expression checks on the unresolved list. These are limited heuristics and need human review.
- **Latency:** the application trace's rounded milliseconds, with nearest-rank p50 and p95. A reported zero for the regex parser is below its reporting resolution; it is not an OpenAI or complete-match latency result.
- **Tokens and cost:** measured trace totals only. Missing usage makes the total unknown. OpenAI cost stays `null` until billing evidence is reconciled; the offline parser uses zero provider tokens and zero provider API cost.

Names, evidence prose and free-form pickup wording are not exact-scored. Case, whitespace and numeric unit spellings are normalized; model identifiers retain meaningful leading zeros. Each fixture has one reference record per item type. Multiple incompatible records of one type are treated as duplicate errors; this set does not assess general inventory entity alignment.

The report records dataset and pipeline hashes, prompt version, requested and returned model identities, response IDs, sampling scope and per-case errors. A three-case smoke run is not a full-dataset result. These scores concern **unconfirmed proposals**; they do not measure usable seller-confirmed facts, accepted allocation validity, payments, photographs, economic savings or user outcomes.

## Before claiming model accuracy

Have an independent domain reviewer inspect the labels and error rubric. Add representative consented listings, photographs and buyer requests; record their provenance. Keep final evaluation cases separate from development examples. If these probes are used to tune the prompt or parser, treat them as development data and collect a fresh held-out set. Run candidate models on the same frozen cases, inspect errors manually, and report precision, recall, completion rates, uncertainty handling, latency and actual cost together.

The proposed 95% usable-fact precision target and five-buyer/two-seller sessions remain unverified. The offline report does not establish those targets.
