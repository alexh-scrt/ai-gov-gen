"""Tests for the question bank defined in ai_gov_gen/questions.py.

Verifies structural integrity, data completeness, and helper function
behaviour for the question bank, category metadata, and framework metadata.
"""

from __future__ import annotations

from typing import Any

import pytest

from ai_gov_gen.questions import (
    CATEGORIES,
    CATEGORY_IDS,
    FRAMEWORK_BY_ID,
    FRAMEWORK_METADATA,
    QUESTION_BY_ID,
    QUESTIONS,
    QUESTIONS_BY_CATEGORY,
    get_category_metadata,
    get_framework_metadata,
    get_questions_for_category,
    get_questions_for_framework,
    get_scored_questions,
)


# ---------------------------------------------------------------------------
# Structural integrity tests for CATEGORIES
# ---------------------------------------------------------------------------


class TestCategories:
    """Tests for the CATEGORIES constant."""

    def test_categories_is_list(self) -> None:
        assert isinstance(CATEGORIES, list)

    def test_categories_not_empty(self) -> None:
        assert len(CATEGORIES) >= 4

    def test_each_category_has_required_keys(self) -> None:
        required_keys = {"id", "label", "description", "icon", "order"}
        for cat in CATEGORIES:
            missing = required_keys - set(cat.keys())
            assert not missing, f"Category {cat.get('id')} missing keys: {missing}"

    def test_expected_category_ids_present(self) -> None:
        ids = {cat["id"] for cat in CATEGORIES}
        assert "data" in ids
        assert "model" in ids
        assert "ops" in ids
        assert "compliance" in ids

    def test_category_ids_are_unique(self) -> None:
        ids = [cat["id"] for cat in CATEGORIES]
        assert len(ids) == len(set(ids))

    def test_category_order_values_present(self) -> None:
        for cat in CATEGORIES:
            assert isinstance(cat["order"], int)
            assert cat["order"] >= 1


# ---------------------------------------------------------------------------
# Structural integrity tests for FRAMEWORK_METADATA
# ---------------------------------------------------------------------------


class TestFrameworkMetadata:
    """Tests for the FRAMEWORK_METADATA constant."""

    def test_framework_metadata_is_list(self) -> None:
        assert isinstance(FRAMEWORK_METADATA, list)

    def test_framework_metadata_not_empty(self) -> None:
        assert len(FRAMEWORK_METADATA) >= 5

    def test_expected_frameworks_present(self) -> None:
        ids = {fw["id"] for fw in FRAMEWORK_METADATA}
        expected = {"nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"}
        assert expected.issubset(ids)

    def test_each_framework_has_required_keys(self) -> None:
        required_keys = {"id", "label", "full_name", "description", "version", "contexts"}
        for fw in FRAMEWORK_METADATA:
            missing = required_keys - set(fw.keys())
            assert not missing, f"Framework {fw.get('id')} missing keys: {missing}"

    def test_framework_ids_are_unique(self) -> None:
        ids = [fw["id"] for fw in FRAMEWORK_METADATA]
        assert len(ids) == len(set(ids))

    def test_framework_by_id_lookup(self) -> None:
        for fw in FRAMEWORK_METADATA:
            assert fw["id"] in FRAMEWORK_BY_ID
            assert FRAMEWORK_BY_ID[fw["id"]] is fw

    def test_contexts_is_non_empty_list(self) -> None:
        for fw in FRAMEWORK_METADATA:
            assert isinstance(fw["contexts"], list)
            assert len(fw["contexts"]) >= 1


# ---------------------------------------------------------------------------
# Structural integrity tests for QUESTIONS
# ---------------------------------------------------------------------------


class TestQuestionsStructure:
    """Tests for the master QUESTIONS list."""

    REQUIRED_KEYS = {
        "id",
        "category",
        "text",
        "help_text",
        "input_type",
        "options",
        "required",
        "frameworks",
        "nist_function",
        "hks_dimension",
        "weight",
    }

    VALID_INPUT_TYPES = {"radio", "checkbox", "text", "select", "textarea"}
    VALID_NIST_FUNCTIONS = {"GOVERN", "MAP", "MEASURE", "MANAGE"}
    VALID_CATEGORIES = {"data", "model", "ops", "compliance"}
    VALID_FRAMEWORK_IDS = {"nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"}

    def test_questions_is_list(self) -> None:
        assert isinstance(QUESTIONS, list)

    def test_questions_not_empty(self) -> None:
        assert len(QUESTIONS) >= 20

    def test_each_question_has_required_keys(self) -> None:
        for q in QUESTIONS:
            missing = self.REQUIRED_KEYS - set(q.keys())
            assert not missing, f"Question {q.get('id')} missing keys: {missing}"

    def test_question_ids_are_unique(self) -> None:
        ids = [q["id"] for q in QUESTIONS]
        assert len(ids) == len(set(ids)), "Duplicate question IDs detected"

    def test_input_types_are_valid(self) -> None:
        for q in QUESTIONS:
            assert q["input_type"] in self.VALID_INPUT_TYPES, (
                f"Question {q['id']} has invalid input_type '{q['input_type']}'"
            )

    def test_nist_functions_are_valid(self) -> None:
        for q in QUESTIONS:
            assert q["nist_function"] in self.VALID_NIST_FUNCTIONS, (
                f"Question {q['id']} has invalid nist_function '{q['nist_function']}'"
            )

    def test_categories_are_valid(self) -> None:
        for q in QUESTIONS:
            assert q["category"] in self.VALID_CATEGORIES, (
                f"Question {q['id']} has invalid category '{q['category']}'"
            )

    def test_frameworks_reference_valid_ids(self) -> None:
        for q in QUESTIONS:
            for fw_id in q["frameworks"]:
                assert fw_id in self.VALID_FRAMEWORK_IDS, (
                    f"Question {q['id']} references unknown framework '{fw_id}'"
                )

    def test_frameworks_is_non_empty_list(self) -> None:
        for q in QUESTIONS:
            assert isinstance(q["frameworks"], list)
            assert len(q["frameworks"]) >= 1, (
                f"Question {q['id']} has empty frameworks list"
            )

    def test_weight_is_float_in_valid_range(self) -> None:
        for q in QUESTIONS:
            assert isinstance(q["weight"], (int, float)), (
                f"Question {q['id']} weight is not numeric"
            )
            assert 0.0 <= q["weight"] <= 1.0, (
                f"Question {q['id']} weight {q['weight']} out of range [0.0, 1.0]"
            )

    def test_required_is_boolean(self) -> None:
        for q in QUESTIONS:
            assert isinstance(q["required"], bool), (
                f"Question {q['id']} 'required' field is not bool"
            )

    def test_options_is_list(self) -> None:
        for q in QUESTIONS:
            assert isinstance(q["options"], list), (
                f"Question {q['id']} 'options' is not a list"
            )

    def test_radio_and_select_have_options(self) -> None:
        for q in QUESTIONS:
            if q["input_type"] in {"radio", "select"}:
                assert len(q["options"]) >= 2, (
                    f"Question {q['id']} is radio/select but has fewer than 2 options"
                )

    def test_checkbox_has_options(self) -> None:
        for q in QUESTIONS:
            if q["input_type"] == "checkbox":
                assert len(q["options"]) >= 2, (
                    f"Checkbox question {q['id']} has fewer than 2 options"
                )

    def test_text_and_textarea_have_empty_options(self) -> None:
        for q in QUESTIONS:
            if q["input_type"] in {"text", "textarea"}:
                assert q["options"] == [], (
                    f"Question {q['id']} is text/textarea but has non-empty options"
                )

    def test_option_keys_are_correct(self) -> None:
        required_option_keys = {"value", "label", "risk_weight"}
        for q in QUESTIONS:
            for opt in q["options"]:
                missing = required_option_keys - set(opt.keys())
                assert not missing, (
                    f"Option in question {q['id']} missing keys: {missing}"
                )

    def test_option_risk_weights_are_valid(self) -> None:
        for q in QUESTIONS:
            for opt in q["options"]:
                assert isinstance(opt["risk_weight"], int), (
                    f"risk_weight in option '{opt['value']}' of question {q['id']} "
                    f"is not int"
                )
                assert 0 <= opt["risk_weight"] <= 3, (
                    f"risk_weight {opt['risk_weight']} in question {q['id']} out of "
                    f"range [0, 3]"
                )

    def test_question_texts_are_non_empty_strings(self) -> None:
        for q in QUESTIONS:
            assert isinstance(q["text"], str) and len(q["text"].strip()) > 0, (
                f"Question {q['id']} has empty or non-string 'text'"
            )

    def test_help_texts_are_strings(self) -> None:
        for q in QUESTIONS:
            assert isinstance(q["help_text"], str), (
                f"Question {q['id']} 'help_text' is not a string"
            )


# ---------------------------------------------------------------------------
# Tests for QUESTIONS_BY_CATEGORY
# ---------------------------------------------------------------------------


class TestQuestionsByCategory:
    """Tests for the QUESTIONS_BY_CATEGORY derived structure."""

    def test_all_categories_present(self) -> None:
        for cat in CATEGORIES:
            assert cat["id"] in QUESTIONS_BY_CATEGORY

    def test_no_question_lost_in_grouping(self) -> None:
        total = sum(len(qs) for qs in QUESTIONS_BY_CATEGORY.values())
        assert total == len(QUESTIONS)

    def test_each_category_has_questions(self) -> None:
        for cat_id, qs in QUESTIONS_BY_CATEGORY.items():
            assert len(qs) >= 1, f"Category '{cat_id}' has no questions"

    def test_questions_belong_to_correct_category(self) -> None:
        for cat_id, qs in QUESTIONS_BY_CATEGORY.items():
            for q in qs:
                assert q["category"] == cat_id


# ---------------------------------------------------------------------------
# Tests for QUESTION_BY_ID
# ---------------------------------------------------------------------------


class TestQuestionById:
    """Tests for the QUESTION_BY_ID lookup dict."""

    def test_lookup_contains_all_questions(self) -> None:
        assert len(QUESTION_BY_ID) == len(QUESTIONS)

    def test_lookup_returns_correct_question(self) -> None:
        for q in QUESTIONS:
            assert QUESTION_BY_ID[q["id"]] is q


# ---------------------------------------------------------------------------
# Tests for CATEGORY_IDS
# ---------------------------------------------------------------------------


class TestCategoryIds:
    """Tests for the CATEGORY_IDS convenience list."""

    def test_category_ids_matches_categories(self) -> None:
        assert set(CATEGORY_IDS) == {cat["id"] for cat in CATEGORIES}

    def test_category_ids_length(self) -> None:
        assert len(CATEGORY_IDS) == len(CATEGORIES)


# ---------------------------------------------------------------------------
# Tests for helper functions
# ---------------------------------------------------------------------------


class TestGetQuestionsForFramework:
    """Tests for get_questions_for_framework()."""

    @pytest.mark.parametrize(
        "framework_id",
        ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
    )
    def test_returns_list_for_valid_framework(self, framework_id: str) -> None:
        result = get_questions_for_framework(framework_id)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_all_returned_questions_include_framework(self) -> None:
        fw = "cmmc_l2"
        for q in get_questions_for_framework(fw):
            assert fw in q["frameworks"]

    def test_invalid_framework_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown framework"):
            get_questions_for_framework("unknown_framework")

    def test_exclude_meta_questions(self) -> None:
        scored = get_questions_for_framework("enterprise", include_meta=False)
        for q in scored:
            assert q["weight"] > 0.0

    def test_include_meta_questions_by_default(self) -> None:
        all_qs = get_questions_for_framework("enterprise", include_meta=True)
        meta_qs = [q for q in all_qs if q["weight"] == 0.0]
        assert len(meta_qs) >= 1


class TestGetQuestionsForCategory:
    """Tests for get_questions_for_category()."""

    @pytest.mark.parametrize(
        "category_id",
        ["data", "model", "ops", "compliance"],
    )
    def test_returns_list_for_valid_category(self, category_id: str) -> None:
        result = get_questions_for_category(category_id)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_all_returned_questions_have_correct_category(self) -> None:
        for q in get_questions_for_category("model"):
            assert q["category"] == "model"

    def test_invalid_category_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown category"):
            get_questions_for_category("invalid_cat")

    def test_framework_filter_works(self) -> None:
        fw = "cmmc_l2"
        qs = get_questions_for_category("ops", framework_id=fw)
        for q in qs:
            assert fw in q["frameworks"]

    def test_invalid_framework_in_category_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown framework"):
            get_questions_for_category("data", framework_id="bad_fw")


class TestGetScoredQuestions:
    """Tests for get_scored_questions()."""

    def test_returns_list(self) -> None:
        assert isinstance(get_scored_questions(), list)

    def test_no_zero_weight_questions_in_result(self) -> None:
        for q in get_scored_questions():
            assert q["weight"] > 0.0

    def test_category_filter(self) -> None:
        qs = get_scored_questions(category_id="data")
        for q in qs:
            assert q["category"] == "data"
            assert q["weight"] > 0.0

    def test_framework_filter(self) -> None:
        fw = "lloyds"
        qs = get_scored_questions(framework_id=fw)
        for q in qs:
            assert fw in q["frameworks"]
            assert q["weight"] > 0.0

    def test_combined_filters(self) -> None:
        qs = get_scored_questions(category_id="compliance", framework_id="nist_ai_rmf")
        for q in qs:
            assert q["category"] == "compliance"
            assert "nist_ai_rmf" in q["frameworks"]
            assert q["weight"] > 0.0

    def test_invalid_category_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown category"):
            get_scored_questions(category_id="bad_category")

    def test_invalid_framework_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown framework"):
            get_scored_questions(framework_id="bad_framework")


class TestGetCategoryMetadata:
    """Tests for get_category_metadata()."""

    @pytest.mark.parametrize(
        "category_id",
        ["data", "model", "ops", "compliance"],
    )
    def test_returns_dict_for_valid_id(self, category_id: str) -> None:
        meta = get_category_metadata(category_id)
        assert isinstance(meta, dict)
        assert meta["id"] == category_id

    def test_invalid_category_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown category"):
            get_category_metadata("nonexistent")


class TestGetFrameworkMetadata:
    """Tests for get_framework_metadata()."""

    @pytest.mark.parametrize(
        "framework_id",
        ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
    )
    def test_returns_dict_for_valid_id(self, framework_id: str) -> None:
        meta = get_framework_metadata(framework_id)
        assert isinstance(meta, dict)
        assert meta["id"] == framework_id

    def test_invalid_framework_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown framework"):
            get_framework_metadata("no_such_framework")


# ---------------------------------------------------------------------------
# Content coverage tests
# ---------------------------------------------------------------------------


class TestQuestionBankCoverage:
    """Verify that the question bank meets minimum coverage requirements."""

    def test_data_category_has_enough_questions(self) -> None:
        qs = QUESTIONS_BY_CATEGORY["data"]
        assert len(qs) >= 6

    def test_model_category_has_enough_questions(self) -> None:
        qs = QUESTIONS_BY_CATEGORY["model"]
        assert len(qs) >= 6

    def test_ops_category_has_enough_questions(self) -> None:
        qs = QUESTIONS_BY_CATEGORY["ops"]
        assert len(qs) >= 6

    def test_compliance_category_has_enough_questions(self) -> None:
        qs = QUESTIONS_BY_CATEGORY["compliance"]
        assert len(qs) >= 6

    def test_all_nist_functions_represented(self) -> None:
        functions_used = {q["nist_function"] for q in QUESTIONS}
        expected = {"GOVERN", "MAP", "MEASURE", "MANAGE"}
        assert expected.issubset(functions_used)

    def test_high_risk_options_exist(self) -> None:
        """At least some questions should have max-risk-weight options."""
        has_max_risk = any(
            any(opt["risk_weight"] == 3 for opt in q["options"])
            for q in QUESTIONS
            if q["options"]
        )
        assert has_max_risk

    def test_zero_risk_options_exist(self) -> None:
        """At least some questions should have zero-risk options."""
        has_zero_risk = any(
            any(opt["risk_weight"] == 0 for opt in q["options"])
            for q in QUESTIONS
            if q["options"]
        )
        assert has_zero_risk

    def test_metadata_questions_exist(self) -> None:
        """Meta questions for system name, owner, and purpose should exist."""
        meta_ids = {"meta_01", "meta_02", "meta_03", "meta_04"}
        present_ids = {q["id"] for q in QUESTIONS}
        assert meta_ids.issubset(present_ids)

    def test_all_five_frameworks_covered_in_questions(self) -> None:
        """Each supported framework should appear in at least one question."""
        all_fw_ids: set[str] = set()
        for q in QUESTIONS:
            all_fw_ids.update(q["frameworks"])
        expected = {"nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"}
        assert expected.issubset(all_fw_ids)
