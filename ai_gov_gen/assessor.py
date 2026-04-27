"""Risk scoring engine for the AI Gov Gen questionnaire.

This module scores questionnaire responses, maps aggregate scores to
Low / Medium / High / Critical risk levels per category, and returns a
structured :class:`AssessmentResult` object ready for consumption by the
document generator.

Scoring algorithm
-----------------
Each scorable question (``weight > 0.0``) contributes a **weighted risk
score** to its category:

1.  For **radio** and **select** questions the selected option's
    ``risk_weight`` (0–3) is used directly.
2.  For **checkbox** questions the *maximum* ``risk_weight`` across all
    selected options is used (selecting even one high-risk option is a
    signal).  Selecting *no* options is treated as the maximum risk weight
    for the question (unanswered = unknown risk).
3.  **text** / **textarea** questions have ``weight == 0.0`` by design so
    they never enter the scoring calculation.

The raw weighted score for a question is::

    raw = option_risk_weight * question.weight

The *maximum possible* raw score for a question is::

    max_raw = MAX_OPTION_RISK_WEIGHT * question.weight   # i.e. 3 * weight

Category scores are then normalised to the range ``[0.0, 100.0]``::

    normalised = (sum_of_raw / sum_of_max_raw) * 100

Risk level thresholds (per category and overall)
------------------------------------------------
* **Low**      : 0 ≤ score < 25
* **Medium**   : 25 ≤ score < 50
* **High**     : 50 ≤ score < 75
* **Critical** : 75 ≤ score ≤ 100

The **overall** risk score is the weighted mean of all category normalised
scores, where each category weight defaults to 1.0 (equal weighting).  A
custom ``category_weights`` mapping can override this.

Public API
----------
:func:`score_responses`
    Primary entry point.  Accepts the raw form data dict and an optional
    framework id; returns an :class:`AssessmentResult`.

:class:`AssessmentResult`
    Dataclass-like result object with per-category scores, risk levels,
    an overall score, metadata fields, and helper properties.

:class:`CategoryResult`
    Per-category scoring detail.

Constants
---------
:data:`RISK_LEVELS` — ordered list of risk level label strings.
:data:`RISK_THRESHOLDS` — mapping of risk level → minimum score threshold.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ai_gov_gen.questions import (
    CATEGORIES,
    FRAMEWORK_BY_ID,
    QUESTION_BY_ID,
    get_scored_questions,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Risk level constants
# ---------------------------------------------------------------------------

#: Ordered list of risk levels from lowest to highest.
RISK_LEVELS: list[str] = ["Low", "Medium", "High", "Critical"]

#: Minimum normalised score (0–100) required to reach each risk level.
RISK_THRESHOLDS: dict[str, float] = {
    "Low": 0.0,
    "Medium": 25.0,
    "High": 50.0,
    "Critical": 75.0,
}

#: Maximum risk weight assigned to any single option.
_MAX_OPTION_RISK_WEIGHT: int = 3

#: Default equal weight applied to each category when computing overall score.
_DEFAULT_CATEGORY_WEIGHT: float = 1.0


# ---------------------------------------------------------------------------
# Result data structures
# ---------------------------------------------------------------------------


@dataclass
class CategoryResult:
    """Scoring result for a single risk category.

    Attributes:
        category_id: The category identifier (e.g., ``"data"``).
        category_label: Human-readable category label.
        normalised_score: Float in ``[0.0, 100.0]`` representing risk within
            this category.  Higher values indicate greater risk.
        risk_level: One of ``"Low"``, ``"Medium"``, ``"High"``, or
            ``"Critical"``.
        raw_score: Sum of weighted option risk weights for answered questions.
        max_possible_score: Maximum achievable raw score for this category
            given the answered questions.
        answered_questions: Number of scored questions answered in this
            category.
        total_questions: Total number of scored questions in this category
            (for the active framework filter).
        question_details: List of per-question scoring detail dicts.  Each
            dict has keys ``question_id``, ``text``, ``weight``,
            ``option_risk_weight``, ``raw_contribution``, and
            ``max_contribution``.
    """

    category_id: str
    category_label: str
    normalised_score: float
    risk_level: str
    raw_score: float
    max_possible_score: float
    answered_questions: int
    total_questions: int
    question_details: list[dict[str, Any]] = field(default_factory=list)

    @property
    def completion_pct(self) -> float:
        """Percentage of scored questions that received an answer.

        Returns:
            Float in ``[0.0, 100.0]``.
        """
        if self.total_questions == 0:
            return 100.0
        return round((self.answered_questions / self.total_questions) * 100.0, 1)

    @property
    def risk_level_index(self) -> int:
        """Zero-based index of the risk level within :data:`RISK_LEVELS`.

        Returns:
            Integer index (0 = Low, 3 = Critical).
        """
        try:
            return RISK_LEVELS.index(self.risk_level)
        except ValueError:
            return 0

    def to_dict(self) -> dict[str, Any]:
        """Serialise this result to a plain dictionary.

        Returns:
            Dict with all public fields including computed properties.
        """
        return {
            "category_id": self.category_id,
            "category_label": self.category_label,
            "normalised_score": self.normalised_score,
            "risk_level": self.risk_level,
            "raw_score": self.raw_score,
            "max_possible_score": self.max_possible_score,
            "answered_questions": self.answered_questions,
            "total_questions": self.total_questions,
            "completion_pct": self.completion_pct,
            "risk_level_index": self.risk_level_index,
            "question_details": self.question_details,
        }


@dataclass
class AssessmentResult:
    """Complete structured result of a scored AI risk assessment.

    Attributes:
        category_results: Ordered list of :class:`CategoryResult` objects,
            one per category in the order defined by
            :data:`~ai_gov_gen.questions.CATEGORIES`.
        overall_score: Weighted mean of all category normalised scores,
            expressed as a float in ``[0.0, 100.0]``.
        overall_risk_level: Top-level risk designation derived from
            ``overall_score``.
        framework_id: The compliance framework used to filter questions
            during scoring (e.g., ``"nist_ai_rmf"``).
        framework_label: Human-readable framework label.
        system_name: Name of the AI system being assessed (from meta_01).
        system_owner: Name of the responsible team / unit (from meta_02).
        system_purpose: Brief purpose statement (from meta_03).
        responses: The original raw response dict for reference.
        warnings: List of warning message strings (e.g., unanswered
            required questions).
    """

    category_results: list[CategoryResult]
    overall_score: float
    overall_risk_level: str
    framework_id: str
    framework_label: str
    system_name: str
    system_owner: str
    system_purpose: str
    responses: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def category_results_by_id(self) -> dict[str, CategoryResult]:
        """Map of category_id → :class:`CategoryResult`.

        Returns:
            Dict for fast lookup by category identifier.
        """
        return {cr.category_id: cr for cr in self.category_results}

    @property
    def highest_risk_category(self) -> CategoryResult | None:
        """Return the :class:`CategoryResult` with the highest normalised score.

        Returns:
            The riskiest category result, or ``None`` if there are none.
        """
        if not self.category_results:
            return None
        return max(self.category_results, key=lambda cr: cr.normalised_score)

    @property
    def critical_categories(self) -> list[CategoryResult]:
        """Return all categories rated Critical.

        Returns:
            List of :class:`CategoryResult` with risk_level == ``"Critical"``.
        """
        return [cr for cr in self.category_results if cr.risk_level == "Critical"]

    @property
    def high_or_critical_categories(self) -> list[CategoryResult]:
        """Return all categories rated High or Critical.

        Returns:
            List of :class:`CategoryResult` with risk_level in
            ``{"High", "Critical"}``.
        """
        return [
            cr for cr in self.category_results
            if cr.risk_level in {"High", "Critical"}
        ]

    @property
    def overall_risk_level_index(self) -> int:
        """Zero-based index of the overall risk level within :data:`RISK_LEVELS`.

        Returns:
            Integer index (0 = Low, 3 = Critical).
        """
        try:
            return RISK_LEVELS.index(self.overall_risk_level)
        except ValueError:
            return 0

    def get_category_result(self, category_id: str) -> CategoryResult | None:
        """Return the :class:`CategoryResult` for a given category id.

        Args:
            category_id: The category identifier string.

        Returns:
            Matching :class:`CategoryResult` or ``None`` if not found.
        """
        return self.category_results_by_id.get(category_id)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the full assessment result to a plain dictionary.

        Returns:
            Nested dict representation suitable for JSON serialisation or
            template rendering.
        """
        return {
            "overall_score": self.overall_score,
            "overall_risk_level": self.overall_risk_level,
            "overall_risk_level_index": self.overall_risk_level_index,
            "framework_id": self.framework_id,
            "framework_label": self.framework_label,
            "system_name": self.system_name,
            "system_owner": self.system_owner,
            "system_purpose": self.system_purpose,
            "warnings": self.warnings,
            "category_results": [
                cr.to_dict() for cr in self.category_results
            ],
            "highest_risk_category": (
                self.highest_risk_category.to_dict()
                if self.highest_risk_category else None
            ),
            "critical_categories": [
                cr.to_dict() for cr in self.critical_categories
            ],
            "high_or_critical_categories": [
                cr.to_dict() for cr in self.high_or_critical_categories
            ],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _map_score_to_risk_level(normalised_score: float) -> str:
    """Map a normalised score in ``[0.0, 100.0]`` to a risk level label.

    The mapping applies the thresholds defined in :data:`RISK_THRESHOLDS`.
    Scores are clamped to ``[0.0, 100.0]`` before comparison.

    Args:
        normalised_score: Float score in the range ``[0.0, 100.0]``.

    Returns:
        One of ``"Low"``, ``"Medium"``, ``"High"``, or ``"Critical"``.
    """
    score = max(0.0, min(100.0, normalised_score))
    # Iterate from highest threshold downward
    for level in reversed(RISK_LEVELS):
        if score >= RISK_THRESHOLDS[level]:
            return level
    return "Low"


def _extract_option_risk_weight(
    question: dict[str, Any],
    answer: Any,
) -> tuple[int, bool]:
    """Determine the effective option risk weight for a scored question.

    For **radio** / **select** questions the selected option's risk weight
    is returned.  For **checkbox** questions the maximum risk weight across
    all selected options is returned.  If the answer is missing or invalid
    (cannot be matched to any option) the maximum risk weight (3) is
    returned and ``answered`` is set to ``False``.

    Args:
        question: The question dict from the question bank.
        answer: The raw answer value from the form submission.  For
            checkboxes this should be a ``list[str]``; for radio/select a
            ``str``.

    Returns:
        A ``(risk_weight, answered)`` tuple where ``risk_weight`` is an
        integer in ``[0, 3]`` and ``answered`` is ``True`` when the answer
        matched at least one valid option.
    """
    input_type = question["input_type"]
    options: list[dict[str, Any]] = question["options"]

    # Build a lookup from option value → risk_weight
    option_map: dict[str, int] = {
        opt["value"]: opt["risk_weight"] for opt in options
    }

    if input_type in {"radio", "select"}:
        if not answer or str(answer) not in option_map:
            logger.debug(
                "Question '%s': no valid answer found (got %r). "
                "Assigning max risk weight.",
                question["id"],
                answer,
            )
            return _MAX_OPTION_RISK_WEIGHT, False
        return option_map[str(answer)], True

    if input_type == "checkbox":
        selected: list[str] = []
        if isinstance(answer, list):
            selected = [str(v) for v in answer if str(v) in option_map]
        elif isinstance(answer, str) and answer in option_map:
            selected = [answer]

        if not selected:
            logger.debug(
                "Question '%s': no valid checkbox selections found (got %r). "
                "Assigning max risk weight.",
                question["id"],
                answer,
            )
            return _MAX_OPTION_RISK_WEIGHT, False

        return max(option_map[v] for v in selected), True

    # text / textarea — should not reach here because weight==0.0 for these
    return 0, bool(answer)


def _score_category(
    category_id: str,
    scored_questions: list[dict[str, Any]],
    responses: dict[str, Any],
) -> CategoryResult:
    """Compute the :class:`CategoryResult` for a single category.

    Args:
        category_id: The category identifier string.
        scored_questions: The list of scored (weight > 0) questions for
            this category, pre-filtered for the active framework.
        responses: The full raw responses dict from the form submission.

    Returns:
        A populated :class:`CategoryResult`.
    """
    from ai_gov_gen.questions import get_category_metadata  # local import

    cat_meta = get_category_metadata(category_id)
    category_label = cat_meta["label"]

    raw_score: float = 0.0
    max_possible: float = 0.0
    answered_count: int = 0
    question_details: list[dict[str, Any]] = []

    for question in scored_questions:
        q_id = question["id"]
        weight = float(question["weight"])
        answer = responses.get(q_id)

        risk_weight, answered = _extract_option_risk_weight(question, answer)

        raw_contribution = risk_weight * weight
        max_contribution = _MAX_OPTION_RISK_WEIGHT * weight

        raw_score += raw_contribution
        max_possible += max_contribution
        if answered:
            answered_count += 1

        question_details.append(
            {
                "question_id": q_id,
                "text": question["text"],
                "weight": weight,
                "answer": answer,
                "option_risk_weight": risk_weight,
                "answered": answered,
                "raw_contribution": round(raw_contribution, 4),
                "max_contribution": round(max_contribution, 4),
            }
        )

    # Normalise score to [0, 100]
    if max_possible > 0.0:
        normalised = (raw_score / max_possible) * 100.0
    else:
        normalised = 0.0

    normalised = round(normalised, 2)
    risk_level = _map_score_to_risk_level(normalised)

    return CategoryResult(
        category_id=category_id,
        category_label=category_label,
        normalised_score=normalised,
        risk_level=risk_level,
        raw_score=round(raw_score, 4),
        max_possible_score=round(max_possible, 4),
        answered_questions=answered_count,
        total_questions=len(scored_questions),
        question_details=question_details,
    )


def _compute_overall_score(
    category_results: list[CategoryResult],
    category_weights: dict[str, float] | None = None,
) -> float:
    """Compute the overall weighted mean normalised score.

    Args:
        category_results: List of per-category results.
        category_weights: Optional mapping of category_id → weight float.
            Defaults to equal weighting (1.0) for all categories.

    Returns:
        Weighted mean score as a float in ``[0.0, 100.0]``.
    """
    if not category_results:
        return 0.0

    weights = category_weights or {}
    total_weight: float = 0.0
    weighted_sum: float = 0.0

    for cr in category_results:
        w = weights.get(cr.category_id, _DEFAULT_CATEGORY_WEIGHT)
        weighted_sum += cr.normalised_score * w
        total_weight += w

    if total_weight == 0.0:
        return 0.0

    return round(weighted_sum / total_weight, 2)


def _extract_metadata(responses: dict[str, Any]) -> tuple[str, str, str]:
    """Extract system metadata fields from the responses dict.

    Args:
        responses: Raw form response dict.

    Returns:
        Tuple of ``(system_name, system_owner, system_purpose)`` strings.
        Falls back to placeholder strings when values are missing.
    """
    system_name = str(responses.get("meta_01", "")).strip() or "[AI System Name Not Provided]"
    system_owner = str(responses.get("meta_02", "")).strip() or "[System Owner Not Provided]"
    system_purpose = str(responses.get("meta_03", "")).strip() or "[System Purpose Not Provided]"
    return system_name, system_owner, system_purpose


def _extract_framework_id(responses: dict[str, Any]) -> str:
    """Determine the target framework from responses, defaulting to 'enterprise'.

    Args:
        responses: Raw form response dict.  The key ``"meta_04"`` holds the
            framework selector value.

    Returns:
        A valid framework id string.
    """
    fw_id = str(responses.get("meta_04", "enterprise")).strip()
    if fw_id not in FRAMEWORK_BY_ID:
        logger.warning(
            "Framework id '%s' from responses is not recognised; "
            "defaulting to 'enterprise'.",
            fw_id,
        )
        fw_id = "enterprise"
    return fw_id


def _collect_warnings(
    category_results: list[CategoryResult],
    responses: dict[str, Any],
) -> list[str]:
    """Collect advisory warning messages about the assessment quality.

    Warnings are informational and do not alter scores.  They alert the
    user to potential issues such as low completion rates or unanswered
    required questions.

    Args:
        category_results: Scored category results.
        responses: Raw form responses.

    Returns:
        List of human-readable warning strings.  May be empty.
    """
    warnings: list[str] = []

    for cr in category_results:
        if cr.total_questions > 0 and cr.completion_pct < 80.0:
            warnings.append(
                f"Category '{cr.category_label}' has low completion rate "
                f"({cr.completion_pct:.0f}% answered). "
                "Unanswered questions are scored at maximum risk weight."
            )

    # Check for metadata fields
    if not str(responses.get("meta_01", "")).strip():
        warnings.append(
            "AI system name (meta_01) was not provided. "
            "Generated documents will use a placeholder."
        )
    if not str(responses.get("meta_02", "")).strip():
        warnings.append(
            "System owner / team name (meta_02) was not provided. "
            "Generated documents will use a placeholder."
        )
    if not str(responses.get("meta_03", "")).strip():
        warnings.append(
            "System purpose description (meta_03) was not provided. "
            "Generated documents will use a placeholder."
        )

    return warnings


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def score_responses(
    responses: dict[str, Any],
    framework_id: str | None = None,
    category_weights: dict[str, float] | None = None,
) -> AssessmentResult:
    """Score a complete set of questionnaire responses.

    This is the primary public entry point for the risk scoring engine.
    It orchestrates question retrieval, per-category scoring, overall score
    computation, and metadata extraction before returning a structured
    :class:`AssessmentResult`.

    Args:
        responses: Dict mapping question id strings to answer values.  For
            radio/select questions the value should be a ``str``; for
            checkboxes a ``list[str]``; for text/textarea a ``str``.  The
            framework selector answer is read from key ``"meta_04"``.
        framework_id: Optional explicit framework id to use for filtering
            questions.  When ``None``, the framework is read from
            ``responses["meta_04"]``, defaulting to ``"enterprise"`` if
            absent or unrecognised.
        category_weights: Optional mapping of category_id → float weight
            for the overall score computation.  Defaults to equal weighting
            across all categories.

    Returns:
        A fully populated :class:`AssessmentResult` instance.

    Raises:
        ValueError: If ``framework_id`` is explicitly provided but is not
            a recognised framework identifier.
    """
    # Resolve framework
    if framework_id is not None:
        if framework_id not in FRAMEWORK_BY_ID:
            valid = ", ".join(sorted(FRAMEWORK_BY_ID.keys()))
            raise ValueError(
                f"Unknown framework '{framework_id}'. Valid options: {valid}"
            )
        resolved_framework_id = framework_id
    else:
        resolved_framework_id = _extract_framework_id(responses)

    framework_meta = FRAMEWORK_BY_ID[resolved_framework_id]
    framework_label = framework_meta["label"]

    logger.info(
        "Scoring responses for framework '%s' (%d keys in responses).",
        resolved_framework_id,
        len(responses),
    )

    # Extract metadata answers
    system_name, system_owner, system_purpose = _extract_metadata(responses)

    # Score each category
    category_results: list[CategoryResult] = []
    for cat in CATEGORIES:
        cat_id = cat["id"]
        scored_qs = get_scored_questions(
            category_id=cat_id,
            framework_id=resolved_framework_id,
        )
        cat_result = _score_category(cat_id, scored_qs, responses)
        category_results.append(cat_result)
        logger.debug(
            "Category '%s': normalised_score=%.2f, risk_level='%s', "
            "answered=%d/%d",
            cat_id,
            cat_result.normalised_score,
            cat_result.risk_level,
            cat_result.answered_questions,
            cat_result.total_questions,
        )

    # Compute overall score
    overall_score = _compute_overall_score(category_results, category_weights)
    overall_risk_level = _map_score_to_risk_level(overall_score)

    logger.info(
        "Overall assessment score: %.2f (%s).",
        overall_score,
        overall_risk_level,
    )

    # Collect warnings
    warnings = _collect_warnings(category_results, responses)

    return AssessmentResult(
        category_results=category_results,
        overall_score=overall_score,
        overall_risk_level=overall_risk_level,
        framework_id=resolved_framework_id,
        framework_label=framework_label,
        system_name=system_name,
        system_owner=system_owner,
        system_purpose=system_purpose,
        responses=responses,
        warnings=warnings,
    )
