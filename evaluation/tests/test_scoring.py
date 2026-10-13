import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from reclaim.ai import AIUnavailable
from reclaim.evaluation import aggregate, load_cases, main, normalized, score_case


def unit(**overrides):
    return {"item_type": "desk", "quantity": 1, "condition": "unknown", "width_cm": None, "brand": None, "sealed": None, "attributes": [], **overrides}


class ScoringChecks(unittest.TestCase):
    def test_wrong_budget_counts_as_both_false_positive_and_missing_truth(self):
        case = {"kind": "interpret", "gold": {"budget_minor": 1000, "location": None, "allow_substitutions": False}}
        result = {"needs": [], "budget_minor": 2000, "location": None, "allow_substitutions": False, "unresolved": []}
        score = score_case(case, result)
        self.assertEqual((score["false_positive"], score["false_negative"]), (1, 1))
        self.assertFalse(score["exact"])

    def test_invented_unknown_attribute_is_not_ignored(self):
        case = {"kind": "extract", "gold": {"units.desk.present": True, "units.desk.quantity": 1, "units.desk.width_cm": None}}
        result = {"units": [unit(attributes=[{"key": "compatible_with", "value": "CAM-A"}])], "unresolved": []}
        score = score_case(case, result)
        self.assertEqual(score["false_positive"], 1)
        self.assertFalse(score["exact"])

    def test_false_is_an_assertion_not_an_unknown_value(self):
        case = {"kind": "extract", "gold": {"units.desk.present": True, "units.desk.quantity": 1, "units.desk.sealed": False}}
        score = score_case(case, {"units": [unit(sealed=True)], "unresolved": []})
        self.assertEqual((score["false_positive"], score["false_negative"]), (1, 1))

    def test_identical_individual_units_can_be_coalesced(self):
        case = {"kind": "extract", "gold": {"units.desk.present": True, "units.desk.quantity": 2}}
        score = score_case(case, {"units": [unit(), unit()], "unresolved": []})
        self.assertTrue(score["exact"])

    def test_duplicate_buyer_needs_are_not_silently_coalesced(self):
        case = {"kind": "interpret", "gold": {"needs.desk.present": True, "needs.desk.quantity": 2, "needs.desk.minimum_condition": "good", "budget_minor": 1000, "location": None, "allow_substitutions": False}}
        need = {"item_type": "desk", "quantity": 1, "minimum_condition": "good", "max_width_cm": None, "brand": None, "sealed": None, "attributes": []}
        score = score_case(case, {"needs": [need, need], "budget_minor": 1000, "location": None, "allow_substitutions": False, "unresolved": []})
        self.assertFalse(score["exact"])
        self.assertGreater(score["false_positive"], 0)

    def test_conflicting_duplicate_unit_order_does_not_change_scores(self):
        case = {"kind": "extract", "gold": {"units.desk.present": True, "units.desk.quantity": 1, "units.desk.width_cm": 90}}
        units = [unit(width_cm=90), unit(width_cm=100)]
        self.assertEqual(score_case(case, {"units": units}), score_case(case, {"units": units[::-1]}))

    def test_missing_provider_output_cannot_achieve_precision_or_exactness(self):
        case = {"kind": "extract", "gold": {"units.desk.present": True, "units.desk.quantity": 1}}
        score = score_case(case, None)
        summary = aggregate([{"status": "UNAVAILABLE", "score": score}])
        self.assertIsNone(summary["precision"])
        self.assertEqual(summary["recall"], 0)
        self.assertEqual(summary["exact_cases"], 0)
        self.assertIsNone(summary["cost_usd"])
        self.assertIsNone(summary["input_tokens"])

    def test_numeric_units_are_normalized_but_identifiers_keep_leading_zeros(self):
        self.assertEqual(normalized("24.0", "diagonal_inches"), normalized("24", "diagonal_inches"))
        self.assertNotEqual(normalized("0012", "model_number"), normalized("12", "model_number"))

    def test_required_missing_constraint_warning_affects_exactness(self):
        case = {"kind": "extract", "gold": {"units.desk.present": True, "units.desk.quantity": 1}, "required_warnings": ["width|dimension"]}
        score = score_case(case, {"units": [unit()], "unresolved": ["Please review this item."]})
        self.assertEqual(score["missing_warnings"], ["width|dimension"])
        self.assertFalse(score["exact"])

    def test_frozen_dataset_has_all_categories_and_the_declared_counts(self):
        cases = load_cases(Path(__file__).resolve().parents[1] / "cases.jsonl")
        self.assertEqual(len(cases), 90)
        for category in ("furniture", "creator", "bulk"):
            self.assertEqual(sum(c["category"] == category and c["kind"] == "extract" for c in cases), 10)
            self.assertEqual(sum(c["category"] == category and c["kind"] == "interpret" for c in cases), 20)

    def test_baseline_never_uses_a_key_even_when_one_is_configured(self):
        case = {"id": "offline", "kind": "extract", "category": "furniture", "text": "One desk", "gold": {"units.desk.present": True, "units.desk.quantity": 1}}
        with tempfile.TemporaryDirectory() as directory:
            dataset, output = Path(directory) / "cases.jsonl", Path(directory) / "report.json"
            dataset.write_text(json.dumps(case) + "\n")
            args = ["evaluate", "--provider", "baseline", "--dataset", str(dataset), "--output", str(output)]
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key-must-not-be-used"}), patch("sys.argv", args), patch("reclaim.ai.OpenAI", side_effect=AssertionError("No network client allowed")), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            report = json.loads(output.read_text())
            self.assertEqual(report["provider"], "baseline")
            self.assertIsNone(report["runs"][0]["model_requested"])

    def test_even_one_failed_provider_response_makes_the_command_fail(self):
        case = {"id": "unavailable", "kind": "extract", "category": "furniture", "text": "One desk", "gold": {"units.desk.present": True}}
        with tempfile.TemporaryDirectory() as directory:
            dataset, output = Path(directory) / "cases.jsonl", Path(directory) / "report.json"
            dataset.write_text(json.dumps(case) + "\n")
            args = ["evaluate", "--dataset", str(dataset), "--output", str(output)]
            with patch("sys.argv", args), patch("reclaim.evaluation.AI.run", side_effect=AIUnavailable()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 1)
            report = json.loads(output.read_text())
            self.assertEqual(report["runs"][0]["summary"]["successful_responses"], 0)


if __name__ == "__main__":
    unittest.main()
