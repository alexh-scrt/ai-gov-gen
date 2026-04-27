"""Unit tests for the document generation engine in ai_gov_gen/generator.py.

Verifies that generator.py produces correct, well-formed document sections,
checklist items, SSP entries, and policy documents given mock assessment
results.  All tests run without a Flask application context except those
explicitly testing render_policy_html.

Covers:
* :func:`generate_checklist` — structure, content, and risk-level assignment
* :func:`generate_ssp_entries` — control entry population and status mapping
* :func:`generate_policy_document` — section rendering and metadata population
* :func:`generate_all` — convenience bundle function
* :class:`GovernanceChecklist` — properties and serialisation
* :class:`ChecklistCategory` — properties
* :class:`ChecklistItem` — field correctness
* :class:`SSPEntry` — field correctness and serialisation
* :class:`PolicyDocument` — full_text property and serialisation
* :class:`PolicySection` — serialisation
* :class:`GeneratedArtifacts` — to_dict
* render_policy_html — requires Flask context (tested separately)
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from ai_gov_gen.assessor import AssessmentResult, CategoryResult, _map_score_to_risk_level
from ai_gov_gen.generator import (
    RISK_LEVEL_BADGE_CLASS,
    RISK_LEVEL_PRIORITY,
    ChecklistCategory,
    ChecklistItem,
    GeneratedArtifacts,
    GovernanceChecklist,
    PolicyDocument,
    PolicySection,
    SSPEntry,
    _determine_implementation_status_and_finding,
    _determine_remediation_action,
    _select_checklist_items,
    generate_all,
    generate_checklist,
    generate_policy_document,
    generate_ssp_entries,
    render_policy_html,
)
from ai_gov_gen.questions import CATEGORIES


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_category_result(
    cat_id: str,
    score: float = 50.0,
    answered: int = 5,
    total: int = 5,
) -> CategoryResult:
    """Create a minimal CategoryResult for testing."""
    labels = {
        "data": "Data Governance",
        "model": "Model Risk",
        "ops": "Operational Security",
        "compliance": "Compliance & Audit",
    }
    return CategoryResult(
        category_id=cat_id,
        category_label=labels.get(cat_id, cat_id.capitalize()),
        normalised_score=score,
        risk_level=_map_score_to_risk_level(score),
        raw_score=score * 0.3,
        max_possible_score=100.0,
        answered_questions=answered,
        total_questions=total,
        question_details=[],
    )


def _make_assessment(
    system_name: str = "Test AI System",
    system_owner: str = "Engineering Team",
    system_purpose: str = "Automates internal document review processes.",
    framework_id: str = "enterprise",
    overall_score: float = 40.0,
    scores: dict[str, float] | None = None,
    responses: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> AssessmentResult:
    """Build a mock AssessmentResult for testing."""
    if scores is None:
        scores = {"data": 30.0, "model": 60.0, "ops": 45.0, "compliance": 25.0}

    category_results = [
        _make_category_result(cat_id, score)
        for cat_id, score in scores.items()
    ]

    # Ensure all four categories are present
    present_ids = {cr.category_id for cr in category_results}
    for cat in CATEGORIES:
        if cat["id"] not in present_ids:
            category_results.append(_make_category_result(cat["id"], 0.0))

    if responses is None:
        responses = {
            "meta_01": system_name,
            "meta_02": system_owner,
            "meta_03": system_purpose,
            "meta_04": framework_id,
            # Provide some scored question answers
            "data_02": "yes_manual",
            "data_03": "yes_documented",
            "data_04": ["schema_validation", "completeness"],
            "data_05": "both",
            "data_06": "yes_enforced",
            "data_07": "yes_equivalent",
            "data_08": "yes_completed",
            "data_01": ["pii"],
            "model_01": "custom_internal",
            "model_02": "low_stakes",
            "model_03": "comprehensive",
            "model_04": "xai_tooling",
            "model_05": "independent",
            "model_06": "full_registry",
            "model_07": "comprehensive",
            "model_08": "mandatory",
            "ops_01": "private_cloud",
            "ops_02": "comprehensive",
            "ops_03": "all_users",
            "ops_04": ["performance_metrics", "data_drift", "security_alerts", "audit_logs"],
            "ops_05": "ai_specific",
            "ops_06": "tested_automated",
            "ops_07": ["sbom", "dependency_scan", "pin_versions", "model_hash"],
            "ops_08": "formal_gated",
            "comp_01": ["nist_ai_rmf", "enterprise"],
            "comp_02": "dedicated_committee",
            "comp_03": "published_signed",
            "comp_04": "full_vrm",
            "comp_05": "operational_process",
            "comp_06": "external_internal",
            "comp_07": "role_specific",
            "comp_08": "fully_documented",
        }

    framework_labels = {
        "nist_ai_rmf": "NIST AI RMF",
        "hks": "HKS AI Risk Framework",
        "cmmc_l2": "CMMC Level 2",
        "lloyds": "Lloyd's Market AI Guidelines",
        "enterprise": "Enterprise Generic",
    }

    return AssessmentResult(
        category_results=category_results,
        overall_score=overall_score,
        overall_risk_level=_map_score_to_risk_level(overall_score),
        framework_id=framework_id,
        framework_label=framework_labels.get(framework_id, framework_id),
        system_name=system_name,
        system_owner=system_owner,
        system_purpose=system_purpose,
        responses=responses,
        warnings=warnings or [],
    )


@pytest.fixture()
def assessment() -> AssessmentResult:
    """Standard mock assessment for most tests."""
    return _make_assessment()


@pytest.fixture()
def high_risk_assessment() -> AssessmentResult:
    """Assessment with all-high scores to test critical-path logic."""
    responses = {
        "meta_01": "Risky AI",
        "meta_02": "Risk Team",
        "meta_03": "High risk system.",
        "meta_04": "enterprise",
        "data_02": "no",
        "data_03": "no",
        "data_04": ["none"],
        "data_05": "neither",
        "data_06": "no",
        "data_07": "no",
        "data_08": "no",
        "data_01": ["phi", "cui", "biometric"],
        "model_01": "saas_api",
        "model_02": "safety_critical",
        "model_03": "no",
        "model_04": "no",
        "model_05": "no",
        "model_06": "no",
        "model_07": "no",
        "model_08": "no",
        "ops_01": "saas_vendor",
        "ops_02": "no",
        "ops_03": "no",
        "ops_04": ["none"],
        "ops_05": "no",
        "ops_06": "no",
        "ops_07": ["none"],
        "ops_08": "no",
        "comp_01": ["none_known"],
        "comp_02": "no",
        "comp_03": "no",
        "comp_04": "no",
        "comp_05": "no",
        "comp_06": "no",
        "comp_07": "no",
        "comp_08": "no_ssp",
    }
    return _make_assessment(
        system_name="Risky AI",
        system_owner="Risk Team",
        system_purpose="High risk system.",
        overall_score=90.0,
        scores={"data": 90.0, "model": 95.0, "ops": 88.0, "compliance": 85.0},
        responses=responses,
    )


@pytest.fixture()
def checklist(assessment: AssessmentResult) -> GovernanceChecklist:
    """Generated checklist from standard assessment."""
    return generate_checklist(assessment)


@pytest.fixture()
def ssp_entries(assessment: AssessmentResult) -> list[SSPEntry]:
    """Generated SSP entries from standard assessment."""
    return generate_ssp_entries(assessment)


@pytest.fixture()
def policy_doc(assessment: AssessmentResult) -> PolicyDocument:
    """Generated policy document from standard assessment."""
    return generate_policy_document(assessment)


@pytest.fixture()
def artifacts(assessment: AssessmentResult) -> GeneratedArtifacts:
    """All generated artifacts from standard assessment."""
    return generate_all(assessment)


# ---------------------------------------------------------------------------
# Constants tests
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for module-level constants."""

    def test_risk_level_badge_class_has_all_levels(self) -> None:
        for level in ["Low", "Medium", "High", "Critical"]:
            assert level in RISK_LEVEL_BADGE_CLASS

    def test_risk_level_badge_class_values_are_strings(self) -> None:
        for val in RISK_LEVEL_BADGE_CLASS.values():
            assert isinstance(val, str) and len(val) > 0

    def test_risk_level_priority_has_all_levels(self) -> None:
        for level in ["Low", "Medium", "High", "Critical"]:
            assert level in RISK_LEVEL_PRIORITY

    def test_risk_level_priority_values_are_strings(self) -> None:
        for val in RISK_LEVEL_PRIORITY.values():
            assert isinstance(val, str) and len(val) > 0


# ---------------------------------------------------------------------------
# ChecklistItem tests
# ---------------------------------------------------------------------------


class TestChecklistItem:
    """Tests for the ChecklistItem dataclass."""

    def _make_item(self, risk_level: str = "Medium") -> ChecklistItem:
        return ChecklistItem(
            item_id="data-1",
            category_id="data",
            category_label="Data Governance",
            control_ref="NIST-AI-MAP-1.1",
            action="Establish data provenance records.",
            rationale="NIST AI RMF MAP 1.1 requirement.",
            risk_level=risk_level,
            priority=RISK_LEVEL_PRIORITY.get(risk_level, risk_level),
            badge_class=RISK_LEVEL_BADGE_CLASS.get(risk_level, "secondary"),
            frameworks=["nist_ai_rmf", "enterprise"],
            completed=False,
        )

    def test_to_dict_returns_dict(self) -> None:
        item = self._make_item()
        assert isinstance(item.to_dict(), dict)

    def test_to_dict_contains_all_keys(self) -> None:
        item = self._make_item()
        d = item.to_dict()
        required_keys = {
            "item_id", "category_id", "category_label", "control_ref",
            "action", "rationale", "risk_level", "priority", "badge_class",
            "frameworks", "completed",
        }
        assert required_keys.issubset(set(d.keys()))

    def test_to_dict_values_match_attributes(self) -> None:
        item = self._make_item(risk_level="High")
        d = item.to_dict()
        assert d["item_id"] == "data-1"
        assert d["risk_level"] == "High"
        assert d["completed"] is False

    def test_completed_default_false(self) -> None:
        item = self._make_item()
        assert item.completed is False

    def test_frameworks_stored_as_list(self) -> None:
        item = self._make_item()
        assert isinstance(item.frameworks, list)


# ---------------------------------------------------------------------------
# ChecklistCategory tests
# ---------------------------------------------------------------------------


class TestChecklistCategory:
    """Tests for the ChecklistCategory dataclass."""

    def _make_item(self, risk_level: str = "High") -> ChecklistItem:
        return ChecklistItem(
            item_id="data-1",
            category_id="data",
            category_label="Data Governance",
            control_ref="REF-001",
            action="Do something.",
            rationale="Because compliance.",
            risk_level=risk_level,
            priority=RISK_LEVEL_PRIORITY[risk_level],
            badge_class=RISK_LEVEL_BADGE_CLASS[risk_level],
            frameworks=["enterprise"],
        )

    def _make_category(self, items: list[ChecklistItem] | None = None) -> ChecklistCategory:
        return ChecklistCategory(
            category_id="data",
            category_label="Data Governance",
            risk_level="High",
            normalised_score=60.0,
            items=items or [],
        )

    def test_item_count_empty(self) -> None:
        cat = self._make_category()
        assert cat.item_count == 0

    def test_item_count_with_items(self) -> None:
        items = [self._make_item("High"), self._make_item("Medium")]
        cat = self._make_category(items)
        assert cat.item_count == 2

    def test_critical_item_count_none(self) -> None:
        items = [self._make_item("High"), self._make_item("Medium")]
        cat = self._make_category(items)
        assert cat.critical_item_count == 0

    def test_critical_item_count_some(self) -> None:
        items = [
            self._make_item("Critical"),
            self._make_item("Critical"),
            self._make_item("High"),
        ]
        cat = self._make_category(items)
        assert cat.critical_item_count == 2

    def test_to_dict_returns_dict(self) -> None:
        cat = self._make_category()
        assert isinstance(cat.to_dict(), dict)

    def test_to_dict_contains_required_keys(self) -> None:
        cat = self._make_category()
        d = cat.to_dict()
        required = {
            "category_id", "category_label", "risk_level",
            "normalised_score", "item_count", "critical_item_count", "items",
        }
        assert required.issubset(set(d.keys()))

    def test_to_dict_items_is_list_of_dicts(self) -> None:
        items = [self._make_item("High")]
        cat = self._make_category(items)
        d = cat.to_dict()
        assert isinstance(d["items"], list)
        assert all(isinstance(i, dict) for i in d["items"])


# ---------------------------------------------------------------------------
# GovernanceChecklist tests
# ---------------------------------------------------------------------------


class TestGovernanceChecklist:
    """Tests for the GovernanceChecklist dataclass."""

    def _make_checklist(
        self,
        categories: list[ChecklistCategory] | None = None,
    ) -> GovernanceChecklist:
        return GovernanceChecklist(
            system_name="Test AI",
            system_owner="Test Team",
            framework_id="enterprise",
            framework_label="Enterprise Generic",
            overall_risk_level="Medium",
            overall_score=40.0,
            generated_date=date.today().isoformat(),
            categories=categories or [],
            warnings=[],
        )

    def test_total_items_empty(self) -> None:
        cl = self._make_checklist()
        assert cl.total_items == 0

    def test_total_items_with_categories(self) -> None:
        items = [
            ChecklistItem(
                item_id=f"data-{i}",
                category_id="data",
                category_label="Data Governance",
                control_ref="REF",
                action="Act.",
                rationale="Rationale.",
                risk_level="Medium",
                priority=RISK_LEVEL_PRIORITY["Medium"],
                badge_class=RISK_LEVEL_BADGE_CLASS["Medium"],
                frameworks=["enterprise"],
            )
            for i in range(3)
        ]
        cat = ChecklistCategory(
            category_id="data",
            category_label="Data Governance",
            risk_level="Medium",
            normalised_score=40.0,
            items=items,
        )
        cl = self._make_checklist([cat])
        assert cl.total_items == 3

    def test_total_critical_items(self) -> None:
        items = [
            ChecklistItem(
                item_id=f"data-{i}",
                category_id="data",
                category_label="Data Governance",
                control_ref="REF",
                action="Act.",
                rationale="Rationale.",
                risk_level="Critical" if i < 2 else "Medium",
                priority=RISK_LEVEL_PRIORITY["Critical" if i < 2 else "Medium"],
                badge_class=RISK_LEVEL_BADGE_CLASS["Critical" if i < 2 else "Medium"],
                frameworks=["enterprise"],
            )
            for i in range(4)
        ]
        cat = ChecklistCategory(
            category_id="data",
            category_label="Data Governance",
            risk_level="Critical",
            normalised_score=80.0,
            items=items,
        )
        cl = self._make_checklist([cat])
        assert cl.total_critical_items == 2

    def test_all_items_flat_list(self) -> None:
        items_a = [
            ChecklistItem(
                item_id="data-1",
                category_id="data",
                category_label="Data Governance",
                control_ref="REF",
                action="Act.",
                rationale="Rationale.",
                risk_level="Medium",
                priority=RISK_LEVEL_PRIORITY["Medium"],
                badge_class=RISK_LEVEL_BADGE_CLASS["Medium"],
                frameworks=["enterprise"],
            )
        ]
        items_b = [
            ChecklistItem(
                item_id="model-1",
                category_id="model",
                category_label="Model Risk",
                control_ref="REF",
                action="Act.",
                rationale="Rationale.",
                risk_level="High",
                priority=RISK_LEVEL_PRIORITY["High"],
                badge_class=RISK_LEVEL_BADGE_CLASS["High"],
                frameworks=["enterprise"],
            )
        ]
        cat_a = ChecklistCategory(
            category_id="data",
            category_label="Data Governance",
            risk_level="Medium",
            normalised_score=40.0,
            items=items_a,
        )
        cat_b = ChecklistCategory(
            category_id="model",
            category_label="Model Risk",
            risk_level="High",
            normalised_score=60.0,
            items=items_b,
        )
        cl = self._make_checklist([cat_a, cat_b])
        assert len(cl.all_items) == 2

    def test_to_dict_contains_required_keys(self) -> None:
        cl = self._make_checklist()
        d = cl.to_dict()
        required = {
            "system_name", "system_owner", "framework_id", "framework_label",
            "overall_risk_level", "overall_score", "generated_date",
            "total_items", "total_critical_items", "warnings", "categories",
        }
        assert required.issubset(set(d.keys()))

    def test_to_dict_categories_is_list(self) -> None:
        cl = self._make_checklist()
        d = cl.to_dict()
        assert isinstance(d["categories"], list)


# ---------------------------------------------------------------------------
# generate_checklist tests
# ---------------------------------------------------------------------------


class TestGenerateChecklist:
    """Integration tests for generate_checklist()."""

    def test_returns_governance_checklist(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        assert isinstance(result, GovernanceChecklist)

    def test_system_name_matches(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        assert result.system_name == assessment.system_name

    def test_system_owner_matches(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        assert result.system_owner == assessment.system_owner

    def test_framework_id_matches(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        assert result.framework_id == assessment.framework_id

    def test_overall_risk_level_matches(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        assert result.overall_risk_level == assessment.overall_risk_level

    def test_overall_score_matches(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        assert result.overall_score == assessment.overall_score

    def test_generated_date_is_today(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        assert result.generated_date == date.today().isoformat()

    def test_has_all_four_categories(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        category_ids = {cat.category_id for cat in result.categories}
        expected = {"data", "model", "ops", "compliance"}
        assert expected == category_ids

    def test_categories_ordered_by_categories_definition(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        expected_order = [cat["id"] for cat in CATEGORIES]
        actual_order = [cat.category_id for cat in result.categories]
        assert actual_order == expected_order

    def test_all_items_have_valid_risk_levels(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        valid_levels = {"Low", "Medium", "High", "Critical"}
        for item in result.all_items:
            assert item.risk_level in valid_levels, (
                f"Item '{item.item_id}' has invalid risk_level '{item.risk_level}'"
            )

    def test_all_items_have_non_empty_action(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        for item in result.all_items:
            assert isinstance(item.action, str) and len(item.action.strip()) > 0, (
                f"Item '{item.item_id}' has empty action"
            )

    def test_all_items_have_non_empty_rationale(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        for item in result.all_items:
            assert isinstance(item.rationale, str) and len(item.rationale.strip()) > 0

    def test_all_items_have_non_empty_control_ref(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        for item in result.all_items:
            assert isinstance(item.control_ref, str) and len(item.control_ref.strip()) > 0

    def test_all_items_have_priority_set(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        for item in result.all_items:
            assert isinstance(item.priority, str) and len(item.priority) > 0

    def test_all_items_have_badge_class(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        for item in result.all_items:
            assert isinstance(item.badge_class, str) and len(item.badge_class) > 0

    def test_all_items_belong_to_correct_category(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        for cat in result.categories:
            for item in cat.items:
                assert item.category_id == cat.category_id

    def test_all_items_completed_false(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        for item in result.all_items:
            assert item.completed is False

    def test_high_risk_assessment_produces_more_items(self, high_risk_assessment: AssessmentResult) -> None:
        low_result = generate_checklist(_make_assessment())
        high_result = generate_checklist(high_risk_assessment)
        assert high_result.total_items >= low_result.total_items

    def test_high_risk_assessment_has_critical_items(
        self, high_risk_assessment: AssessmentResult
    ) -> None:
        result = generate_checklist(high_risk_assessment)
        assert result.total_critical_items > 0

    def test_warnings_propagated_from_assessment(self) -> None:
        assessment = _make_assessment(warnings=["Test warning message."])
        result = generate_checklist(assessment)
        assert "Test warning message." in result.warnings

    def test_to_dict_is_json_serialisable(self, checklist: GovernanceChecklist) -> None:
        import json
        d = checklist.to_dict()
        serialised = json.dumps(d)
        assert isinstance(serialised, str)

    def test_total_items_matches_sum_of_category_items(
        self, checklist: GovernanceChecklist
    ) -> None:
        manual_count = sum(cat.item_count for cat in checklist.categories)
        assert checklist.total_items == manual_count

    def test_category_risk_levels_are_from_assessment(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        cat_by_id = assessment.category_results_by_id
        for cat in result.categories:
            expected_risk = cat_by_id.get(cat.category_id)
            if expected_risk:
                assert cat.risk_level == expected_risk.risk_level

    def test_category_scores_match_assessment(self, assessment: AssessmentResult) -> None:
        result = generate_checklist(assessment)
        cat_by_id = assessment.category_results_by_id
        for cat in result.categories:
            expected = cat_by_id.get(cat.category_id)
            if expected:
                assert cat.normalised_score == expected.normalised_score

    @pytest.mark.parametrize(
        "framework_id",
        ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
    )
    def test_all_frameworks_produce_checklist(self, framework_id: str) -> None:
        assessment = _make_assessment(framework_id=framework_id)
        result = generate_checklist(assessment)
        assert isinstance(result, GovernanceChecklist)
        assert result.total_items >= 0

    def test_items_within_category_ordered_by_risk_descending(
        self, high_risk_assessment: AssessmentResult
    ) -> None:
        """Critical items should appear before lower-risk items."""
        from ai_gov_gen.assessor import RISK_LEVELS
        result = generate_checklist(high_risk_assessment)
        for cat in result.categories:
            if len(cat.items) > 1:
                for i in range(len(cat.items) - 1):
                    idx_a = RISK_LEVELS.index(cat.items[i].risk_level)
                    idx_b = RISK_LEVELS.index(cat.items[i + 1].risk_level)
                    assert idx_a >= idx_b, (
                        f"Items in '{cat.category_id}' are not sorted by risk descending: "
                        f"{cat.items[i].risk_level} before {cat.items[i + 1].risk_level}"
                    )


# ---------------------------------------------------------------------------
# _select_checklist_items tests
# ---------------------------------------------------------------------------


class TestSelectChecklistItems:
    """Tests for the internal _select_checklist_items function."""

    def test_returns_list(self, assessment: AssessmentResult) -> None:
        result = _select_checklist_items(assessment)
        assert isinstance(result, list)

    def test_all_items_have_required_keys(self, assessment: AssessmentResult) -> None:
        items = _select_checklist_items(assessment)
        required = {"category_id", "control_ref", "action", "rationale",
                    "effective_risk_level", "frameworks"}
        for item in items:
            missing = required - set(item.keys())
            assert not missing, f"Item missing keys: {missing}"

    def test_items_filtered_by_framework(self) -> None:
        assessment = _make_assessment(framework_id="cmmc_l2")
        items = _select_checklist_items(assessment)
        for item in items:
            assert "cmmc_l2" in item["frameworks"], (
                f"Item '{item['control_ref']}' should not be in cmmc_l2 results"
            )

    def test_high_risk_responses_trigger_more_items(self) -> None:
        low = _make_assessment()
        high = _make_assessment(
            responses={
                "meta_01": "AI", "meta_02": "Team", "meta_03": "Desc.",
                "meta_04": "enterprise",
                "data_02": "no",  # triggers data provenance item
                "model_03": "no",  # triggers bias testing item
            }
        )
        low_items = _select_checklist_items(low)
        high_items = _select_checklist_items(high)
        assert len(high_items) >= len(low_items)

    def test_unanswered_questions_trigger_items(self) -> None:
        """Questions left unanswered should trigger gap items."""
        assessment = _make_assessment(responses={
            "meta_01": "AI", "meta_02": "Team", "meta_03": "Desc.",
            "meta_04": "enterprise",
        })
        items = _select_checklist_items(assessment)
        # Without any answers, should have maximum items triggered
        assert len(items) > 0


# ---------------------------------------------------------------------------
# SSPEntry tests
# ---------------------------------------------------------------------------


class TestSSPEntry:
    """Tests for the SSPEntry dataclass."""

    def _make_entry(self) -> SSPEntry:
        return SSPEntry(
            entry_id="SSP-AI-DATA-001",
            control_family="Data Governance",
            control_ref="NIST AI RMF GOVERN-1.1",
            control_name="AI Data Classification",
            control_description="Classify all AI data assets.",
            implementation_status="Implemented",
            implementation_detail="Data classification applied to all assets.",
            responsible_role="Data Governance Lead",
            assessment_finding="Control is fully implemented.",
            risk_level="Low",
            remediation_action="No remediation required.",
            evidence_artifacts=["Data inventory register", "Classification policy"],
            frameworks=["nist_ai_rmf", "enterprise"],
        )

    def test_to_dict_returns_dict(self) -> None:
        entry = self._make_entry()
        assert isinstance(entry.to_dict(), dict)

    def test_to_dict_contains_all_keys(self) -> None:
        entry = self._make_entry()
        d = entry.to_dict()
        required_keys = {
            "entry_id", "control_family", "control_ref", "control_name",
            "control_description", "implementation_status", "implementation_detail",
            "responsible_role", "assessment_finding", "risk_level",
            "remediation_action", "evidence_artifacts", "frameworks",
        }
        assert required_keys.issubset(set(d.keys()))

    def test_to_dict_values_match(self) -> None:
        entry = self._make_entry()
        d = entry.to_dict()
        assert d["entry_id"] == "SSP-AI-DATA-001"
        assert d["implementation_status"] == "Implemented"
        assert isinstance(d["evidence_artifacts"], list)
        assert len(d["evidence_artifacts"]) == 2


# ---------------------------------------------------------------------------
# generate_ssp_entries tests
# ---------------------------------------------------------------------------


class TestGenerateSspEntries:
    """Integration tests for generate_ssp_entries()."""

    def test_returns_list(self, assessment: AssessmentResult) -> None:
        result = generate_ssp_entries(assessment)
        assert isinstance(result, list)

    def test_returns_non_empty_list(self, assessment: AssessmentResult) -> None:
        result = generate_ssp_entries(assessment)
        assert len(result) > 0

    def test_all_items_are_ssp_entries(self, assessment: AssessmentResult) -> None:
        result = generate_ssp_entries(assessment)
        for entry in result:
            assert isinstance(entry, SSPEntry)

    def test_entry_ids_are_unique(self, assessment: AssessmentResult) -> None:
        result = generate_ssp_entries(assessment)
        ids = [e.entry_id for e in result]
        assert len(ids) == len(set(ids)), "Duplicate SSP entry IDs detected"

    def test_entry_ids_follow_naming_convention(self, assessment: AssessmentResult) -> None:
        result = generate_ssp_entries(assessment)
        for entry in result:
            # Should match SSP-AI-{FAMILY}-{seq:03d}
            assert entry.entry_id.startswith("SSP-AI-"), (
                f"Entry ID '{entry.entry_id}' does not follow naming convention"
            )

    def test_implementation_status_valid_values(self, assessment: AssessmentResult) -> None:
        valid_statuses = {
            "Implemented", "Partially Implemented", "Planned",
            "Not Implemented", "Not Applicable",
        }
        result = generate_ssp_entries(assessment)
        for entry in result:
            assert entry.implementation_status in valid_statuses, (
                f"Entry '{entry.entry_id}' has invalid status '{entry.implementation_status}'"
            )

    def test_risk_levels_are_valid(self, assessment: AssessmentResult) -> None:
        valid_levels = {"Low", "Medium", "High", "Critical"}
        result = generate_ssp_entries(assessment)
        for entry in result:
            assert entry.risk_level in valid_levels, (
                f"Entry '{entry.entry_id}' has invalid risk_level '{entry.risk_level}'"
            )

    def test_control_names_are_non_empty(self, assessment: AssessmentResult) -> None:
        result = generate_ssp_entries(assessment)
        for entry in result:
            assert isinstance(entry.control_name, str) and len(entry.control_name.strip()) > 0

    def test_control_descriptions_are_non_empty(self, assessment: AssessmentResult) -> None:
        result = generate_ssp_entries(assessment)
        for entry in result:
            assert isinstance(entry.control_description, str)
            assert len(entry.control_description.strip()) > 0

    def test_assessment_findings_mention_system_name(self, assessment: AssessmentResult) -> None:
        result = generate_ssp_entries(assessment)
        for entry in result:
            assert assessment.system_name in entry.implementation_detail, (
                f"Entry '{entry.entry_id}' implementation_detail does not mention system name"
            )

    def test_evidence_artifacts_is_non_empty_list(self, assessment: AssessmentResult) -> None:
        result = generate_ssp_entries(assessment)
        for entry in result:
            assert isinstance(entry.evidence_artifacts, list)
            assert len(entry.evidence_artifacts) > 0, (
                f"Entry '{entry.entry_id}' has no evidence artifacts"
            )

    def test_responsible_roles_are_non_empty(self, assessment: AssessmentResult) -> None:
        result = generate_ssp_entries(assessment)
        for entry in result:
            assert isinstance(entry.responsible_role, str)
            assert len(entry.responsible_role.strip()) > 0

    def test_remediation_action_non_empty(self, assessment: AssessmentResult) -> None:
        result = generate_ssp_entries(assessment)
        for entry in result:
            assert isinstance(entry.remediation_action, str)
            assert len(entry.remediation_action.strip()) > 0

    def test_fully_answered_low_risk_has_implemented_entries(
        self, assessment: AssessmentResult
    ) -> None:
        result = generate_ssp_entries(assessment)
        # Some entries should be Implemented since we provided good answers
        statuses = {e.implementation_status for e in result}
        assert "Implemented" in statuses

    def test_high_risk_assessment_has_not_implemented_entries(
        self, high_risk_assessment: AssessmentResult
    ) -> None:
        result = generate_ssp_entries(high_risk_assessment)
        statuses = {e.implementation_status for e in result}
        assert "Not Implemented" in statuses

    def test_to_dict_is_json_serialisable(self, ssp_entries: list[SSPEntry]) -> None:
        import json
        for entry in ssp_entries:
            d = entry.to_dict()
            serialised = json.dumps(d)
            assert isinstance(serialised, str)

    def test_frameworks_list_is_non_empty(self, assessment: AssessmentResult) -> None:
        result = generate_ssp_entries(assessment)
        for entry in result:
            assert isinstance(entry.frameworks, list)
            assert len(entry.frameworks) > 0

    @pytest.mark.parametrize(
        "framework_id",
        ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
    )
    def test_all_frameworks_produce_ssp_entries(self, framework_id: str) -> None:
        assessment = _make_assessment(framework_id=framework_id)
        result = generate_ssp_entries(assessment)
        assert isinstance(result, list)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# _determine_implementation_status_and_finding tests
# ---------------------------------------------------------------------------


class TestDetermineImplementationStatusAndFinding:
    """Tests for the internal SSP status determination helper."""

    def _get_data_encryption_template(self) -> dict[str, Any]:
        """Return the data encryption SSP template for testing."""
        from ai_gov_gen.generator import _SSP_CONTROL_TEMPLATES
        for tmpl in _SSP_CONTROL_TEMPLATES:
            if tmpl.get("finding_question") == "data_05":
                return tmpl
        pytest.skip("data_05 template not found")

    def test_implemented_when_best_answer(self) -> None:
        tmpl = self._get_data_encryption_template()
        status, finding = _determine_implementation_status_and_finding(
            tmpl, {"data_05": "both"}
        )
        assert status == "Implemented"
        assert len(finding) > 0

    def test_not_implemented_when_worst_answer(self) -> None:
        tmpl = self._get_data_encryption_template()
        status, finding = _determine_implementation_status_and_finding(
            tmpl, {"data_05": "neither"}
        )
        assert status == "Not Implemented"

    def test_partial_when_partial_answer(self) -> None:
        tmpl = self._get_data_encryption_template()
        status, finding = _determine_implementation_status_and_finding(
            tmpl, {"data_05": "transit_only"}
        )
        assert status == "Partially Implemented"

    def test_unanswered_returns_not_implemented(self) -> None:
        tmpl = self._get_data_encryption_template()
        status, finding = _determine_implementation_status_and_finding(tmpl, {})
        assert status == "Not Implemented"
        assert "not answered" in finding.lower() or "not implemented" in finding.lower()

    def test_checkbox_answer_uses_first_matching_key(self) -> None:
        """For checkbox questions, the first matching answer value is used."""
        from ai_gov_gen.generator import _SSP_CONTROL_TEMPLATES
        # Find the runtime monitoring template (ops_04 is a checkbox)
        monitoring_tmpl = None
        for tmpl in _SSP_CONTROL_TEMPLATES:
            if tmpl.get("finding_question") == "ops_04":
                monitoring_tmpl = tmpl
                break
        if monitoring_tmpl is None:
            pytest.skip("ops_04 template not found")

        status, finding = _determine_implementation_status_and_finding(
            monitoring_tmpl,
            {"ops_04": ["performance_metrics", "data_drift"]},
        )
        assert len(status) > 0
        assert len(finding) > 0


# ---------------------------------------------------------------------------
# _determine_remediation_action tests
# ---------------------------------------------------------------------------


class TestDetermineRemediationAction:
    """Tests for the internal remediation action helper."""

    def _dummy_template(self) -> dict[str, Any]:
        return {"control_name": "Test Control"}

    def test_implemented_no_remediation(self) -> None:
        action = _determine_remediation_action(self._dummy_template(), "Implemented")
        assert "no" in action.lower() or "not required" in action.lower()

    def test_partially_implemented_remediation(self) -> None:
        action = _determine_remediation_action(
            self._dummy_template(), "Partially Implemented"
        )
        assert "complete" in action.lower() or "implementation" in action.lower()

    def test_planned_remediation(self) -> None:
        action = _determine_remediation_action(self._dummy_template(), "Planned")
        assert "accelerate" in action.lower() or "plan" in action.lower()

    def test_not_applicable_remediation(self) -> None:
        action = _determine_remediation_action(self._dummy_template(), "Not Applicable")
        assert "not applicable" in action.lower() or "not required" in action.lower()

    def test_not_implemented_remediation(self) -> None:
        action = _determine_remediation_action(self._dummy_template(), "Not Implemented")
        assert "immediately" in action.lower() or "initiate" in action.lower()

    def test_unknown_status_returns_not_implemented_action(self) -> None:
        action = _determine_remediation_action(self._dummy_template(), "Unknown Status")
        assert isinstance(action, str) and len(action) > 0


# ---------------------------------------------------------------------------
# PolicySection tests
# ---------------------------------------------------------------------------


class TestPolicySection:
    """Tests for the PolicySection dataclass."""

    def test_to_dict_returns_dict(self) -> None:
        sec = PolicySection(
            section_number="1",
            title="Purpose and Scope",
            content="This policy governs...",
        )
        d = sec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_contains_required_keys(self) -> None:
        sec = PolicySection(
            section_number="2",
            title="Definitions",
            content="Key terms...",
        )
        d = sec.to_dict()
        assert set(d.keys()) == {"section_number", "title", "content"}

    def test_to_dict_values_match(self) -> None:
        sec = PolicySection(
            section_number="3",
            title="Governance",
            content="Governance content.",
        )
        d = sec.to_dict()
        assert d["section_number"] == "3"
        assert d["title"] == "Governance"
        assert d["content"] == "Governance content."


# ---------------------------------------------------------------------------
# PolicyDocument tests
# ---------------------------------------------------------------------------


class TestPolicyDocument:
    """Tests for the PolicyDocument dataclass."""

    def _make_policy_doc(
        self,
        sections: list[PolicySection] | None = None,
    ) -> PolicyDocument:
        return PolicyDocument(
            title="AI Use Policy — Test AI",
            document_id="AI-POL-TEST-20240101",
            version="1.0",
            system_name="Test AI",
            system_owner="Test Team",
            system_purpose="Test purpose.",
            framework_id="enterprise",
            framework_label="Enterprise Generic",
            overall_risk_level="Medium",
            generated_date=date.today().isoformat(),
            sections=sections or [],
            warnings=[],
        )

    def test_full_text_includes_title(self) -> None:
        doc = self._make_policy_doc()
        assert "AI Use Policy" in doc.full_text

    def test_full_text_includes_section_content(self) -> None:
        sections = [
            PolicySection(section_number="1", title="Purpose", content="This is the purpose.")
        ]
        doc = self._make_policy_doc(sections)
        assert "This is the purpose." in doc.full_text

    def test_full_text_includes_all_sections(self) -> None:
        sections = [
            PolicySection(section_number=str(i), title=f"Section {i}", content=f"Content {i}")
            for i in range(1, 4)
        ]
        doc = self._make_policy_doc(sections)
        for sec in sections:
            assert sec.content in doc.full_text

    def test_to_dict_returns_dict(self) -> None:
        doc = self._make_policy_doc()
        assert isinstance(doc.to_dict(), dict)

    def test_to_dict_contains_required_keys(self) -> None:
        doc = self._make_policy_doc()
        d = doc.to_dict()
        required = {
            "title", "document_id", "version", "system_name", "system_owner",
            "system_purpose", "framework_id", "framework_label",
            "overall_risk_level", "generated_date", "sections", "warnings",
        }
        assert required.issubset(set(d.keys()))

    def test_to_dict_sections_is_list_of_dicts(self) -> None:
        sections = [
            PolicySection(section_number="1", title="Purpose", content="Content.")
        ]
        doc = self._make_policy_doc(sections)
        d = doc.to_dict()
        assert isinstance(d["sections"], list)
        assert all(isinstance(s, dict) for s in d["sections"])

    def test_to_dict_warnings_is_list(self) -> None:
        doc = self._make_policy_doc()
        d = doc.to_dict()
        assert isinstance(d["warnings"], list)


# ---------------------------------------------------------------------------
# generate_policy_document tests
# ---------------------------------------------------------------------------


class TestGeneratePolicyDocument:
    """Integration tests for generate_policy_document()."""

    def test_returns_policy_document(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        assert isinstance(result, PolicyDocument)

    def test_system_name_in_document(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        assert result.system_name == assessment.system_name

    def test_system_owner_in_document(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        assert result.system_owner == assessment.system_owner

    def test_system_purpose_in_document(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        assert result.system_purpose == assessment.system_purpose

    def test_framework_id_in_document(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        assert result.framework_id == assessment.framework_id

    def test_overall_risk_level_in_document(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        assert result.overall_risk_level == assessment.overall_risk_level

    def test_generated_date_is_today(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        assert result.generated_date == date.today().isoformat()

    def test_version_is_set(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        assert isinstance(result.version, str) and len(result.version) > 0

    def test_document_id_is_set(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        assert isinstance(result.document_id, str) and len(result.document_id) > 0

    def test_document_id_contains_system_name_prefix(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        # document_id should start with AI-POL-
        assert result.document_id.startswith("AI-POL-")

    def test_has_multiple_sections(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        assert len(result.sections) >= 5

    def test_all_sections_have_non_empty_title(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        for sec in result.sections:
            assert isinstance(sec.title, str) and len(sec.title.strip()) > 0

    def test_all_sections_have_non_empty_content(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        for sec in result.sections:
            assert isinstance(sec.content, str) and len(sec.content.strip()) > 0, (
                f"Section '{sec.title}' has empty content"
            )

    def test_all_sections_have_section_numbers(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        for sec in result.sections:
            assert isinstance(sec.section_number, str) and len(sec.section_number.strip()) > 0

    def test_system_name_appears_in_section_content(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        # System name should appear in at least one section
        contents_with_name = [
            sec for sec in result.sections
            if assessment.system_name in sec.content
        ]
        assert len(contents_with_name) >= 1, (
            f"System name '{assessment.system_name}' not found in any policy section"
        )

    def test_system_owner_appears_in_section_content(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        contents_with_owner = [
            sec for sec in result.sections
            if assessment.system_owner in sec.content
        ]
        assert len(contents_with_owner) >= 1

    def test_framework_label_appears_in_content(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        contents_with_fw = [
            sec for sec in result.sections
            if assessment.framework_label in sec.content
        ]
        assert len(contents_with_fw) >= 1

    def test_full_text_is_non_empty(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        assert len(result.full_text.strip()) > 0

    def test_warnings_propagated(self) -> None:
        assessment = _make_assessment(warnings=["Test policy warning."])
        result = generate_policy_document(assessment)
        assert "Test policy warning." in result.warnings

    def test_title_includes_system_name(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        assert assessment.system_name in result.title

    def test_to_dict_is_json_serialisable(self, policy_doc: PolicyDocument) -> None:
        import json
        d = policy_doc.to_dict()
        serialised = json.dumps(d)
        assert isinstance(serialised, str)

    def test_risk_summary_section_mentions_categories(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        # The risk register section (section 10) should mention category labels
        risk_sections = [
            sec for sec in result.sections
            if "risk" in sec.title.lower() or "register" in sec.title.lower()
        ]
        if risk_sections:
            combined_content = " ".join(s.content for s in risk_sections)
            # At least one category should be mentioned
            cat_labels = ["Data Governance", "Model Risk", "Operational Security", "Compliance"]
            mentioned = any(label in combined_content for label in cat_labels)
            assert mentioned

    @pytest.mark.parametrize(
        "framework_id",
        ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
    )
    def test_all_frameworks_produce_policy_document(self, framework_id: str) -> None:
        assessment = _make_assessment(framework_id=framework_id)
        result = generate_policy_document(assessment)
        assert isinstance(result, PolicyDocument)
        assert len(result.sections) >= 5

    def test_data_section_mentions_data_risk_level(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        data_cr = assessment.get_category_result("data")
        if data_cr:
            data_sections = [
                sec for sec in result.sections
                if "data" in sec.title.lower() or "data" in sec.section_number
            ]
            combined = " ".join(s.content for s in data_sections)
            assert data_cr.risk_level in combined

    def test_policy_section_numbers_are_sequential(self, assessment: AssessmentResult) -> None:
        result = generate_policy_document(assessment)
        # Verify that section numbers go 1, 2, 3, ... or "1", "2", ...
        for i, sec in enumerate(result.sections, start=1):
            assert sec.section_number == str(i), (
                f"Section {i} has number '{sec.section_number}', expected '{i}'"
            )


# ---------------------------------------------------------------------------
# GeneratedArtifacts tests
# ---------------------------------------------------------------------------


class TestGeneratedArtifacts:
    """Tests for the GeneratedArtifacts dataclass."""

    def test_generate_all_returns_artifacts(self, assessment: AssessmentResult) -> None:
        result = generate_all(assessment)
        assert isinstance(result, GeneratedArtifacts)

    def test_artifacts_has_checklist(self, artifacts: GeneratedArtifacts) -> None:
        assert isinstance(artifacts.checklist, GovernanceChecklist)

    def test_artifacts_has_ssp_entries(self, artifacts: GeneratedArtifacts) -> None:
        assert isinstance(artifacts.ssp_entries, list)
        assert all(isinstance(e, SSPEntry) for e in artifacts.ssp_entries)

    def test_artifacts_has_policy_document(self, artifacts: GeneratedArtifacts) -> None:
        assert isinstance(artifacts.policy_document, PolicyDocument)

    def test_artifacts_has_assessment(self, artifacts: GeneratedArtifacts) -> None:
        assert isinstance(artifacts.assessment, AssessmentResult)

    def test_artifacts_assessment_matches_input(self, assessment: AssessmentResult) -> None:
        artifacts = generate_all(assessment)
        assert artifacts.assessment is assessment

    def test_to_dict_returns_dict(self, artifacts: GeneratedArtifacts) -> None:
        assert isinstance(artifacts.to_dict(), dict)

    def test_to_dict_contains_all_keys(self, artifacts: GeneratedArtifacts) -> None:
        d = artifacts.to_dict()
        required = {"checklist", "ssp_entries", "policy_document", "assessment"}
        assert required.issubset(set(d.keys()))

    def test_to_dict_ssp_entries_is_list(self, artifacts: GeneratedArtifacts) -> None:
        d = artifacts.to_dict()
        assert isinstance(d["ssp_entries"], list)

    def test_to_dict_is_json_serialisable(self, artifacts: GeneratedArtifacts) -> None:
        import json
        d = artifacts.to_dict()
        serialised = json.dumps(d)
        assert isinstance(serialised, str)

    def test_generate_all_is_idempotent(self, assessment: AssessmentResult) -> None:
        """Calling generate_all twice should produce equivalent results."""
        result1 = generate_all(assessment)
        result2 = generate_all(assessment)
        assert result1.checklist.total_items == result2.checklist.total_items
        assert len(result1.ssp_entries) == len(result2.ssp_entries)
        assert len(result1.policy_document.sections) == len(result2.policy_document.sections)

    def test_checklist_and_policy_doc_have_same_system_name(
        self, artifacts: GeneratedArtifacts
    ) -> None:
        assert artifacts.checklist.system_name == artifacts.policy_document.system_name

    def test_checklist_and_policy_doc_have_same_framework(
        self, artifacts: GeneratedArtifacts
    ) -> None:
        assert artifacts.checklist.framework_id == artifacts.policy_document.framework_id


# ---------------------------------------------------------------------------
# render_policy_html tests (require Flask application context)
# ---------------------------------------------------------------------------


class TestRenderPolicyHtml:
    """Tests for render_policy_html() — requires a Flask application context."""

    @pytest.fixture()
    def flask_app(self, tmp_path):
        """Create a minimal Flask test application."""
        from ai_gov_gen import create_app
        app = create_app(
            test_config={
                "TESTING": True,
                "OUTPUT_FOLDER": str(tmp_path / "output"),
                "SECRET_KEY": "test-secret",
            }
        )
        return app

    def test_render_policy_html_returns_string(
        self, flask_app, assessment: AssessmentResult
    ) -> None:
        policy_doc = generate_policy_document(assessment)
        with flask_app.app_context():
            html = render_policy_html(policy_doc, assessment)
        assert isinstance(html, str)

    def test_render_policy_html_is_non_empty(
        self, flask_app, assessment: AssessmentResult
    ) -> None:
        policy_doc = generate_policy_document(assessment)
        with flask_app.app_context():
            html = render_policy_html(policy_doc, assessment)
        assert len(html.strip()) > 0

    def test_render_policy_html_contains_system_name(
        self, flask_app, assessment: AssessmentResult
    ) -> None:
        policy_doc = generate_policy_document(assessment)
        with flask_app.app_context():
            html = render_policy_html(policy_doc, assessment)
        assert assessment.system_name in html

    def test_render_policy_html_contains_system_owner(
        self, flask_app, assessment: AssessmentResult
    ) -> None:
        policy_doc = generate_policy_document(assessment)
        with flask_app.app_context():
            html = render_policy_html(policy_doc, assessment)
        assert assessment.system_owner in html

    def test_render_policy_html_is_valid_html(
        self, flask_app, assessment: AssessmentResult
    ) -> None:
        policy_doc = generate_policy_document(assessment)
        with flask_app.app_context():
            html = render_policy_html(policy_doc, assessment)
        assert "<!DOCTYPE html>" in html or "<html" in html
        assert "</html>" in html

    def test_render_policy_html_with_checklist(
        self, flask_app, assessment: AssessmentResult
    ) -> None:
        policy_doc = generate_policy_document(assessment)
        checklist = generate_checklist(assessment)
        with flask_app.app_context():
            html = render_policy_html(policy_doc, assessment, checklist=checklist)
        assert isinstance(html, str) and len(html) > 0

    def test_render_policy_html_with_ssp_entries(
        self, flask_app, assessment: AssessmentResult
    ) -> None:
        policy_doc = generate_policy_document(assessment)
        ssp_entries = generate_ssp_entries(assessment)
        with flask_app.app_context():
            html = render_policy_html(
                policy_doc, assessment, ssp_entries=ssp_entries
            )
        assert isinstance(html, str) and len(html) > 0

    def test_render_policy_html_with_all_artifacts(
        self, flask_app, assessment: AssessmentResult
    ) -> None:
        artifacts = generate_all(assessment)
        with flask_app.app_context():
            html = render_policy_html(
                artifacts.policy_document,
                artifacts.assessment,
                checklist=artifacts.checklist,
                ssp_entries=artifacts.ssp_entries,
            )
        assert isinstance(html, str) and len(html) > 0
        assert artifacts.assessment.system_name in html

    def test_render_policy_html_raises_without_flask_context(
        self, assessment: AssessmentResult
    ) -> None:
        policy_doc = generate_policy_document(assessment)
        with pytest.raises(RuntimeError, match="Flask application context"):
            render_policy_html(policy_doc, assessment)

    def test_render_policy_html_contains_risk_level(
        self, flask_app, assessment: AssessmentResult
    ) -> None:
        policy_doc = generate_policy_document(assessment)
        with flask_app.app_context():
            html = render_policy_html(policy_doc, assessment)
        assert assessment.overall_risk_level in html

    def test_render_policy_html_contains_framework_label(
        self, flask_app, assessment: AssessmentResult
    ) -> None:
        policy_doc = generate_policy_document(assessment)
        with flask_app.app_context():
            html = render_policy_html(policy_doc, assessment)
        assert assessment.framework_label in html

    def test_render_policy_html_checklist_content_present(
        self, flask_app, assessment: AssessmentResult
    ) -> None:
        policy_doc = generate_policy_document(assessment)
        checklist = generate_checklist(assessment)
        with flask_app.app_context():
            html = render_policy_html(policy_doc, assessment, checklist=checklist)
        # Checklist items' control refs should appear in the HTML
        if checklist.all_items:
            first_item = checklist.all_items[0]
            assert first_item.control_ref in html

    def test_render_policy_html_ssp_entry_ids_present(
        self, flask_app, assessment: AssessmentResult
    ) -> None:
        policy_doc = generate_policy_document(assessment)
        ssp_entries = generate_ssp_entries(assessment)
        with flask_app.app_context():
            html = render_policy_html(
                policy_doc, assessment, ssp_entries=ssp_entries
            )
        if ssp_entries:
            assert ssp_entries[0].entry_id in html


# ---------------------------------------------------------------------------
# Cross-component consistency tests
# ---------------------------------------------------------------------------


class TestCrossComponentConsistency:
    """Tests that verify consistency across checklist, SSP, and policy."""

    def test_all_artifacts_share_system_name(self, artifacts: GeneratedArtifacts) -> None:
        assert artifacts.checklist.system_name == artifacts.policy_document.system_name
        assert artifacts.checklist.system_name == artifacts.assessment.system_name

    def test_all_artifacts_share_framework_id(self, artifacts: GeneratedArtifacts) -> None:
        assert artifacts.checklist.framework_id == artifacts.policy_document.framework_id
        assert artifacts.checklist.framework_id == artifacts.assessment.framework_id

    def test_all_artifacts_share_overall_risk_level(self, artifacts: GeneratedArtifacts) -> None:
        assert artifacts.checklist.overall_risk_level == artifacts.policy_document.overall_risk_level

    def test_all_artifacts_share_generated_date(self, artifacts: GeneratedArtifacts) -> None:
        today = date.today().isoformat()
        assert artifacts.checklist.generated_date == today
        assert artifacts.policy_document.generated_date == today

    def test_ssp_entry_system_names_consistent(self, artifacts: GeneratedArtifacts) -> None:
        system_name = artifacts.assessment.system_name
        for entry in artifacts.ssp_entries:
            assert system_name in entry.implementation_detail

    def test_high_risk_produces_more_checklist_items_than_low_risk(self) -> None:
        low_assessment = _make_assessment(overall_score=10.0)
        high_assessment = _make_assessment(
            overall_score=90.0,
            scores={"data": 90.0, "model": 90.0, "ops": 90.0, "compliance": 90.0},
            responses={
                "meta_01": "AI", "meta_02": "Team", "meta_03": "Desc.",
                "meta_04": "enterprise",
                "data_02": "no",
                "data_03": "no",
                "data_05": "neither",
                "data_06": "no",
                "data_07": "no",
                "data_08": "no",
                "model_03": "no",
                "model_04": "no",
                "model_05": "no",
                "model_07": "no",
                "model_08": "no",
                "ops_02": "no",
                "ops_03": "no",
                "ops_04": ["none"],
                "ops_05": "no",
                "ops_06": "no",
                "ops_07": ["none"],
                "ops_08": "no",
                "comp_02": "no",
                "comp_03": "no",
                "comp_04": "no",
                "comp_05": "no",
                "comp_06": "no",
                "comp_07": "no",
                "comp_08": "no_ssp",
            },
        )
        low_artifacts = generate_all(low_assessment)
        high_artifacts = generate_all(high_assessment)
        assert high_artifacts.checklist.total_items >= low_artifacts.checklist.total_items

    def test_policy_document_sections_cover_all_categories(self, artifacts: GeneratedArtifacts) -> None:
        all_content = artifacts.policy_document.full_text
        # The policy should at minimum mention data, model, ops, and compliance topics
        expected_topics = ["data", "model", "access", "audit"]
        for topic in expected_topics:
            assert topic.lower() in all_content.lower(), (
                f"Policy document does not mention '{topic}'"
            )
