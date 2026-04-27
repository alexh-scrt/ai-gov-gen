"""Flask route handlers for AI Gov Gen.

This module defines the ``main_bp`` Blueprint containing all route handlers
for the AI Gov Gen web application:

* ``GET  /``                   — Landing page / framework selector
* ``GET  /questionnaire``      — Multi-step questionnaire wizard (step 1)
* ``POST /questionnaire``      — Submit questionnaire step and advance
* ``GET  /results``            — Assessment results and document preview
* ``POST /results``            — Submit complete questionnaire and score
* ``GET  /download/docx``      — Download generated DOCX artifact
* ``GET  /download/pdf``       — Download generated PDF artifact
* ``GET  /about``              — About / framework information page

Session state
-------------
The wizard stores questionnaire responses in the Flask session so that
users can progress through multiple category steps without losing earlier
answers.  The session keys used are:

* ``"responses"``      — Accumulated dict of question_id → answer
* ``"current_step"``   — Index of the current wizard step (0-based)
* ``"framework_id"``   — Selected compliance framework id
* ``"assessment"``     — Serialised assessment result dict (post-scoring)

Blueprint
---------
:data:`main_bp` — The Flask Blueprint registered by :func:`~ai_gov_gen.create_app`.
"""

from __future__ import annotations

import io
import logging
from typing import Any

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from ai_gov_gen.assessor import AssessmentResult, score_responses
from ai_gov_gen.exporter import (
    ExportError,
    build_export_filename,
    export_docx_from_assessment,
    export_pdf_from_assessment,
)
from ai_gov_gen.generator import (
    generate_all,
    generate_checklist,
    generate_policy_document,
    generate_ssp_entries,
)
from ai_gov_gen.questions import (
    CATEGORIES,
    FRAMEWORK_METADATA,
    QUESTIONS_BY_CATEGORY,
    get_category_metadata,
    get_questions_for_category,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

main_bp = Blueprint(
    "main",
    __name__,
    template_folder="templates",
    static_folder="static",
)

# ---------------------------------------------------------------------------
# Wizard step configuration
# ---------------------------------------------------------------------------

# Each step is a dict with:
#   step_index    — zero-based position in the wizard
#   category_id   — question category to display (or None for meta steps)
#   title         — display title
#   description   — short description shown in the wizard header

_WIZARD_STEPS: list[dict[str, Any]] = [
    {
        "step_index": 0,
        "category_id": None,
        "step_id": "setup",
        "title": "System Setup",
        "description": (
            "Tell us about the AI system you are assessing and select "
            "your target compliance framework."
        ),
    },
    {
        "step_index": 1,
        "category_id": "data",
        "step_id": "data",
        "title": "Data Governance",
        "description": (
            "Questions about data provenance, privacy, quality, encryption, "
            "and lifecycle management for data used in or by the AI system."
        ),
    },
    {
        "step_index": 2,
        "category_id": "model",
        "step_id": "model",
        "title": "Model Risk",
        "description": (
            "Questions about model development, bias testing, explainability, "
            "validation, version control, and human oversight."
        ),
    },
    {
        "step_index": 3,
        "category_id": "ops",
        "step_id": "ops",
        "title": "Operational Security",
        "description": (
            "Questions about deployment architecture, access control, runtime "
            "monitoring, incident response, and supply-chain security."
        ),
    },
    {
        "step_index": 4,
        "category_id": "compliance",
        "step_id": "compliance",
        "title": "Compliance & Audit",
        "description": (
            "Questions about regulatory obligations, governance structure, "
            "vendor management, audit readiness, and staff training."
        ),
    },
]

_TOTAL_STEPS = len(_WIZARD_STEPS)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _get_setup_questions() -> list[dict[str, Any]]:
    """Return the meta/setup questions shown on wizard step 0.

    These are the contextual questions (meta_01 through meta_04) that
    capture system name, owner, purpose, and framework selection.

    Returns:
        Ordered list of setup question dicts.
    """
    from ai_gov_gen.questions import QUESTION_BY_ID  # local import

    meta_ids = ["meta_01", "meta_02", "meta_03", "meta_04"]
    return [QUESTION_BY_ID[qid] for qid in meta_ids if qid in QUESTION_BY_ID]


def _get_step_questions(step: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the questions for a given wizard step dict.

    For the setup step (category_id is None) returns the meta questions.
    For category steps, returns all questions in that category.

    Args:
        step: A step dict from :data:`_WIZARD_STEPS`.

    Returns:
        List of question dicts for the step.
    """
    if step["category_id"] is None:
        return _get_setup_questions()

    framework_id = session.get("framework_id", "enterprise")
    try:
        return get_questions_for_category(
            step["category_id"],
            framework_id=framework_id,
        )
    except ValueError:
        return get_questions_for_category(step["category_id"])


def _extract_form_answers(
    form_data: Any,
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Extract and normalise answers from the submitted form data.

    For checkbox questions the value is a list of selected option values.
    For all other input types the value is a single string.
    Empty or missing answers are stored as empty string.

    Args:
        form_data: The ``request.form`` ImmutableMultiDict.
        questions: The list of question dicts for this step.

    Returns:
        Dict mapping question_id → answer (str or list[str]).
    """
    answers: dict[str, Any] = {}
    for question in questions:
        q_id = question["id"]
        if question["input_type"] == "checkbox":
            # getlist returns all selected values as a list
            selected = form_data.getlist(q_id)
            answers[q_id] = selected if selected else []
        else:
            answers[q_id] = form_data.get(q_id, "").strip()
    return answers


def _build_assessment_from_session() -> AssessmentResult | None:
    """Score the responses stored in the session and return an AssessmentResult.

    Returns:
        A scored :class:`~ai_gov_gen.assessor.AssessmentResult`, or
        ``None`` if the session contains insufficient data.
    """
    responses = session.get("responses", {})
    if not responses:
        return None

    framework_id = session.get("framework_id") or responses.get("meta_04", "enterprise")

    try:
        return score_responses(responses, framework_id=framework_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to score responses from session: %s", exc)
        return None


def _restore_assessment_from_session() -> AssessmentResult | None:
    """Attempt to reconstruct an AssessmentResult from cached session data.

    When the ``"assessment"`` key is present in the session it means the
    user has already submitted the full questionnaire.  Re-score from
    responses to avoid storing large objects in the cookie.

    Returns:
        AssessmentResult or None.
    """
    if "responses" not in session:
        return None
    return _build_assessment_from_session()


def _progress_percent(step_index: int) -> int:
    """Compute the wizard progress percentage for a given step index.

    Args:
        step_index: Zero-based step index.

    Returns:
        Integer percentage (0–100).
    """
    return int((step_index / _TOTAL_STEPS) * 100)


# ---------------------------------------------------------------------------
# Route: Landing page
# ---------------------------------------------------------------------------


@main_bp.route("/", methods=["GET"])
def index() -> str:
    """Render the landing page with framework overview and start prompt.

    Returns:
        Rendered ``index.html`` template.
    """
    return render_template(
        "index.html",
        frameworks=FRAMEWORK_METADATA,
        categories=CATEGORIES,
        title="AI Gov Gen — AI Governance Document Generator",
    )


# ---------------------------------------------------------------------------
# Route: Questionnaire wizard
# ---------------------------------------------------------------------------


@main_bp.route("/questionnaire", methods=["GET"])
def questionnaire() -> Response | str:
    """Render the current wizard step or redirect to step 0.

    The current step is read from the session.  If the session is fresh
    (no ``current_step`` key) the user is redirected to step 0.

    Query parameters:
        step (int): Optional explicit step index to navigate to directly.
        reset (str): If ``"1"`` or ``"true"``, clears the session and
            starts the wizard from the beginning.

    Returns:
        Rendered ``questionnaire.html`` template or redirect response.
    """
    # Handle explicit reset request
    if request.args.get("reset", "").lower() in ("1", "true", "yes"):
        session.clear()
        return redirect(url_for("main.questionnaire"))

    # Read explicit step override from query string
    requested_step = request.args.get("step", type=int)
    if requested_step is not None:
        step_index = max(0, min(requested_step, _TOTAL_STEPS - 1))
    else:
        step_index = session.get("current_step", 0)

    current_step = _WIZARD_STEPS[step_index]
    questions = _get_step_questions(current_step)
    existing_responses = session.get("responses", {})

    return render_template(
        "questionnaire.html",
        step=current_step,
        step_index=step_index,
        total_steps=_TOTAL_STEPS,
        steps=_WIZARD_STEPS,
        questions=questions,
        responses=existing_responses,
        frameworks=FRAMEWORK_METADATA,
        categories=CATEGORIES,
        progress_percent=_progress_percent(step_index),
        is_last_step=(step_index == _TOTAL_STEPS - 1),
        is_first_step=(step_index == 0),
        title=f"Step {step_index + 1} of {_TOTAL_STEPS}: {current_step['title']}",
    )


@main_bp.route("/questionnaire", methods=["POST"])
def questionnaire_submit() -> Response:
    """Handle questionnaire step submission.

    Extracts answers from the submitted form, merges them into the
    session responses dict, and either advances to the next step or
    redirects to the results page if the final step was submitted.

    Form fields:
        ``step_index`` (int): The step index that was submitted.
        Per-question answer fields named by their question ID.

    Returns:
        Redirect to the next wizard step or to the results page.
    """
    submitted_step_index = int(request.form.get("step_index", 0))
    submitted_step_index = max(0, min(submitted_step_index, _TOTAL_STEPS - 1))

    current_step = _WIZARD_STEPS[submitted_step_index]
    questions = _get_step_questions(current_step)

    # Extract and merge answers
    answers = _extract_form_answers(request.form, questions)

    existing_responses: dict[str, Any] = session.get("responses", {})
    existing_responses.update(answers)
    session["responses"] = existing_responses

    # Update framework selection if the setup step was submitted
    if current_step["step_id"] == "setup":
        framework_id = answers.get("meta_04", "enterprise")
        session["framework_id"] = framework_id if framework_id else "enterprise"

    logger.debug(
        "Step %d submitted; %d answers collected so far.",
        submitted_step_index,
        len(existing_responses),
    )

    # Determine next action
    next_step_index = submitted_step_index + 1

    if next_step_index >= _TOTAL_STEPS:
        # Final step submitted — redirect to results
        session["current_step"] = _TOTAL_STEPS - 1
        return redirect(url_for("main.results"))

    # Advance to the next step
    session["current_step"] = next_step_index
    return redirect(url_for("main.questionnaire", step=next_step_index))


# ---------------------------------------------------------------------------
# Route: Results page
# ---------------------------------------------------------------------------


@main_bp.route("/results", methods=["GET"])
def results() -> Response | str:
    """Score the questionnaire responses and display the results page.

    Retrieves stored responses from the session, runs the scoring engine,
    generates all governance artifacts, and renders the results template.

    If no responses are found in the session, redirects the user back to
    the start of the questionnaire.

    Returns:
        Rendered ``results.html`` template or redirect response.
    """
    assessment = _restore_assessment_from_session()

    if assessment is None:
        flash(
            "No questionnaire responses found. Please complete the assessment first.",
            "warning",
        )
        return redirect(url_for("main.questionnaire", reset="1"))

    logger.info(
        "Generating results for system '%s' (framework: %s, score: %.1f).",
        assessment.system_name,
        assessment.framework_id,
        assessment.overall_score,
    )

    try:
        artifacts = generate_all(assessment)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Artifact generation failed on results page.")
        flash(
            f"Document generation failed: {exc}. "
            "Your assessment scores are shown below.",
            "danger",
        )
        # Still render results with scoring data but without artifacts
        return render_template(
            "results.html",
            assessment=assessment,
            assessment_dict=assessment.to_dict(),
            checklist=None,
            ssp_entries=[],
            policy_document=None,
            frameworks=FRAMEWORK_METADATA,
            categories=CATEGORIES,
            title="Assessment Results",
            generation_error=str(exc),
        )

    return render_template(
        "results.html",
        assessment=assessment,
        assessment_dict=assessment.to_dict(),
        checklist=artifacts.checklist,
        checklist_dict=artifacts.checklist.to_dict(),
        ssp_entries=artifacts.ssp_entries,
        ssp_entries_dicts=[e.to_dict() for e in artifacts.ssp_entries],
        policy_document=artifacts.policy_document,
        policy_dict=artifacts.policy_document.to_dict(),
        frameworks=FRAMEWORK_METADATA,
        categories=CATEGORIES,
        title=f"Results — {assessment.system_name}",
        generation_error=None,
    )


# ---------------------------------------------------------------------------
# Route: DOCX download
# ---------------------------------------------------------------------------


@main_bp.route("/download/docx", methods=["GET"])
def download_docx() -> Response:
    """Generate and stream a DOCX file for the current assessment.

    Reads stored responses from the session, re-scores them, generates
    all governance artifacts, builds the DOCX byte stream, and returns
    it as a file download response.

    Returns:
        Flask ``Response`` with DOCX content-type and attachment
        disposition, or a redirect to the questionnaire if no session
        data is present.
    """
    assessment = _restore_assessment_from_session()

    if assessment is None:
        flash(
            "No assessment data found. Please complete the questionnaire first.",
            "warning",
        )
        return redirect(url_for("main.questionnaire", reset="1"))

    logger.info(
        "DOCX download requested for '%s'.",
        assessment.system_name,
    )

    try:
        docx_bytes = export_docx_from_assessment(
            assessment,
            include_checklist=True,
            include_ssp=True,
        )
    except ExportError as exc:
        logger.error("DOCX export failed: %s", exc)
        flash(
            f"DOCX export failed: {exc.reason}. Please try again.",
            "danger",
        )
        return redirect(url_for("main.results"))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during DOCX export.")
        flash(f"Unexpected export error: {exc}", "danger")
        return redirect(url_for("main.results"))

    filename = build_export_filename(
        system_name=assessment.system_name,
        artifact_type="full",
        export_format="docx",
        generated_date=assessment.responses.get(
            "generated_date",
            None,
        ),
    )

    return send_file(
        io.BytesIO(docx_bytes),
        mimetype=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        as_attachment=True,
        download_name=filename,
    )


# ---------------------------------------------------------------------------
# Route: PDF download
# ---------------------------------------------------------------------------


@main_bp.route("/download/pdf", methods=["GET"])
def download_pdf() -> Response:
    """Generate and stream a PDF file for the current assessment.

    Reads stored responses from the session, re-scores them, generates
    all governance artifacts, renders the HTML policy document, converts
    it to PDF via WeasyPrint, and returns it as a file download response.

    An active Flask application context is required for HTML rendering.

    Returns:
        Flask ``Response`` with PDF content-type and attachment
        disposition, or a redirect if no session data is present or
        export fails.
    """
    assessment = _restore_assessment_from_session()

    if assessment is None:
        flash(
            "No assessment data found. Please complete the questionnaire first.",
            "warning",
        )
        return redirect(url_for("main.questionnaire", reset="1"))

    logger.info(
        "PDF download requested for '%s'.",
        assessment.system_name,
    )

    try:
        pdf_bytes = export_pdf_from_assessment(
            assessment,
            include_checklist=True,
            include_ssp=True,
        )
    except ExportError as exc:
        logger.error("PDF export failed: %s", exc)
        flash(
            f"PDF export failed: {exc.reason}. "
            "Try downloading the DOCX version instead.",
            "danger",
        )
        return redirect(url_for("main.results"))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during PDF export.")
        flash(f"Unexpected export error: {exc}", "danger")
        return redirect(url_for("main.results"))

    filename = build_export_filename(
        system_name=assessment.system_name,
        artifact_type="full",
        export_format="pdf",
    )

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


# ---------------------------------------------------------------------------
# Route: About page
# ---------------------------------------------------------------------------


@main_bp.route("/about", methods=["GET"])
def about() -> str:
    """Render the about / framework information page.

    Returns:
        Rendered ``about.html`` template.
    """
    return render_template(
        "about.html",
        frameworks=FRAMEWORK_METADATA,
        categories=CATEGORIES,
        title="About AI Gov Gen",
    )


# ---------------------------------------------------------------------------
# Route: Reset / start over
# ---------------------------------------------------------------------------


@main_bp.route("/reset", methods=["POST", "GET"])
def reset() -> Response:
    """Clear the session and restart the questionnaire wizard.

    Accepts both GET and POST so it can be triggered from a button form
    (POST) or a direct link (GET).

    Returns:
        Redirect to the start of the questionnaire.
    """
    session.clear()
    flash("Assessment cleared. Start a new assessment below.", "info")
    return redirect(url_for("main.questionnaire"))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


@main_bp.app_errorhandler(404)
def not_found(error: Exception) -> tuple[str, int]:
    """Handle 404 Not Found errors.

    Args:
        error: The exception or HTTP error object.

    Returns:
        Tuple of rendered error template string and 404 status code.
    """
    return (
        render_template(
            "error.html",
            error_code=404,
            error_title="Page Not Found",
            error_message=(
                "The page you requested could not be found. "
                "Please check the URL or return to the home page."
            ),
            title="404 — Not Found",
        ),
        404,
    )


@main_bp.app_errorhandler(500)
def internal_error(error: Exception) -> tuple[str, int]:
    """Handle 500 Internal Server Error responses.

    Args:
        error: The exception or HTTP error object.

    Returns:
        Tuple of rendered error template string and 500 status code.
    """
    logger.exception("Internal server error.")
    return (
        render_template(
            "error.html",
            error_code=500,
            error_title="Internal Server Error",
            error_message=(
                "An unexpected error occurred on the server. "
                "The error has been logged. Please try again or "
                "contact support if the problem persists."
            ),
            title="500 — Server Error",
        ),
        500,
    )


@main_bp.app_errorhandler(413)
def request_too_large(error: Exception) -> tuple[str, int]:
    """Handle 413 Request Entity Too Large errors.

    Args:
        error: The exception or HTTP error object.

    Returns:
        Tuple of rendered error template string and 413 status code.
    """
    return (
        render_template(
            "error.html",
            error_code=413,
            error_title="Request Too Large",
            error_message=(
                "The submitted form data exceeded the maximum allowed size (2 MB). "
                "Please reduce the size of your answers and try again."
            ),
            title="413 — Request Too Large",
        ),
        413,
    )


# ---------------------------------------------------------------------------
# Template context processors
# ---------------------------------------------------------------------------


@main_bp.context_processor
def inject_globals() -> dict[str, Any]:
    """Inject common template variables into all Blueprint templates.

    These variables are available in every template rendered by this
    Blueprint without needing to be passed explicitly from each view.

    Returns:
        Dict of template context variables.
    """
    return {
        "app_name": "AI Gov Gen",
        "app_version": "0.1.0",
        "supported_frameworks": current_app.config.get("SUPPORTED_FRAMEWORKS", []),
        "nav_categories": CATEGORIES,
        "wizard_steps": _WIZARD_STEPS,
        "total_wizard_steps": _TOTAL_STEPS,
        "current_session_step": session.get("current_step", 0),
        "has_active_assessment": "responses" in session and bool(session.get("responses")),
    }
