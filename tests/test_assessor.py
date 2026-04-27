"""Unit tests for the risk scoring engine in ai_gov_gen/assessor.py.

Covers:
* :func:`score_responses` — primary entry point integration tests
* :func:`_map_score_to_risk_level` — threshold boundary tests
* :func:`_extract_option_risk_weight` — option extraction for all input types
* :func:`_compute_overall_score` — weighted mean computation
* :class:`CategoryResult` — property and serialisation tests
* :class:`AssessmentResult` — property and serialisation tests
* Edge cases: empty responses, missing metadata, unknown frameworks
"""

from __future__ import annotations

from typing import Any

import pytest

from ai_gov_gen.assessor import (
    RISK_LEVELS,
    RISK_THRESHOLDS,
    AssessmentResult,
    CategoryResult,
    _compute_overall_score,
    _extract_metadata,
    _extract_option_risk_weight,
    _map_score_to_risk_level,
    _score_category,
    score_responses,
)
from ai_gov_gen.questions import CATEGORIES, QUESTIONS, get_scored_questions


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_minimal_responses(
    framework_id: str = "enterprise",
    system_name: str = "Test AI",
    system_owner: str = "Test Team",
    system_purpose: str = "Test purpose.",
) -> dict[str, Any]:
    """Build a minimal response dict that answers all scored questions with
    the *lowest-risk* option for each question."""
    responses: dict[str, Any] = {
        "meta_01": system_name,
        "meta_02": system_owner,
        "meta_03": system_purpose,
        "meta_04": framework_id,
    }
    scored = get_scored_questions(framework_id=framework_id)
    for q in scored:
        if q["input_type"] in {"radio", "select"} and q["options"]:
            # Pick the option with the lowest risk_weight
            best_opt = min(q["options"], key=lambda o: o["risk_weight"])
            responses[q["id"]] = best_opt["value"]
        elif q["input_type"] == "checkbox" and q["options"]:
            # Select only the lowest-risk option
            best_opt = min(q["options"], key=lambda o: o["risk_weight"])
            responses[q["id"]] = [best_opt["value"]]
    return responses


def _make_worst_case_responses(
    framework_id: str = "enterprise",
) -> dict[str, Any]:
    """Build a response dict that always selects the highest-risk option."""
    responses: dict[str, Any] = {
        "meta_01": "Dangerous AI",
        "meta_02": "Reckless Team",
        "meta_03": "Maximally risky system.",
        "meta_04": framework_id,
    }
    scored = get_scored_questions(framework_id=framework_id)
    for q in scored:
        if q["input_type"] in {"radio", "select"} and q["options"]:
            worst_opt = max(q["options"], key=lambda o: o["risk_weight"])
            responses[q["id"]] = worst_opt["value"]
        elif q["input_type"] == "checkbox" and q["options"]:
            worst_opt = max(q["options"], key=lambda o: o["risk_weight"])
            responses[q["id"]] = [worst_opt["value"]]
    return responses


def _make_empty_responses() -> dict[str, Any]:
    """Build a response dict with no answers (triggers max risk everywhere)."""
    return {}


@pytest.fixture()
def minimal_result() -> AssessmentResult:
    """AssessmentResult from all-lowest-risk answers."""
    return score_responses(_make_minimal_responses())


@pytest.fixture()
def worst_case_result() -> AssessmentResult:
    """AssessmentResult from all-highest-risk answers."""
    return score_responses(_make_worst_case_responses())


@pytest.fixture()
def empty_result() -> AssessmentResult:
    """AssessmentResult from a completely empty response dict."""
    return score_responses(_make_empty_responses())


# ---------------------------------------------------------------------------
# RISK_LEVELS and RISK_THRESHOLDS constants
# ---------------------------------------------------------------------------


class TestRiskLevelConstants:
    """Verify the module-level constants are correctly defined."""

    def test_risk_levels_ordered(self) -> None:
        assert RISK_LEVELS == ["Low", "Medium", "High", "Critical"]

    def test_risk_thresholds_keys_match_levels(self) -> None:
        assert set(RISK_THRESHOLDS.keys()) == set(RISK_LEVELS)

    def test_risk_thresholds_ascending(self) -> None:
        values = [RISK_THRESHOLDS[lvl] for lvl in RISK_LEVELS]
        assert values == sorted(values)

    def test_low_threshold_is_zero(self) -> None:
        assert RISK_THRESHOLDS["Low"] == 0.0

    def test_critical_threshold_below_100(self) -> None:
        assert RISK_THRESHOLDS["Critical"] < 100.0


# ---------------------------------------------------------------------------
# _map_score_to_risk_level
# ---------------------------------------------------------------------------


class TestMapScoreToRiskLevel:
    """Boundary and parametric tests for _map_score_to_risk_level."""

    @pytest.mark.parametrize(
        "score, expected",
        [
            (0.0, "Low"),
            (24.9, "Low"),
            (25.0, "Medium"),
            (49.9, "Medium"),
            (50.0, "High"),
            (74.9, "High"),
            (75.0, "Critical"),
            (100.0, "Critical"),
        ],
    )
    def test_boundary_values(self, score: float, expected: str) -> None:
        assert _map_score_to_risk_level(score) == expected

    def test_negative_score_clamped_to_low(self) -> None:
        assert _map_score_to_risk_level(-10.0) == "Low"

    def test_score_above_100_clamped_to_critical(self) -> None:
        assert _map_score_to_risk_level(105.0) == "Critical"

    def test_returns_string(self) -> None:
        assert isinstance(_map_score_to_risk_level(50.0), str)

    def test_all_levels_reachable(self) -> None:
        """Every risk level should be reachable via some score."""
        reached = set()
        for score in [0.0, 25.0, 50.0, 75.0]:
            reached.add(_map_score_to_risk_level(score))
        assert reached == set(RISK_LEVELS)


# ---------------------------------------------------------------------------
# _extract_option_risk_weight
# ---------------------------------------------------------------------------


class TestExtractOptionRiskWeight:
    """Tests for option risk weight extraction across all input types."""

    def _radio_question(self) -> dict[str, Any]:
        return {
            "id": "test_radio",
            "input_type": "radio",
            "weight": 1.0,
            "options": [
                {"value": "yes", "label": "Yes", "risk_weight": 0},
                {"value": "partial", "label": "Partial", "risk_weight": 1},
                {"value": "no", "label": "No", "risk_weight": 3},
            ],
        }

    def _select_question(self) -> dict[str, Any]:
        return {
            "id": "test_select",
            "input_type": "select",
            "weight": 0.8,
            "options": [
                {"value": "low", "label": "Low", "risk_weight": 0},
                {"value": "high", "label": "High", "risk_weight": 3},
            ],
        }

    def _checkbox_question(self) -> dict[str, Any]:
        return {
            "id": "test_checkbox",
            "input_type": "checkbox",
            "weight": 0.9,
            "options": [
                {"value": "a", "label": "A", "risk_weight": 0},
                {"value": "b", "label": "B", "risk_weight": 1},
                {"value": "c", "label": "C", "risk_weight": 3},
            ],
        }

    # Radio tests
    def test_radio_known_answer_returns_correct_weight(self) -> None:
        q = self._radio_question()
        weight, answered = _extract_option_risk_weight(q, "yes")
        assert weight == 0
        assert answered is True

    def test_radio_high_risk_answer(self) -> None:
        q = self._radio_question()
        weight, answered = _extract_option_risk_weight(q, "no")
        assert weight == 3
        assert answered is True

    def test_radio_missing_answer_returns_max_and_unanswered(self) -> None:
        q = self._radio_question()
        weight, answered = _extract_option_risk_weight(q, None)
        assert weight == 3
        assert answered is False

    def test_radio_invalid_answer_returns_max_and_unanswered(self) -> None:
        q = self._radio_question()
        weight, answered = _extract_option_risk_weight(q, "not_a_valid_option")
        assert weight == 3
        assert answered is False

    def test_radio_empty_string_returns_max_and_unanswered(self) -> None:
        q = self._radio_question()
        weight, answered = _extract_option_risk_weight(q, "")
        assert weight == 3
        assert answered is False

    # Select tests
    def test_select_known_answer(self) -> None:
        q = self._select_question()
        weight, answered = _extract_option_risk_weight(q, "low")
        assert weight == 0
        assert answered is True

    def test_select_missing_answer(self) -> None:
        q = self._select_question()
        weight, answered = _extract_option_risk_weight(q, None)
        assert weight == 3
        assert answered is False

    # Checkbox tests
    def test_checkbox_single_low_risk_selection(self) -> None:
        q = self._checkbox_question()
        weight, answered = _extract_option_risk_weight(q, ["a"])
        assert weight == 0
        assert answered is True

    def test_checkbox_multiple_selections_returns_max(self) -> None:
        q = self._checkbox_question()
        weight, answered = _extract_option_risk_weight(q, ["a", "b", "c"])
        assert weight == 3
        assert answered is True

    def test_checkbox_single_high_risk_selection(self) -> None:
        q = self._checkbox_question()
        weight, answered = _extract_option_risk_weight(q, ["c"])
        assert weight == 3
        assert answered is True

    def test_checkbox_empty_list_returns_max_and_unanswered(self) -> None:
        q = self._checkbox_question()
        weight, answered = _extract_option_risk_weight(q, [])
        assert weight == 3
        assert answered is False

    def test_checkbox_invalid_values_treated_as_unanswered(self) -> None:
        q = self._checkbox_question()
        weight, answered = _extract_option_risk_weight(q, ["invalid_value"])
        assert weight == 3
        assert answered is False

    def test_checkbox_mix_valid_invalid_uses_valid_only(self) -> None:
        q = self._checkbox_question()
        # "a" is valid (weight=0), "bad" is invalid
        weight, answered = _extract_option_risk_weight(q, ["a", "bad"])
        assert weight == 0
        assert answered is True

    def test_checkbox_string_answer_treated_as_single_selection(self) -> None:
        q = self._checkbox_question()
        weight, answered = _extract_option_risk_weight(q, "b")
        assert weight == 1
        assert answered is True


# ---------------------------------------------------------------------------
# _compute_overall_score
# ---------------------------------------------------------------------------


class TestComputeOverallScore:
    """Tests for the weighted mean overall score computation."""

    def _make_cr(self, cat_id: str, score: float) -> CategoryResult:
        return CategoryResult(
            category_id=cat_id,
            category_label=cat_id.capitalize(),
            normalised_score=score,
            risk_level=_map_score_to_risk_level(score),
            raw_score=score,
            max_possible_score=100.0,
            answered_questions=5,
            total_questions=5,
        )

    def test_equal_weights_returns_mean(self) -> None:
        results = [
            self._make_cr("data", 20.0),
            self._make_cr("model", 60.0),
        ]
        assert _compute_overall_score(results) == 40.0

    def test_custom_weights_applied(self) -> None:
        results = [
            self._make_cr("data", 0.0),
            self._make_cr("model", 100.0),
        ]
        # data weight=1, model weight=3 → (0*1 + 100*3) / 4 = 75.0
        score = _compute_overall_score(
            results, category_weights={"data": 1.0, "model": 3.0}
        )
        assert score == 75.0

    def test_empty_list_returns_zero(self) -> None:
        assert _compute_overall_score([]) == 0.0

    def test_single_category_returns_its_score(self) -> None:
        results = [self._make_cr("data", 42.5)]
        assert _compute_overall_score(results) == 42.5

    def test_all_zero_scores_returns_zero(self) -> None:
        results = [
            self._make_cr("data", 0.0),
            self._make_cr("model", 0.0),
            self._make_cr("ops", 0.0),
            self._make_cr("compliance", 0.0),
        ]
        assert _compute_overall_score(results) == 0.0

    def test_all_max_scores_returns_100(self) -> None:
        results = [
            self._make_cr("data", 100.0),
            self._make_cr("model", 100.0),
            self._make_cr("ops", 100.0),
            self._make_cr("compliance", 100.0),
        ]
        assert _compute_overall_score(results) == 100.0

    def test_result_is_rounded_to_two_decimals(self) -> None:
        results = [
            self._make_cr("data", 33.333),
            self._make_cr("model", 66.667),
        ]
        score = _compute_overall_score(results)
        # Should be rounded to 2 decimal places
        assert score == round(score, 2)


# ---------------------------------------------------------------------------
# _extract_metadata
# ---------------------------------------------------------------------------


class TestExtractMetadata:
    """Tests for metadata extraction from the response dict."""

    def test_all_fields_present(self) -> None:
        responses = {
            "meta_01": "My AI System",
            "meta_02": "Engineering Team",
            "meta_03": "Automates document review.",
        }
        name, owner, purpose = _extract_metadata(responses)
        assert name == "My AI System"
        assert owner == "Engineering Team"
        assert purpose == "Automates document review."

    def test_missing_fields_return_placeholders(self) -> None:
        name, owner, purpose = _extract_metadata({})
        assert "Not Provided" in name or len(name) > 0
        assert "Not Provided" in owner or len(owner) > 0
        assert "Not Provided" in purpose or len(purpose) > 0

    def test_whitespace_only_treated_as_missing(self) -> None:
        responses = {"meta_01": "   ", "meta_02": "\t", "meta_03": "\n"}
        name, owner, purpose = _extract_metadata(responses)
        assert name != "   "
        assert owner != "\t"
        assert purpose != "\n"

    def test_values_are_stripped(self) -> None:
        responses = {
            "meta_01": "  AI System  ",
            "meta_02": "  Dev Team  ",
            "meta_03": "  A purpose.  ",
        }
        name, owner, purpose = _extract_metadata(responses)
        assert name == "AI System"
        assert owner == "Dev Team"
        assert purpose == "A purpose."


# ---------------------------------------------------------------------------
# CategoryResult
# ---------------------------------------------------------------------------


class TestCategoryResult:
    """Tests for CategoryResult dataclass properties and serialisation."""

    def _make_result(
        self,
        score: float = 50.0,
        answered: int = 8,
        total: int = 8,
    ) -> CategoryResult:
        return CategoryResult(
            category_id="data",
            category_label="Data Governance",
            normalised_score=score,
            risk_level=_map_score_to_risk_level(score),
            raw_score=score * 0.3,
            max_possible_score=100.0,
            answered_questions=answered,
            total_questions=total,
        )

    def test_completion_pct_full(self) -> None:
        cr = self._make_result(answered=8, total=8)
        assert cr.completion_pct == 100.0

    def test_completion_pct_partial(self) -> None:
        cr = self._make_result(answered=4, total=8)
        assert cr.completion_pct == 50.0

    def test_completion_pct_zero_total(self) -> None:
        cr = self._make_result(answered=0, total=0)
        assert cr.completion_pct == 100.0

    def test_risk_level_index_low(self) -> None:
        cr = self._make_result(score=10.0)
        assert cr.risk_level_index == 0

    def test_risk_level_index_medium(self) -> None:
        cr = self._make_result(score=30.0)
        assert cr.risk_level_index == 1

    def test_risk_level_index_high(self) -> None:
        cr = self._make_result(score=60.0)
        assert cr.risk_level_index == 2

    def test_risk_level_index_critical(self) -> None:
        cr = self._make_result(score=80.0)
        assert cr.risk_level_index == 3

    def test_to_dict_contains_required_keys(self) -> None:
        cr = self._make_result()
        d = cr.to_dict()
        required_keys = {
            "category_id",
            "category_label",
            "normalised_score",
            "risk_level",
            "raw_score",
            "max_possible_score",
            "answered_questions",
            "total_questions",
            "completion_pct",
            "risk_level_index",
            "question_details",
        }
        assert required_keys.issubset(set(d.keys()))

    def test_to_dict_values_match_attributes(self) -> None:
        cr = self._make_result(score=60.0)
        d = cr.to_dict()
        assert d["category_id"] == "data"
        assert d["normalised_score"] == 60.0
        assert d["risk_level"] == "High"


# ---------------------------------------------------------------------------
# AssessmentResult
# ---------------------------------------------------------------------------


class TestAssessmentResult:
    """Tests for AssessmentResult properties and serialisation."""

    def _make_cat_result(self, cat_id: str, score: float) -> CategoryResult:
        return CategoryResult(
            category_id=cat_id,
            category_label=cat_id.capitalize(),
            normalised_score=score,
            risk_level=_map_score_to_risk_level(score),
            raw_score=score,
            max_possible_score=100.0,
            answered_questions=5,
            total_questions=5,
        )

    def _make_result(
        self,
        scores: dict[str, float] | None = None,
        overall: float = 50.0,
    ) -> AssessmentResult:
        if scores is None:
            scores = {"data": 20.0, "model": 80.0, "ops": 50.0, "compliance": 30.0}
        cat_results = [self._make_cat_result(k, v) for k, v in scores.items()]
        return AssessmentResult(
            category_results=cat_results,
            overall_score=overall,
            overall_risk_level=_map_score_to_risk_level(overall),
            framework_id="enterprise",
            framework_label="Enterprise Generic",
            system_name="Test AI",
            system_owner="Test Team",
            system_purpose="Test purpose.",
            responses={},
            warnings=[],
        )

    def test_category_results_by_id_lookup(self) -> None:
        result = self._make_result()
        assert "data" in result.category_results_by_id
        assert "model" in result.category_results_by_id

    def test_highest_risk_category(self) -> None:
        result = self._make_result(scores={"data": 10.0, "model": 90.0})
        assert result.highest_risk_category is not None
        assert result.highest_risk_category.category_id == "model"

    def test_highest_risk_category_empty(self) -> None:
        result = AssessmentResult(
            category_results=[],
            overall_score=0.0,
            overall_risk_level="Low",
            framework_id="enterprise",
            framework_label="Enterprise Generic",
            system_name="",
            system_owner="",
            system_purpose="",
            responses={},
            warnings=[],
        )
        assert result.highest_risk_category is None

    def test_critical_categories(self) -> None:
        result = self._make_result(scores={"data": 80.0, "model": 20.0})
        critical = result.critical_categories
        assert len(critical) == 1
        assert critical[0].category_id == "data"

    def test_high_or_critical_categories(self) -> None:
        result = self._make_result(
            scores={"data": 80.0, "model": 55.0, "ops": 20.0, "compliance": 25.0}
        )
        hoc = result.high_or_critical_categories
        ids = {cr.category_id for cr in hoc}
        assert "data" in ids
        assert "model" in ids
        assert "ops" not in ids

    def test_overall_risk_level_index_low(self) -> None:
        result = self._make_result(overall=10.0)
        assert result.overall_risk_level_index == 0

    def test_overall_risk_level_index_critical(self) -> None:
        result = self._make_result(overall=90.0)
        assert result.overall_risk_level_index == 3

    def test_get_category_result_found(self) -> None:
        result = self._make_result()
        cr = result.get_category_result("data")
        assert cr is not None
        assert cr.category_id == "data"

    def test_get_category_result_not_found(self) -> None:
        result = self._make_result()
        assert result.get_category_result("nonexistent") is None

    def test_to_dict_contains_required_keys(self) -> None:
        result = self._make_result()
        d = result.to_dict()
        required = {
            "overall_score",
            "overall_risk_level",
            "overall_risk_level_index",
            "framework_id",
            "framework_label",
            "system_name",
            "system_owner",
            "system_purpose",
            "warnings",
            "category_results",
            "highest_risk_category",
            "critical_categories",
            "high_or_critical_categories",
        }
        assert required.issubset(set(d.keys()))

    def test_to_dict_category_results_is_list_of_dicts(self) -> None:
        result = self._make_result()
        d = result.to_dict()
        assert isinstance(d["category_results"], list)
        for item in d["category_results"]:
            assert isinstance(item, dict)


# ---------------------------------------------------------------------------
# score_responses — integration tests
# ---------------------------------------------------------------------------


class TestScoreResponses:
    """Integration tests for the primary score_responses entry point."""

    def test_returns_assessment_result(self, minimal_result: AssessmentResult) -> None:
        assert isinstance(minimal_result, AssessmentResult)

    def test_minimal_responses_produce_low_risk(self, minimal_result: AssessmentResult) -> None:
        """Answering all questions with lowest-risk options should produce Low or Medium overall."""
        assert minimal_result.overall_risk_level in {"Low", "Medium"}

    def test_worst_case_produces_critical_risk(self, worst_case_result: AssessmentResult) -> None:
        """Answering all questions with highest-risk options should produce Critical overall."""
        assert worst_case_result.overall_risk_level == "Critical"

    def test_empty_responses_produce_critical_risk(self, empty_result: AssessmentResult) -> None:
        """No answers means maximum risk for every question — should be Critical."""
        assert empty_result.overall_risk_level == "Critical"

    def test_overall_score_in_range(self, minimal_result: AssessmentResult) -> None:
        assert 0.0 <= minimal_result.overall_score <= 100.0

    def test_overall_score_in_range_worst(self, worst_case_result: AssessmentResult) -> None:
        assert 0.0 <= worst_case_result.overall_score <= 100.0

    def test_category_results_has_all_categories(self, minimal_result: AssessmentResult) -> None:
        expected_ids = {cat["id"] for cat in CATEGORIES}
        result_ids = {cr.category_id for cr in minimal_result.category_results}
        assert expected_ids == result_ids

    def test_category_scores_in_range(self, minimal_result: AssessmentResult) -> None:
        for cr in minimal_result.category_results:
            assert 0.0 <= cr.normalised_score <= 100.0, (
                f"Category '{cr.category_id}' score {cr.normalised_score} out of range"
            )

    def test_category_risk_levels_are_valid(self, minimal_result: AssessmentResult) -> None:
        for cr in minimal_result.category_results:
            assert cr.risk_level in RISK_LEVELS

    def test_overall_risk_level_is_valid(self, minimal_result: AssessmentResult) -> None:
        assert minimal_result.overall_risk_level in RISK_LEVELS

    def test_framework_id_stored(self, minimal_result: AssessmentResult) -> None:
        assert minimal_result.framework_id == "enterprise"

    def test_framework_label_stored(self, minimal_result: AssessmentResult) -> None:
        assert isinstance(minimal_result.framework_label, str)
        assert len(minimal_result.framework_label) > 0

    def test_system_name_stored(self, minimal_result: AssessmentResult) -> None:
        assert minimal_result.system_name == "Test AI"

    def test_system_owner_stored(self, minimal_result: AssessmentResult) -> None:
        assert minimal_result.system_owner == "Test Team"

    def test_system_purpose_stored(self, minimal_result: AssessmentResult) -> None:
        assert minimal_result.system_purpose == "Test purpose."

    def test_responses_stored(self, minimal_result: AssessmentResult) -> None:
        assert isinstance(minimal_result.responses, dict)

    def test_warnings_is_list(self, minimal_result: AssessmentResult) -> None:
        assert isinstance(minimal_result.warnings, list)

    def test_explicit_framework_id_overrides_meta04(self) -> None:
        responses = _make_minimal_responses(framework_id="enterprise")
        result = score_responses(responses, framework_id="nist_ai_rmf")
        assert result.framework_id == "nist_ai_rmf"

    def test_invalid_explicit_framework_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown framework"):
            score_responses({}, framework_id="bad_framework")

    def test_unrecognised_meta04_defaults_to_enterprise(self) -> None:
        responses = {"meta_04": "totally_unknown_fw"}
        result = score_responses(responses)
        assert result.framework_id == "enterprise"

    @pytest.mark.parametrize(
        "framework_id",
        ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
    )
    def test_all_frameworks_scoreable(self, framework_id: str) -> None:
        responses = _make_minimal_responses(framework_id=framework_id)
        result = score_responses(responses, framework_id=framework_id)
        assert result.framework_id == framework_id
        assert 0.0 <= result.overall_score <= 100.0

    def test_custom_category_weights_affect_score(self) -> None:
        """Heavily weighting one category should pull overall score toward it."""
        responses_low = _make_minimal_responses()   # all low risk
        responses_high = _make_worst_case_responses()  # all high risk

        # Create a mixed scenario: manually set data to low-risk, rest skipped
        mixed = {"meta_01": "AI", "meta_02": "Team", "meta_03": "Desc.", "meta_04": "enterprise"}
        data_qs = get_scored_questions(category_id="data", framework_id="enterprise")
        for q in data_qs:
            if q["input_type"] in {"radio", "select"} and q["options"]:
                best = min(q["options"], key=lambda o: o["risk_weight"])
                mixed[q["id"]] = best["value"]
            elif q["input_type"] == "checkbox" and q["options"]:
                best = min(q["options"], key=lambda o: o["risk_weight"])
                mixed[q["id"]] = [best["value"]]

        # Weight data heavily
        result_data_heavy = score_responses(
            mixed,
            category_weights={"data": 10.0, "model": 1.0, "ops": 1.0, "compliance": 1.0},
        )
        # Weight other categories heavily (data has low risk so this makes overall higher)
        result_other_heavy = score_responses(
            mixed,
            category_weights={"data": 1.0, "model": 10.0, "ops": 10.0, "compliance": 10.0},
        )
        # When data (low risk) is weighted heavily, overall should be lower
        assert result_data_heavy.overall_score < result_other_heavy.overall_score

    def test_answered_questions_count_correct(self) -> None:
        responses = _make_minimal_responses()
        result = score_responses(responses)
        for cr in result.category_results:
            assert cr.answered_questions <= cr.total_questions
            assert cr.answered_questions >= 0

    def test_question_details_populated(self, minimal_result: AssessmentResult) -> None:
        for cr in minimal_result.category_results:
            if cr.total_questions > 0:
                assert len(cr.question_details) == cr.total_questions

    def test_question_detail_has_expected_keys(self, minimal_result: AssessmentResult) -> None:
        required_keys = {
            "question_id",
            "text",
            "weight",
            "answer",
            "option_risk_weight",
            "answered",
            "raw_contribution",
            "max_contribution",
        }
        for cr in minimal_result.category_results:
            for detail in cr.question_details:
                missing = required_keys - set(detail.keys())
                assert not missing, (
                    f"Question detail in '{cr.category_id}' missing keys: {missing}"
                )

    def test_worst_case_all_categories_high_or_critical(self, worst_case_result: AssessmentResult) -> None:
        for cr in worst_case_result.category_results:
            assert cr.risk_level in {"High", "Critical"}, (
                f"Category '{cr.category_id}' expected High/Critical, got '{cr.risk_level}'"
            )

    def test_warnings_generated_for_missing_metadata(self) -> None:
        responses = {}  # No metadata
        result = score_responses(responses)
        assert len(result.warnings) > 0

    def test_no_warnings_for_complete_responses(self) -> None:
        responses = _make_minimal_responses()
        result = score_responses(responses)
        # Warnings about metadata should not be present
        metadata_warnings = [
            w for w in result.warnings
            if "meta_01" in w or "meta_02" in w or "meta_03" in w
        ]
        assert len(metadata_warnings) == 0

    def test_to_dict_is_json_serialisable(self, minimal_result: AssessmentResult) -> None:
        import json
        d = minimal_result.to_dict()
        # Should not raise
        serialised = json.dumps(d)
        assert isinstance(serialised, str)

    def test_score_consistency_idempotent(self) -> None:
        """Scoring the same responses twice should return identical scores."""
        responses = _make_minimal_responses()
        result1 = score_responses(responses)
        result2 = score_responses(responses)
        assert result1.overall_score == result2.overall_score
        for cr1, cr2 in zip(result1.category_results, result2.category_results):
            assert cr1.normalised_score == cr2.normalised_score

    def test_partial_responses_score_above_all_low(self) -> None:
        """Partially answered forms should score higher than fully low-risk answers."""
        minimal = score_responses(_make_minimal_responses())
        partial = score_responses({"meta_04": "enterprise"})  # Only meta, no scored answers
        # Unanswered = max risk, so partial should score higher
        assert partial.overall_score >= minimal.overall_score


# ---------------------------------------------------------------------------
# _score_category — unit tests
# ---------------------------------------------------------------------------


class TestScoreCategory:
    """Unit tests for the internal _score_category function."""

    def test_returns_category_result(self) -> None:
        qs = get_scored_questions(category_id="data", framework_id="enterprise")
        responses = _make_minimal_responses()
        result = _score_category("data", qs, responses)
        assert isinstance(result, CategoryResult)

    def test_category_id_set_correctly(self) -> None:
        qs = get_scored_questions(category_id="model", framework_id="enterprise")
        result = _score_category("model", qs, {})
        assert result.category_id == "model"

    def test_total_questions_matches_input(self) -> None:
        qs = get_scored_questions(category_id="ops", framework_id="enterprise")
        result = _score_category("ops", qs, {})
        assert result.total_questions == len(qs)

    def test_empty_question_list_gives_zero_score(self) -> None:
        result = _score_category("data", [], {})
        assert result.normalised_score == 0.0
        assert result.answered_questions == 0
        assert result.total_questions == 0

    def test_all_answered_low_risk_score_near_zero(self) -> None:
        qs = get_scored_questions(category_id="compliance", framework_id="enterprise")
        responses = _make_minimal_responses()
        result = _score_category("compliance", qs, responses)
        assert result.normalised_score < 50.0  # Should be Low or Medium

    def test_no_answers_score_is_100(self) -> None:
        qs = get_scored_questions(category_id="data", framework_id="enterprise")
        result = _score_category("data", qs, {})
        # All unanswered → all max risk → should be 100.0
        assert result.normalised_score == 100.0

    def test_question_details_count_matches_questions(self) -> None:
        qs = get_scored_questions(category_id="data", framework_id="enterprise")
        result = _score_category("data", qs, {})
        assert len(result.question_details) == len(qs)

    def test_max_possible_score_is_sum_of_3_times_weights(self) -> None:
        qs = get_scored_questions(category_id="data", framework_id="enterprise")
        expected_max = sum(3 * q["weight"] for q in qs)
        result = _score_category("data", qs, {})
        assert abs(result.max_possible_score - expected_max) < 1e-6
