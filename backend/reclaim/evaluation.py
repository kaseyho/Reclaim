"""Score frozen text probes without putting their reference answers in prompts."""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import re

from dotenv import load_dotenv

from . import ai as ai_module
from .ai import AI, AIUnavailable
from .config import Settings


def normalized(value, key=""):
    if value is None or value == "unknown":
        return None
    if isinstance(value, str):
        value = " ".join(value.strip().casefold().split())
        if key.endswith("compatible_with"):
            return ",".join(sorted(part.strip() for part in value.split(",")))
        if re.search(r"_(?:cm|mm|m|inches|inch|kg|g|ml|l|hz|watts|count)$", key):
            try:
                number = Decimal(value)
                if number.is_finite():
                    return format(number.normalize(), "f")
            except InvalidOperation:
                pass
        return value
    return value


def prediction_facts(kind, result):
    """Free-form names, evidence prose and pickup wording are not exact-scored."""
    collection = "units" if kind == "extract" else "needs"
    fields = ("quantity", "condition", "width_cm", "brand", "sealed") if kind == "extract" else (
        "quantity", "minimum_condition", "max_width_cm", "brand", "sealed"
    )
    facts = {}
    duplicates = defaultdict(int)
    # Coalesce truly identical unit records; two identical singles can mean two goods.
    records = {}
    for unit in result[collection]:
        attributes = sorted(
            ((a["key"], normalized(a["value"], a["key"]), a.get("operator")) for a in unit["attributes"]),
            key=lambda attribute: json.dumps(attribute),
        )
        identity = (unit["item_type"], tuple(normalized(unit.get(f), f) for f in fields if f != "quantity"), tuple(attributes))
        if kind == "extract" and identity in records:
            records[identity]["quantity"] += unit["quantity"]
        else:
            records[identity if kind == "extract" else (identity, len(records))] = {**unit, "quantity": unit["quantity"]}
    def order_key(unit):
        field_values = json.dumps({field: unit.get(field) for field in fields}, sort_keys=True)
        attributes = sorted(
            ((a["key"], normalized(a["value"], a["key"]), a.get("operator")) for a in unit["attributes"]),
            key=lambda attribute: json.dumps(attribute),
        )
        return unit["item_type"], field_values, json.dumps(attributes)

    ordered = sorted(records.values(), key=order_key)
    for unit in ordered:
        item_type = unit["item_type"]
        duplicates[item_type] += 1
        suffix = "" if duplicates[item_type] == 1 else f"#duplicate-{duplicates[item_type]}"
        prefix = f"{collection}.{item_type}{suffix}"
        facts[f"{prefix}.present"] = True
        for field in fields:
            facts[f"{prefix}.{field}"] = normalized(unit.get(field), field)
        attribute_counts = defaultdict(int)
        for attribute in unit["attributes"]:
            key = attribute["key"]
            attribute_counts[key] += 1
            attr_suffix = "" if attribute_counts[key] == 1 else f"#duplicate-{attribute_counts[key]}"
            path = f"{prefix}.attributes.{key}{attr_suffix}"
            facts[path] = normalized(attribute["value"], key)
            if kind == "interpret":
                facts[f"{path}.operator"] = attribute["operator"]
    if kind == "interpret":
        for field in ("budget_minor", "location", "allow_substitutions"):
            facts[field] = normalized(result[field], field)
    return facts


def score_case(case, result):
    gold = {key: normalized(value, key) for key, value in case["gold"].items()}
    actual = prediction_facts(case["kind"], result) if result is not None else {}
    expected_assertions = {key: value for key, value in gold.items() if value is not None}
    actual_assertions = {key: value for key, value in actual.items() if value is not None}
    true_positive = sum(key in expected_assertions and value == expected_assertions[key] for key, value in actual_assertions.items())
    false_positive = len(actual_assertions) - true_positive
    false_negative = len(expected_assertions) - true_positive
    differences = []
    for key in sorted(set(gold) | set(actual)):
        if gold.get(key) != actual.get(key):
            differences.append({"field": key, "expected": gold.get(key), "actual": actual.get(key)})
    warnings = " ".join(result.get("unresolved", [])) if result is not None else ""
    missing_warnings = [pattern for pattern in case.get("required_warnings", []) if not re.search(pattern, warnings, re.I)]
    unknown_fields = [key for key, value in gold.items() if value is None]
    return {
        "true_positive": true_positive, "false_positive": false_positive, "false_negative": false_negative,
        "exact": result is not None and not differences and not missing_warnings,
        "unknown_fields": len(unknown_fields),
        "unknown_abstentions": sum(actual.get(key) is None for key in unknown_fields),
        "warning_checks": len(case.get("required_warnings", [])),
        "differences": differences, "missing_warnings": missing_warnings,
    }


def ratio(numerator, denominator):
    return round(numerator / denominator, 6) if denominator else None


def aggregate(rows):
    sums = {key: sum(row["score"][key] for row in rows) for key in (
        "true_positive", "false_positive", "false_negative", "unknown_fields", "unknown_abstentions"
    )}
    latencies = sorted(row["trace"]["latency_ms"] for row in rows if row.get("trace") and row["trace"].get("latency_ms") is not None)
    known_input_tokens = sum(row.get("trace", {}).get("input_tokens") or 0 for row in rows)
    known_output_tokens = sum(row.get("trace", {}).get("output_tokens") or 0 for row in rows)
    usage_complete = bool(rows) and all(row.get("trace", {}).get("input_tokens") is not None and row.get("trace", {}).get("output_tokens") is not None for row in rows)
    return {
        "cases": len(rows), "successful_responses": sum(row["status"] == "COMPLETED" for row in rows),
        "exact_cases": sum(row["score"]["exact"] for row in rows),
        "precision": ratio(sums["true_positive"], sums["true_positive"] + sums["false_positive"]),
        "recall": ratio(sums["true_positive"], sums["true_positive"] + sums["false_negative"]),
        **sums,
        "warning_checks": sum(row["score"]["warning_checks"] for row in rows),
        "missed_warning_checks": sum(len(row["score"]["missing_warnings"]) for row in rows),
        "latency_p50_ms": latencies[math.ceil(len(latencies) * .5) - 1] if latencies else None,
        "latency_p95_ms": latencies[math.ceil(len(latencies) * .95) - 1] if latencies else None,
        "input_tokens": known_input_tokens if usage_complete else None,
        "output_tokens": known_output_tokens if usage_complete else None,
        "known_input_tokens": known_input_tokens, "known_output_tokens": known_output_tokens,
        "token_usage_complete": usage_complete,
        # Provider traces deliberately do not invent a billed or estimated cost.
        "cost_usd": 0 if rows and all(row.get("trace", {}).get("provider") == "demo-parser" for row in rows) else None,
    }


def load_cases(path):
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Dataset must contain unique, nonempty case identifiers.")
    for case in cases:
        if case["kind"] not in {"extract", "interpret"} or case["category"] not in {"furniture", "creator", "bulk"}:
            raise ValueError(f"Invalid probe kind/category: {case['id']}")
        if not case["gold"] or not 3 <= len(case["text"]) <= 4000:
            raise ValueError(f"Invalid probe text/labels: {case['id']}")
        for pattern in case.get("required_warnings", []):
            re.compile(pattern)
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("baseline", "openai", "soclaas"), default="baseline")
    parser.add_argument("--dataset", type=Path, default=Path("evaluation/cases.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/raw/ai-evaluation.json"))
    parser.add_argument("--model", action="append", help="Repeat to compare explicit model IDs or aliases; connected modes only.")
    parser.add_argument("--limit", type=int, help="Explicit small smoke run; report records the reduced scope.")
    parser.add_argument("--stop-after-errors", type=int, default=3)
    args = parser.parse_args()
    if (args.limit is not None and args.limit < 1) or args.stop_after_errors < 1:
        parser.error("Limits must be positive.")
    if args.provider == "baseline" and args.model:
        parser.error("Baseline mode does not call or compare models.")
    load_dotenv()
    key_name = "SOCLAAS_API_KEY" if args.provider == "soclaas" else "OPENAI_API_KEY"
    api_key = os.getenv(key_name, "") if args.provider != "baseline" else ""
    if args.provider != "baseline" and not api_key:
        parser.error(f"Set {key_name} in the ignored .env before selecting {args.provider} mode.")
    try:
        dataset = load_cases(args.dataset)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(f"Dataset could not be loaded: {error}")
    selected = dataset[:args.limit] if args.limit else dataset
    default_model = os.getenv("SOCLAAS_MODEL", "default") if args.provider == "soclaas" else os.getenv("OPENAI_MODEL", "gpt-4.1-mini-2025-04-14")
    models = args.model or ([default_model] if api_key else [None])
    report = {
        "provenance": "Codex-authored synthetic text probes; labels frozen separately from runtime prompts; not human-reviewed production data.",
        "scope": "Inventory and buyer-request proposals only; no photographs, solver/payments, usable confirmed facts or user research are evaluated.",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "pipeline_sha256": hashlib.sha256(Path(ai_module.__file__).read_bytes()).hexdigest(),
        "grader_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "dataset_cases": len(dataset), "requested_cases": len(selected),
        "provider": args.provider, "runs": [],
    }
    for model in models:
        pipeline = AI(Settings(openai_api_key=api_key if args.provider == "openai" else "", soclaas_api_key=api_key if args.provider == "soclaas" else "", openai_model=model if args.provider == "openai" else "gpt-4.1-mini-2025-04-14", soclaas_model=model if args.provider == "soclaas" else "default"))
        rows = []
        consecutive_errors = 0
        for case in selected:
            try:
                result, trace = pipeline.run(case["kind"], case["text"], case["category"])
                payload = result.model_dump(mode="json")
                row = {"id": case["id"], "kind": case["kind"], "category": case["category"], "status": "COMPLETED", "prediction": payload, "trace": trace, "score": score_case(case, payload)}
                consecutive_errors = 0
            except AIUnavailable as error:
                cause = error.__cause__ or error
                failure = {"type": type(cause).__name__}
                if hasattr(cause, "status_code"):
                    failure["http_status"] = cause.status_code
                row = {"id": case["id"], "kind": case["kind"], "category": case["category"], "status": "UNAVAILABLE", "failure": failure, "prediction": None, "score": score_case(case, None)}
                consecutive_errors += 1
            rows.append(row)
            if consecutive_errors >= args.stop_after_errors:
                break
        report["runs"].append({
            "model_requested": model, "prompt_version": pipeline.prompt_version,
            "models_returned": sorted({row["trace"]["model"] for row in rows if row.get("trace", {}).get("model")}),
            "completed_requested_scope": len(rows) == len(selected),
            "completed_full_dataset": len(rows) == len(dataset),
            "summary": aggregate(rows),
            "by_kind": {kind: aggregate([row for row in rows if row["kind"] == kind]) for kind in ("extract", "interpret")},
            "cases": rows,
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "provider": args.provider, "dataset_cases": len(dataset), "requested_cases": len(selected), "runs": [{key: run[key] for key in ("model_requested", "completed_full_dataset", "summary")} for run in report["runs"]]}, indent=2))
    return 0 if all(run["completed_requested_scope"] and all(row["status"] == "COMPLETED" for row in run["cases"]) for run in report["runs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
