"""Document generation engine for AI Gov Gen.

This module takes a scored :class:`~ai_gov_gen.assessor.AssessmentResult`
and renders three types of governance artifacts using Jinja2 templates:

1. **Governance Checklist** — a prioritised, categorised list of control
   actions with risk-level badges and completion status fields.
2. **SSP Entries** — System Security Plan control entries mapped to NIST AI
   RMF subcategories, CMMC practices, or framework-specific controls.
3. **Policy Document** — a full AI use policy document populated with
   team-specific details drawn from the assessment responses.

All rendering is done through Jinja2 templates loaded from an *in-module*
template string registry (for the structured data artifacts) and from the
Flask application's ``templates/`` folder (for the HTML policy document
used by WeasyPrint).

Public API
----------
:func:`generate_checklist`
    Returns a structured :class:`GovernanceChecklist` object.

:func:`generate_ssp_entries`
    Returns a list of :class:`SSPEntry` objects.

:func:`generate_policy_document`
    Returns a :class:`PolicyDocument` object with fully rendered sections.

:func:`render_policy_html`
    Renders the policy document to an HTML string suitable for
    WeasyPrint PDF generation.  Requires an active Flask application
    context.

:func:`generate_all`
    Convenience wrapper that calls all three generators and returns a
    :class:`GeneratedArtifacts` bundle.

Data structures
---------------
:class:`ChecklistItem`
    A single checklist action item.

:class:`ChecklistCategory`
    A group of checklist items for one risk category.

:class:`GovernanceChecklist`
    The full governance checklist.

:class:`SSPEntry`
    One SSP control entry.

:class:`PolicySection`
    One named section of the policy document.

:class:`PolicyDocument`
    The full AI use policy document.

:class:`GeneratedArtifacts`
    Bundle of all three artifact types.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined

from ai_gov_gen.assessor import AssessmentResult, CategoryResult
from ai_gov_gen.questions import (
    FRAMEWORK_BY_ID,
    get_framework_metadata,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Risk-level helper constants
# ---------------------------------------------------------------------------

#: CSS / badge colour classes for each risk level (Bootstrap 5 colours).
RISK_LEVEL_BADGE_CLASS: dict[str, str] = {
    "Low": "success",
    "Medium": "warning",
    "High": "danger",
    "Critical": "dark",
}

#: Short priority labels aligned to risk levels.
RISK_LEVEL_PRIORITY: dict[str, str] = {
    "Low": "P4 – Informational",
    "Medium": "P3 – Moderate",
    "High": "P2 – High",
    "Critical": "P1 – Critical",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ChecklistItem:
    """A single actionable checklist item.

    Attributes:
        item_id: Unique identifier string, e.g. ``"data-1"``.
        category_id: The risk category this item belongs to.
        category_label: Human-readable category label.
        control_ref: Short control reference string, e.g. ``"NIST-GOVERN-1.1"``.
        action: The specific action the team must take.
        rationale: Why this action is required (links to framework/regulation).
        risk_level: Severity of failing this control (Low/Medium/High/Critical).
        priority: Human-readable priority label.
        badge_class: Bootstrap colour class for the risk badge.
        frameworks: List of framework IDs this item applies to.
        completed: Whether the item has been ticked off (default ``False``).
    """

    item_id: str
    category_id: str
    category_label: str
    control_ref: str
    action: str
    rationale: str
    risk_level: str
    priority: str
    badge_class: str
    frameworks: list[str]
    completed: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary.

        Returns:
            Dict with all public fields.
        """
        return {
            "item_id": self.item_id,
            "category_id": self.category_id,
            "category_label": self.category_label,
            "control_ref": self.control_ref,
            "action": self.action,
            "rationale": self.rationale,
            "risk_level": self.risk_level,
            "priority": self.priority,
            "badge_class": self.badge_class,
            "frameworks": self.frameworks,
            "completed": self.completed,
        }


@dataclass
class ChecklistCategory:
    """A group of checklist items for one risk category.

    Attributes:
        category_id: The risk category identifier.
        category_label: Human-readable category label.
        risk_level: Overall risk level for this category from the assessment.
        normalised_score: Float score in ``[0.0, 100.0]``.
        items: Ordered list of :class:`ChecklistItem` objects.
    """

    category_id: str
    category_label: str
    risk_level: str
    normalised_score: float
    items: list[ChecklistItem] = field(default_factory=list)

    @property
    def item_count(self) -> int:
        """Total number of items in this category."""
        return len(self.items)

    @property
    def critical_item_count(self) -> int:
        """Number of Critical-priority items."""
        return sum(1 for i in self.items if i.risk_level == "Critical")

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "category_id": self.category_id,
            "category_label": self.category_label,
            "risk_level": self.risk_level,
            "normalised_score": self.normalised_score,
            "item_count": self.item_count,
            "critical_item_count": self.critical_item_count,
            "items": [i.to_dict() for i in self.items],
        }


@dataclass
class GovernanceChecklist:
    """The complete AI governance checklist.

    Attributes:
        system_name: Name of the AI system being assessed.
        system_owner: Responsible team or business unit.
        framework_id: Target compliance framework.
        framework_label: Human-readable framework label.
        overall_risk_level: Top-level risk designation.
        overall_score: Float in ``[0.0, 100.0]``.
        generated_date: ISO date string (YYYY-MM-DD).
        categories: Ordered list of :class:`ChecklistCategory` objects.
        warnings: Advisory messages from the scoring engine.
    """

    system_name: str
    system_owner: str
    framework_id: str
    framework_label: str
    overall_risk_level: str
    overall_score: float
    generated_date: str
    categories: list[ChecklistCategory] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_items(self) -> int:
        """Total checklist items across all categories."""
        return sum(c.item_count for c in self.categories)

    @property
    def total_critical_items(self) -> int:
        """Total Critical-priority items."""
        return sum(c.critical_item_count for c in self.categories)

    @property
    def all_items(self) -> list[ChecklistItem]:
        """Flat list of all checklist items."""
        items: list[ChecklistItem] = []
        for cat in self.categories:
            items.extend(cat.items)
        return items

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "system_name": self.system_name,
            "system_owner": self.system_owner,
            "framework_id": self.framework_id,
            "framework_label": self.framework_label,
            "overall_risk_level": self.overall_risk_level,
            "overall_score": self.overall_score,
            "generated_date": self.generated_date,
            "total_items": self.total_items,
            "total_critical_items": self.total_critical_items,
            "warnings": self.warnings,
            "categories": [c.to_dict() for c in self.categories],
        }


@dataclass
class SSPEntry:
    """One System Security Plan control entry for an AI system.

    Attributes:
        entry_id: Unique identifier, e.g. ``"SSP-AI-DATA-001"``.
        control_family: Control family label, e.g. ``"Data Governance"``.
        control_ref: Framework control reference, e.g. ``"NIST AI RMF GOVERN-1.1"``.
        control_name: Short control name.
        control_description: Full description of what the control requires.
        implementation_status: One of ``"Implemented"``, ``"Planned"``,
            ``"Partially Implemented"``, ``"Not Implemented"``.
        implementation_detail: Narrative description of how the control is
            implemented (or will be) for this specific AI system.
        responsible_role: Role or team accountable for the control.
        assessment_finding: What the assessment revealed about this control.
        risk_level: Risk level if this control is not in place.
        remediation_action: Recommended action if not fully implemented.
        evidence_artifacts: List of suggested evidence artefact types.
        frameworks: Framework IDs this entry applies to.
    """

    entry_id: str
    control_family: str
    control_ref: str
    control_name: str
    control_description: str
    implementation_status: str
    implementation_detail: str
    responsible_role: str
    assessment_finding: str
    risk_level: str
    remediation_action: str
    evidence_artifacts: list[str]
    frameworks: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "entry_id": self.entry_id,
            "control_family": self.control_family,
            "control_ref": self.control_ref,
            "control_name": self.control_name,
            "control_description": self.control_description,
            "implementation_status": self.implementation_status,
            "implementation_detail": self.implementation_detail,
            "responsible_role": self.responsible_role,
            "assessment_finding": self.assessment_finding,
            "risk_level": self.risk_level,
            "remediation_action": self.remediation_action,
            "evidence_artifacts": self.evidence_artifacts,
            "frameworks": self.frameworks,
        }


@dataclass
class PolicySection:
    """One named section of the AI use policy document.

    Attributes:
        section_number: Numeric label, e.g. ``"3.2"``.
        title: Section title.
        content: Rendered Markdown/plain-text content of the section.
    """

    section_number: str
    title: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "section_number": self.section_number,
            "title": self.title,
            "content": self.content,
        }


@dataclass
class PolicyDocument:
    """A fully rendered AI use policy document.

    Attributes:
        title: Document title.
        document_id: Unique reference identifier.
        version: Document version string.
        system_name: Name of the AI system this policy covers.
        system_owner: Responsible team or business unit.
        system_purpose: Brief purpose statement.
        framework_id: Target compliance framework.
        framework_label: Human-readable framework label.
        overall_risk_level: Risk posture of the system.
        generated_date: ISO date string.
        sections: Ordered list of :class:`PolicySection` objects.
        warnings: Advisory messages.
    """

    title: str
    document_id: str
    version: str
    system_name: str
    system_owner: str
    system_purpose: str
    framework_id: str
    framework_label: str
    overall_risk_level: str
    generated_date: str
    sections: list[PolicySection] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        """Concatenated plain-text content of all sections."""
        parts: list[str] = [self.title, ""]
        for sec in self.sections:
            parts.append(f"{sec.section_number}  {sec.title}")
            parts.append(sec.content)
            parts.append("")
        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "title": self.title,
            "document_id": self.document_id,
            "version": self.version,
            "system_name": self.system_name,
            "system_owner": self.system_owner,
            "system_purpose": self.system_purpose,
            "framework_id": self.framework_id,
            "framework_label": self.framework_label,
            "overall_risk_level": self.overall_risk_level,
            "generated_date": self.generated_date,
            "sections": [s.to_dict() for s in self.sections],
            "warnings": self.warnings,
        }


@dataclass
class GeneratedArtifacts:
    """Bundle of all three generated governance artifacts.

    Attributes:
        checklist: The :class:`GovernanceChecklist`.
        ssp_entries: List of :class:`SSPEntry` objects.
        policy_document: The :class:`PolicyDocument`.
        assessment: The source :class:`~ai_gov_gen.assessor.AssessmentResult`.
    """

    checklist: GovernanceChecklist
    ssp_entries: list[SSPEntry]
    policy_document: PolicyDocument
    assessment: AssessmentResult

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "checklist": self.checklist.to_dict(),
            "ssp_entries": [e.to_dict() for e in self.ssp_entries],
            "policy_document": self.policy_document.to_dict(),
            "assessment": self.assessment.to_dict(),
        }


# ---------------------------------------------------------------------------
# Internal Jinja2 environment (standalone, no Flask required)
# ---------------------------------------------------------------------------

_JINJA_ENV = Environment(
    loader=BaseLoader(),
    autoescape=False,
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _render(template_string: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 template string with the given context.

    Args:
        template_string: Jinja2 template source.
        context: Variable namespace for the template.

    Returns:
        Rendered string.
    """
    tmpl = _JINJA_ENV.from_string(template_string)
    return tmpl.render(**context)


# ---------------------------------------------------------------------------
# Checklist control library
# ---------------------------------------------------------------------------
# Each entry describes a potential checklist item.  Items are selected and
# their risk levels determined at runtime based on the assessment findings.
#
# Schema:
#   category_id     — which risk category
#   control_ref     — short framework reference
#   action          — what must be done
#   rationale       — why (regulatory / framework source)
#   base_risk_level — risk level if this gap is present
#   triggered_by    — question ids whose answers may trigger this item
#                     (empty list means always included)
#   trigger_values  — option values that trigger this item (empty = always)
#   frameworks      — applicable framework ids
# ---------------------------------------------------------------------------

_CHECKLIST_LIBRARY: list[dict[str, Any]] = [
    # ------------------------------------------------------------------ DATA
    {
        "category_id": "data",
        "control_ref": "NIST-AI-MAP-1.1",
        "action": "Establish and maintain a data provenance and lineage register for all training and inference datasets.",
        "rationale": "NIST AI RMF MAP 1.1 requires context and risk characterisation of AI data. Undocumented data origins undermine audit and bias investigation.",
        "base_risk_level": "High",
        "triggered_by": ["data_02"],
        "trigger_values": ["partial", "no"],
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
    },
    {
        "category_id": "data",
        "control_ref": "GDPR-Art5 / NIST-AI-GOV-1.2",
        "action": "Document the lawful basis for processing personal data and obtain explicit consent where required.",
        "rationale": "GDPR Article 5 and Article 6 require a documented legal basis for all personal data processing. Undocumented consent exposes the organisation to regulatory fines.",
        "base_risk_level": "Critical",
        "triggered_by": ["data_03"],
        "trigger_values": ["yes_assumed", "uncertain", "no"],
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
    },
    {
        "category_id": "data",
        "control_ref": "NIST-AI-MEASURE-2.5",
        "action": "Implement automated data quality controls including schema validation, completeness checks, and bias scanning before data enters the AI pipeline.",
        "rationale": "NIST AI RMF MEASURE 2.5 requires evaluation of data quality for AI trustworthiness. Poor data quality amplifies bias and degrades model reliability.",
        "base_risk_level": "High",
        "triggered_by": ["data_04"],
        "trigger_values": ["none"],
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
    },
    {
        "category_id": "data",
        "control_ref": "CMMC-SC.L2-3.13.10 / NIST-AI-MANAGE-1.3",
        "action": "Enable encryption at rest and in transit for all AI training data, inference inputs, model weights, and outputs containing sensitive information.",
        "rationale": "CMMC Level 2 SC.L2-3.13.10 mandates encryption for CUI. Unencrypted AI data is vulnerable to interception and exfiltration.",
        "base_risk_level": "High",
        "triggered_by": ["data_05"],
        "trigger_values": ["transit_only", "rest_only", "neither"],
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
    },
    {
        "category_id": "data",
        "control_ref": "GDPR-Art5e / NIST-AI-GOV-1.4",
        "action": "Define and technically enforce data retention and deletion schedules for all AI training and inference data.",
        "rationale": "GDPR Article 5(e) requires storage limitation. Retaining data beyond its necessary period increases breach risk and regulatory exposure.",
        "base_risk_level": "Medium",
        "triggered_by": ["data_06"],
        "trigger_values": ["yes_manual", "partial", "no"],
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
    },
    {
        "category_id": "data",
        "control_ref": "NIST-AI-MAP-2.3",
        "action": "Apply equivalent data governance controls to all third-party and vendor-supplied datasets including provenance review, bias scanning, and license verification.",
        "rationale": "Third-party data introduces supply-chain risk. NIST AI RMF MAP 2.3 requires identification of risks from external AI components and data sources.",
        "base_risk_level": "High",
        "triggered_by": ["data_07"],
        "trigger_values": ["partial", "no"],
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "enterprise"],
    },
    {
        "category_id": "data",
        "control_ref": "GDPR-Art35 / HKS-Privacy",
        "action": "Complete a Data Protection Impact Assessment (DPIA) or Privacy Impact Assessment (PIA) before the AI system processes personal data at scale.",
        "rationale": "GDPR Article 35 mandates a DPIA for high-risk processing. A PIA identifies and mitigates privacy risks before harm occurs.",
        "base_risk_level": "Critical",
        "triggered_by": ["data_08"],
        "trigger_values": ["in_progress", "no"],
        "frameworks": ["hks", "lloyds", "enterprise"],
    },
    {
        "category_id": "data",
        "control_ref": "NIST-AI-GOV-1.1",
        "action": "Conduct a PII / sensitive data inventory and classify all data assets processed by the AI system according to sensitivity and regulatory category.",
        "rationale": "Understanding what sensitive data the AI system touches is the foundation of effective data governance and is required by most AI risk frameworks.",
        "base_risk_level": "High",
        "triggered_by": ["data_01"],
        "trigger_values": ["pii", "phi", "cui", "biometric"],
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
    },
    # ----------------------------------------------------------------- MODEL
    {
        "category_id": "model",
        "control_ref": "NIST-AI-MEASURE-2.7",
        "action": "Conduct comprehensive bias and fairness testing across all relevant demographic sub-groups before deployment and after any model update.",
        "rationale": "NIST AI RMF MEASURE 2.7 requires evaluation of AI bias. Untested bias can cause discriminatory outcomes and regulatory violations.",
        "base_risk_level": "Critical",
        "triggered_by": ["model_03"],
        "trigger_values": ["partial", "planned", "no"],
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
    },
    {
        "category_id": "model",
        "control_ref": "EU-AI-Act-Art13 / NIST-AI-MEASURE-2.6",
        "action": "Implement post-hoc explainability tooling (e.g., SHAP, LIME) or adopt an inherently interpretable model architecture to support audit and user contestation rights.",
        "rationale": "EU AI Act Article 13 requires transparency. GDPR Article 22 grants the right to meaningful explanation for automated decisions.",
        "base_risk_level": "High",
        "triggered_by": ["model_04"],
        "trigger_values": ["partial", "no"],
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
    },
    {
        "category_id": "model",
        "control_ref": "NIST-AI-MEASURE-2.2",
        "action": "Establish an independent model validation process conducted by a team separate from the model development team, including out-of-time and adversarial testing.",
        "rationale": "Independent validation catches errors and biases that development teams miss. NIST AI RMF MEASURE 2.2 requires testing and evaluation against defined metrics.",
        "base_risk_level": "High",
        "triggered_by": ["model_05"],
        "trigger_values": ["internal_only", "ad_hoc", "no"],
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
    },
    {
        "category_id": "model",
        "control_ref": "NIST-AI-GOV-1.3",
        "action": "Implement a model registry that records version history, training metadata, performance benchmarks, bias test results, and approval sign-offs for each production model.",
        "rationale": "A model registry is essential for reproducibility, incident investigation, and demonstrating compliance. NIST AI RMF GOVERN 1.3 requires documented AI lifecycle practices.",
        "base_risk_level": "Medium",
        "triggered_by": ["model_06"],
        "trigger_values": ["version_control", "partial", "no"],
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
    },
    {
        "category_id": "model",
        "control_ref": "NIST-AI-MEASURE-2.9",
        "action": "Perform adversarial robustness testing and prompt injection red-teaming before deployment, and schedule regular re-testing after model updates.",
        "rationale": "NIST AI RMF MEASURE 2.9 requires evaluation of AI resilience. Prompt injection and adversarial inputs are critical attack vectors for LLMs and ML systems.",
        "base_risk_level": "High",
        "triggered_by": ["model_07"],
        "trigger_values": ["basic", "planned", "no"],
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "enterprise"],
    },
    {
        "category_id": "model",
        "control_ref": "EU-AI-Act-Art14 / NIST-AI-MANAGE-4.1",
        "action": "Mandate human-in-the-loop review for all high-stakes AI-assisted decisions and document the human oversight procedure in the system operating procedures.",
        "rationale": "EU AI Act Article 14 requires human oversight for high-risk AI systems. Fully automated high-stakes decisions carry significant legal and reputational risk.",
        "base_risk_level": "Critical",
        "triggered_by": ["model_08"],
        "trigger_values": ["optional", "no"],
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
    },
    {
        "category_id": "model",
        "control_ref": "NIST-AI-MAP-1.5",
        "action": "Document and contractually manage supply-chain risks for third-party or foundation model components, including their training data, intended use, and known limitations.",
        "rationale": "Third-party and foundation models carry hidden biases and capability limitations. NIST AI RMF MAP 1.5 requires understanding of AI supply chain context.",
        "base_risk_level": "High",
        "triggered_by": ["model_01"],
        "trigger_values": ["custom_external", "foundation_finetuned", "foundation_vanilla", "saas_api"],
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
    },
    # ------------------------------------------------------------------- OPS
    {
        "category_id": "ops",
        "control_ref": "CMMC-AC.L2-3.1.1 / NIST-AI-MANAGE-2.2",
        "action": "Implement and enforce role-based access control (RBAC) with least-privilege principles across all AI system components including training infrastructure, model serving endpoints, and data stores.",
        "rationale": "CMMC AC.L2-3.1.1 and NIST SP 800-171 require limiting system access to authorised users with roles consistent with their job functions.",
        "base_risk_level": "High",
        "triggered_by": ["ops_02"],
        "trigger_values": ["partial", "basic", "no"],
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
    },
    {
        "category_id": "ops",
        "control_ref": "CMMC-IA.L2-3.5.3",
        "action": "Enforce multi-factor authentication (MFA) for all accounts with access to AI system components, with particular priority on privileged and administrative accounts.",
        "rationale": "CMMC Level 2 IA.L2-3.5.3 mandates MFA for network access using privileged accounts. MFA significantly reduces credential-based attack risk.",
        "base_risk_level": "High",
        "triggered_by": ["ops_03"],
        "trigger_values": ["privileged_only", "optional", "no"],
        "frameworks": ["cmmc_l2", "lloyds", "enterprise"],
    },
    {
        "category_id": "ops",
        "control_ref": "NIST-AI-MANAGE-4.2",
        "action": "Deploy runtime monitoring covering model performance degradation, input data drift, output distribution shifts, and security anomalies, with automated alerting thresholds.",
        "rationale": "NIST AI RMF MANAGE 4.2 requires ongoing monitoring of deployed AI systems to detect performance issues and emergent risks.",
        "base_risk_level": "High",
        "triggered_by": ["ops_04"],
        "trigger_values": ["none"],
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
    },
    {
        "category_id": "ops",
        "control_ref": "NIST-AI-MANAGE-4.3",
        "action": "Develop, approve, and regularly test an AI-specific incident response plan covering model poisoning, harmful outputs, adversarial attacks, and discriminatory decision events.",
        "rationale": "NIST AI RMF MANAGE 4.3 requires response plans for AI incidents. AI failure modes differ from traditional IT incidents and require purpose-built procedures.",
        "base_risk_level": "High",
        "triggered_by": ["ops_05"],
        "trigger_values": ["general_ir", "draft", "no"],
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
    },
    {
        "category_id": "ops",
        "control_ref": "NIST-AI-MANAGE-4.4",
        "action": "Implement and periodically test a model kill-switch and rollback capability with a documented Recovery Time Objective (RTO) of no more than 4 hours for critical systems.",
        "rationale": "NIST AI RMF MANAGE 4.4 requires deactivation and recovery capabilities for AI systems. Rapid rollback limits harm from defective model deployments.",
        "base_risk_level": "High",
        "triggered_by": ["ops_06"],
        "trigger_values": ["untested", "no"],
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "enterprise"],
    },
    {
        "category_id": "ops",
        "control_ref": "NIST-AI-MAP-1.6 / CMMC-CM.L2-3.4.1",
        "action": "Maintain a Software Bill of Materials (SBOM) for all AI dependencies, implement automated vulnerability scanning, and cryptographically verify model weights.",
        "rationale": "CMMC CM.L2-3.4.1 requires a baseline inventory of AI system components. Supply-chain attacks via compromised ML dependencies and model weights are an emerging threat.",
        "base_risk_level": "Medium",
        "triggered_by": ["ops_07"],
        "trigger_values": ["none"],
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "enterprise"],
    },
    {
        "category_id": "ops",
        "control_ref": "NIST-AI-MANAGE-1.1",
        "action": "Implement a formal gated change management process for all AI model updates, requiring documented testing results, bias re-evaluation, and explicit approval before production promotion.",
        "rationale": "Uncontrolled model updates introduce regression, bias, and security risk. NIST AI RMF MANAGE 1.1 requires AI risk management practices to be integrated into change control.",
        "base_risk_level": "High",
        "triggered_by": ["ops_08"],
        "trigger_values": ["informal", "ci_cd_no_gate", "no"],
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
    },
    # ------------------------------------------------------------ COMPLIANCE
    {
        "category_id": "compliance",
        "control_ref": "NIST-AI-GOV-1.1",
        "action": "Establish or designate an AI governance committee or Chief AI Officer (CAIO) role with formal authority over AI deployment decisions, risk acceptance, and policy.",
        "rationale": "NIST AI RMF GOVERN 1.1 requires organisational accountability for AI risk. Without clear ownership, AI risks go unmanaged and accountability is diffused.",
        "base_risk_level": "Critical",
        "triggered_by": ["comp_02"],
        "trigger_values": ["existing_role", "informal", "no"],
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
    },
    {
        "category_id": "compliance",
        "control_ref": "NIST-AI-GOV-1.2",
        "action": "Publish a formal AI use policy covering acceptable use, prohibited applications, data handling requirements, and employee responsibilities, and obtain signed acknowledgements from all relevant staff.",
        "rationale": "NIST AI RMF GOVERN 1.2 requires policies and procedures for responsible AI deployment. An unacknowledged policy cannot be enforced.",
        "base_risk_level": "High",
        "triggered_by": ["comp_03"],
        "trigger_values": ["published_no_ack", "draft", "no"],
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
    },
    {
        "category_id": "compliance",
        "control_ref": "NIST-AI-MAP-3.2",
        "action": "Extend the organisation's vendor risk management programme to all third-party AI vendors, including security assessments, contractual AI-specific clauses, and sub-processor reviews.",
        "rationale": "Third-party AI vendors handle sensitive data and provide core decision logic. NIST AI RMF MAP 3.2 requires assessment of AI supply chain entities.",
        "base_risk_level": "High",
        "triggered_by": ["comp_04"],
        "trigger_values": ["partial", "no"],
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
    },
    {
        "category_id": "compliance",
        "control_ref": "GDPR-Art22 / EU-AI-Act-Art85",
        "action": "Operationalise a contestation and redress mechanism so that individuals affected by AI-assisted decisions can meaningfully challenge outcomes and seek human review.",
        "rationale": "GDPR Article 22 and EU AI Act Article 85 establish rights to explanation and redress for automated decision-making. A policy statement alone is insufficient.",
        "base_risk_level": "High",
        "triggered_by": ["comp_05"],
        "trigger_values": ["policy_only", "no"],
        "frameworks": ["hks", "lloyds", "enterprise"],
    },
    {
        "category_id": "compliance",
        "control_ref": "NIST-AI-GOV-4.1",
        "action": "Establish a regular audit cycle (at minimum annual internal and biennial external) covering AI governance controls, model performance, bias metrics, and policy compliance.",
        "rationale": "NIST AI RMF GOVERN 4.1 requires organisational review of AI risks over time. Regular audits verify control effectiveness and identify emerging risks.",
        "base_risk_level": "Medium",
        "triggered_by": ["comp_06"],
        "trigger_values": ["ad_hoc", "no"],
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
    },
    {
        "category_id": "compliance",
        "control_ref": "CMMC-AT.L2-3.2.1 / NIST-AI-GOV-5.1",
        "action": "Deliver role-specific AI risk and governance training to all staff who build, deploy, procure, or oversee AI systems, with annual refreshers and competency verification.",
        "rationale": "CMMC AT.L2-3.2.1 requires security awareness training. NIST AI RMF GOVERN 5.1 requires AI risk literacy across the organisation.",
        "base_risk_level": "Medium",
        "triggered_by": ["comp_07"],
        "trigger_values": ["general", "ad_hoc", "no"],
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
    },
    {
        "category_id": "compliance",
        "control_ref": "CMMC-CA.L2-3.12.4",
        "action": "Document the AI system fully in the organisation's System Security Plan (SSP) including control mappings, data flows, boundary diagrams, and responsible roles.",
        "rationale": "CMMC CA.L2-3.12.4 requires an SSP covering all systems in scope. AI systems not documented in the SSP are outside the assessed security boundary.",
        "base_risk_level": "High",
        "triggered_by": ["comp_08"],
        "trigger_values": ["partially", "not_included", "no_ssp"],
        "frameworks": ["cmmc_l2", "enterprise"],
    },
]


# ---------------------------------------------------------------------------
# SSP control template library
# ---------------------------------------------------------------------------
# Controls to include in the SSP output, with Jinja2 template strings for
# implementation_detail and assessment_finding that accept the assessment context.

_SSP_CONTROL_TEMPLATES: list[dict[str, Any]] = [
    {
        "entry_id_prefix": "SSP-AI-DATA",
        "seq": 1,
        "control_family": "Data Governance",
        "control_ref": "NIST AI RMF GOVERN-1.1 / MAP-1.1",
        "control_name": "AI Data Classification and Provenance",
        "control_description": (
            "Establish and maintain comprehensive records of all data types processed by "
            "the AI system, including their sensitivity classification, origin, lineage, "
            "and applicable legal basis for processing."
        ),
        "responsible_role": "Data Governance Lead / DPO",
        "evidence_artifacts": [
            "Data inventory register",
            "Data lineage diagrams",
            "DPIA / PIA report",
            "Legal basis documentation",
        ],
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
        "finding_question": "data_02",
        "finding_map": {
            "yes_automated": "Automated data lineage tracking is in place. Control is fully implemented.",
            "yes_manual": "Manual documentation exists but automated lineage is absent. Control is partially implemented.",
            "partial": "Only some datasets are documented. Control requires remediation.",
            "no": "No data provenance tracking exists. Control is not implemented — immediate remediation required.",
        },
        "status_map": {
            "yes_automated": "Implemented",
            "yes_manual": "Partially Implemented",
            "partial": "Partially Implemented",
            "no": "Not Implemented",
        },
    },
    {
        "entry_id_prefix": "SSP-AI-DATA",
        "seq": 2,
        "control_family": "Data Governance",
        "control_ref": "NIST AI RMF MANAGE-1.3 / CMMC SC.L2-3.13.10",
        "control_name": "AI Data Encryption",
        "control_description": (
            "Ensure all AI system data assets — including training datasets, inference "
            "inputs, model weights, and inference outputs — are encrypted both at rest "
            "and in transit using approved cryptographic standards."
        ),
        "responsible_role": "Information Security Officer",
        "evidence_artifacts": [
            "Encryption configuration records",
            "TLS certificate inventory",
            "Key management procedure",
            "Security architecture diagram",
        ],
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
        "finding_question": "data_05",
        "finding_map": {
            "both": "Encryption is implemented at rest and in transit. Control is fully implemented.",
            "transit_only": "Encryption in transit only; at-rest encryption is absent. Control is partially implemented.",
            "rest_only": "Encryption at rest only; in-transit encryption is absent. Control is partially implemented.",
            "neither": "No encryption in place. Control is not implemented — critical remediation required.",
            "not_applicable": "No sensitive data processed; encryption control is not applicable.",
        },
        "status_map": {
            "both": "Implemented",
            "transit_only": "Partially Implemented",
            "rest_only": "Partially Implemented",
            "neither": "Not Implemented",
            "not_applicable": "Not Applicable",
        },
    },
    {
        "entry_id_prefix": "SSP-AI-MODEL",
        "seq": 1,
        "control_family": "Model Risk",
        "control_ref": "NIST AI RMF MEASURE-2.7 / HKS Fairness",
        "control_name": "AI Bias and Fairness Testing",
        "control_description": (
            "Conduct formal bias and fairness evaluations across all relevant demographic "
            "sub-groups before initial deployment and after every material model change. "
            "Document results and remediation actions in the model registry."
        ),
        "responsible_role": "ML Engineering / Model Risk Team",
        "evidence_artifacts": [
            "Bias testing methodology document",
            "Fairness metrics report",
            "Sub-group performance analysis",
            "Remediation action log",
        ],
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
        "finding_question": "model_03",
        "finding_map": {
            "comprehensive": "Comprehensive bias testing across all relevant sub-groups is in place. Control is fully implemented.",
            "partial": "Only some sub-groups have been tested. Control is partially implemented.",
            "planned": "Bias testing is planned but not yet conducted. Control is not implemented.",
            "no": "No bias testing has been conducted. Control is not implemented — immediate remediation required.",
            "not_applicable": "Model does not operate on personal data; bias testing is not applicable.",
        },
        "status_map": {
            "comprehensive": "Implemented",
            "partial": "Partially Implemented",
            "planned": "Planned",
            "no": "Not Implemented",
            "not_applicable": "Not Applicable",
        },
    },
    {
        "entry_id_prefix": "SSP-AI-MODEL",
        "seq": 2,
        "control_family": "Model Risk",
        "control_ref": "NIST AI RMF MEASURE-2.6 / EU AI Act Art.13",
        "control_name": "Model Explainability and Interpretability",
        "control_description": (
            "Ensure that predictions and recommendations generated by the AI system can "
            "be explained to end users, oversight teams, and regulators in a meaningful "
            "and accessible manner, supporting the right to contestation."
        ),
        "responsible_role": "ML Engineering / Compliance Officer",
        "evidence_artifacts": [
            "Explainability methodology documentation",
            "XAI tool configuration and output examples",
            "User-facing explanation interface design",
            "Audit trail of explanations provided",
        ],
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
        "finding_question": "model_04",
        "finding_map": {
            "inherently_interpretable": "Model is inherently interpretable. Control is fully implemented.",
            "xai_tooling": "Post-hoc XAI tooling is deployed. Control is fully implemented.",
            "partial": "Some explanation capability exists but coverage is incomplete. Control is partially implemented.",
            "no": "No explainability capability exists. Control is not implemented — remediation required.",
        },
        "status_map": {
            "inherently_interpretable": "Implemented",
            "xai_tooling": "Implemented",
            "partial": "Partially Implemented",
            "no": "Not Implemented",
        },
    },
    {
        "entry_id_prefix": "SSP-AI-OPS",
        "seq": 1,
        "control_family": "Operational Security",
        "control_ref": "CMMC AC.L2-3.1.1 / NIST SP 800-171 3.1.1",
        "control_name": "AI System Access Control",
        "control_description": (
            "Implement role-based access control with least-privilege enforcement for all "
            "AI system components, including training environments, model serving "
            "infrastructure, inference APIs, and associated data stores."
        ),
        "responsible_role": "Information Security Officer / Platform Engineering",
        "evidence_artifacts": [
            "RBAC policy and role matrix",
            "Access control configuration screenshots",
            "Privileged access review records",
            "Identity and access management (IAM) audit logs",
        ],
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
        "finding_question": "ops_02",
        "finding_map": {
            "comprehensive": "RBAC with least-privilege is enforced across all components. Control is fully implemented.",
            "partial": "RBAC is applied to some but not all components. Control is partially implemented.",
            "basic": "Only password-based controls exist with no role separation. Control requires significant remediation.",
            "no": "No access controls are in place. Control is not implemented — critical remediation required.",
        },
        "status_map": {
            "comprehensive": "Implemented",
            "partial": "Partially Implemented",
            "basic": "Partially Implemented",
            "no": "Not Implemented",
        },
    },
    {
        "entry_id_prefix": "SSP-AI-OPS",
        "seq": 2,
        "control_family": "Operational Security",
        "control_ref": "NIST AI RMF MANAGE-4.2",
        "control_name": "AI Runtime Monitoring and Alerting",
        "control_description": (
            "Deploy continuous monitoring of the AI system covering model performance "
            "degradation, input data drift, output anomalies, and security events, with "
            "automated alerting thresholds and defined escalation paths."
        ),
        "responsible_role": "MLOps / Security Operations Center",
        "evidence_artifacts": [
            "Monitoring dashboard configuration",
            "Alert threshold definitions",
            "Incident escalation runbook",
            "Sample monitoring reports",
        ],
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
        "finding_question": "ops_04",
        "finding_map": {
            "performance_metrics": "Model performance monitoring is in place. Review coverage for data drift and security alerting.",
            "data_drift": "Data drift monitoring is in place. Verify security alerting and output distribution monitoring.",
            "output_distribution": "Output distribution monitoring is in place. Verify performance and security coverage.",
            "security_alerts": "Security alerting is in place. Verify ML-specific performance and drift monitoring.",
            "audit_logs": "Audit logging is in place. Verify real-time performance, drift, and security monitoring.",
            "none": "No runtime monitoring is in place. Control is not implemented — immediate remediation required.",
        },
        "status_map": {
            "performance_metrics": "Partially Implemented",
            "data_drift": "Partially Implemented",
            "output_distribution": "Partially Implemented",
            "security_alerts": "Partially Implemented",
            "audit_logs": "Partially Implemented",
            "none": "Not Implemented",
        },
    },
    {
        "entry_id_prefix": "SSP-AI-COMP",
        "seq": 1,
        "control_family": "Compliance and Governance",
        "control_ref": "NIST AI RMF GOVERN-1.1",
        "control_name": "AI Governance Structure",
        "control_description": (
            "Establish a formal AI governance structure with defined roles, "
            "responsibilities, and authority for AI risk management decisions, "
            "including a designated AI governance committee or equivalent role."
        ),
        "responsible_role": "Chief Information Officer / Chief Risk Officer",
        "evidence_artifacts": [
            "AI governance committee charter",
            "RACI matrix for AI decisions",
            "Meeting minutes and decision logs",
            "AI risk acceptance authority documentation",
        ],
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
        "finding_question": "comp_02",
        "finding_map": {
            "dedicated_committee": "A dedicated AI governance committee with C-suite sponsorship is in place. Control is fully implemented.",
            "existing_role": "Existing risk or compliance role covers AI governance. Consider a dedicated AI governance structure as the programme matures.",
            "informal": "Governance is informal with no designated role. Control requires remediation.",
            "no": "No AI governance role or committee exists. Control is not implemented — immediate remediation required.",
        },
        "status_map": {
            "dedicated_committee": "Implemented",
            "existing_role": "Partially Implemented",
            "informal": "Partially Implemented",
            "no": "Not Implemented",
        },
    },
    {
        "entry_id_prefix": "SSP-AI-COMP",
        "seq": 2,
        "control_family": "Compliance and Governance",
        "control_ref": "CMMC CA.L2-3.12.4",
        "control_name": "SSP Documentation of AI System",
        "control_description": (
            "Document the AI system within the organisation's System Security Plan "
            "including system boundaries, data flows, applicable security controls, "
            "responsible roles, and interconnections with other information systems."
        ),
        "responsible_role": "Information Systems Security Officer (ISSO)",
        "evidence_artifacts": [
            "Current SSP document with AI system section",
            "System boundary diagram",
            "Data flow diagrams",
            "Security control mapping table",
        ],
        "frameworks": ["cmmc_l2", "enterprise"],
        "finding_question": "comp_08",
        "finding_map": {
            "fully_documented": "AI system is fully documented in the current SSP. Control is fully implemented.",
            "partially": "AI system is only partially documented in the SSP. Control requires completion.",
            "not_included": "AI system is not yet included in the SSP. Control is not implemented.",
            "no_ssp": "No SSP exists for this organisation. Control is not implemented — foundational remediation required.",
        },
        "status_map": {
            "fully_documented": "Implemented",
            "partially": "Partially Implemented",
            "not_included": "Not Implemented",
            "no_ssp": "Not Implemented",
        },
    },
]


# ---------------------------------------------------------------------------
# Policy document section templates
# ---------------------------------------------------------------------------

_POLICY_SECTION_TEMPLATES: list[dict[str, str]] = [
    {
        "section_number": "1",
        "title": "Purpose and Scope",
        "template": (
            "This AI Use Policy ('Policy') governs the deployment, operation, and "
            "oversight of the AI system known as **{{ system_name }}**, operated by "
            "**{{ system_owner }}**. The system is described as follows:\n\n"
            "> {{ system_purpose }}\n\n"
            "This Policy applies to all personnel who design, develop, deploy, procure, "
            "use, or oversee the above AI system. It has been prepared in alignment with "
            "the **{{ framework_label }}** and reflects the risk posture identified "
            "through a structured AI risk assessment conducted on {{ generated_date }}.\n\n"
            "The overall AI deployment risk level for {{ system_name }} has been assessed "
            "as: **{{ overall_risk_level }}** (score: {{ overall_score | round(1) }} / 100)."
        ),
    },
    {
        "section_number": "2",
        "title": "Definitions",
        "template": (
            "**Artificial Intelligence (AI) System**: Any machine-based system that can, "
            "for a given set of objectives, make predictions, recommendations, or decisions "
            "influencing real or virtual environments (OECD definition).\n\n"
            "**AI Risk**: The potential for harm, disruption, or adverse outcomes arising "
            "from the development, deployment, or use of AI systems.\n\n"
            "**Model**: A computational artefact trained on data to perform a specific task, "
            "including machine learning models, foundation models, and large language models.\n\n"
            "**Training Data**: Data used to develop, optimise, or fine-tune the AI model.\n\n"
            "**Inference**: The process of using a trained model to generate outputs "
            "(predictions, decisions, recommendations) from new input data.\n\n"
            "**Human-in-the-Loop (HITL)**: A design pattern in which human judgement is "
            "required before or after AI-generated outputs are acted upon.\n\n"
            "**Compliance Framework**: {{ framework_label }} — "
            "{{ framework_description }}\n\n"
            "**System Owner**: {{ system_owner }} — the team or business unit accountable "
            "for the AI system covered by this Policy."
        ),
    },
    {
        "section_number": "3",
        "title": "Governance and Accountability",
        "template": (
            "**3.1 System Ownership**\n\n"
            "{{ system_owner }} is designated as the System Owner for {{ system_name }} "
            "and is responsible for ensuring that the system is operated in accordance "
            "with this Policy, applicable laws, and the {{ framework_label }}.\n\n"
            "**3.2 AI Governance Authority**\n\n"
            "All material changes to the AI system — including model updates, significant "
            "changes to training data, deployment environment changes, or expansions of use "
            "case scope — must be reviewed and approved by the designated AI governance "
            "authority within the organisation before implementation.\n\n"
            "**3.3 Risk Acceptance**\n\n"
            "Residual AI risks that cannot be fully mitigated must be formally accepted by "
            "an accountable executive (at minimum a Director or equivalent). Risk acceptance "
            "decisions must be documented and reviewed at least annually.\n\n"
            "**3.4 Policy Review Cycle**\n\n"
            "This Policy must be reviewed at least annually, or following any material "
            "change to the AI system, applicable regulations, or the organisation's risk "
            "appetite. The next scheduled review date is twelve months from "
            "{{ generated_date }}."
        ),
    },
    {
        "section_number": "4",
        "title": "Data Governance Requirements",
        "template": (
            "**4.1 Data Classification**\n\n"
            "All data processed by {{ system_name }} must be classified according to the "
            "organisation's data classification policy. The data risk level for this system "
            "is assessed as: **{{ data_risk_level }}**.\n\n"
            "**4.2 Lawful Basis for Processing**\n\n"
            "Where {{ system_name }} processes personal data, {{ system_owner }} must "
            "document and maintain the lawful basis for processing in accordance with "
            "applicable privacy regulations. Processing must not commence or continue "
            "without a documented legal basis.\n\n"
            "**4.3 Data Quality**\n\n"
            "All training and inference data must pass defined quality gates before use, "
            "including schema validation, completeness checks, and bias scanning where "
            "applicable. Data quality results must be recorded in the system's audit log.\n\n"
            "**4.4 Data Retention and Deletion**\n\n"
            "Training data, inference logs, and model outputs must be retained only for "
            "the minimum period necessary to fulfil their purpose. A documented retention "
            "schedule must be maintained and technically enforced.\n\n"
            "**4.5 Encryption**\n\n"
            "All sensitive data processed by {{ system_name }} must be encrypted at rest "
            "using AES-256 or equivalent, and in transit using TLS 1.2 or higher. "
            "Encryption key management must follow the organisation's key management policy."
        ),
    },
    {
        "section_number": "5",
        "title": "Model Risk Management",
        "template": (
            "**5.1 Model Development and Validation**\n\n"
            "All models deployed as part of {{ system_name }} must undergo formal "
            "validation before production deployment. Where feasible, validation must be "
            "conducted by a team independent from the development team. Validation results "
            "must be recorded in the model registry.\n\n"
            "The model risk level for this system is assessed as: **{{ model_risk_level }}**.\n\n"
            "**5.2 Bias and Fairness**\n\n"
            "Models that produce outputs affecting individuals must be tested for bias "
            "across all relevant demographic sub-groups before deployment. Bias test "
            "results, including any identified disparities and remediation actions, must "
            "be documented and reviewed by the AI governance authority.\n\n"
            "**5.3 Explainability**\n\n"
            "Where {{ system_name }} supports decisions that affect individuals, the "
            "system must be capable of providing meaningful explanations of its outputs "
            "to authorised requestors. Explanation capability must be verified as part of "
            "pre-deployment testing.\n\n"
            "**5.4 Human Oversight**\n\n"
            "For high-stakes outputs, a human-in-the-loop review process must be "
            "maintained. The specific oversight procedure for {{ system_name }} is "
            "documented in the system's operating procedures and must be followed by "
            "all users.\n\n"
            "**5.5 Model Registry**\n\n"
            "A model registry entry must be maintained for every version of every model "
            "deployed within {{ system_name }}. The registry must capture: model version, "
            "training data reference, performance metrics, bias test results, "
            "validation sign-off, and deployment date."
        ),
    },
    {
        "section_number": "6",
        "title": "Operational Security Controls",
        "template": (
            "**6.1 Access Control**\n\n"
            "Access to {{ system_name }} and its supporting infrastructure must be "
            "controlled on the principle of least privilege. Role-based access control "
            "(RBAC) must be implemented and reviewed quarterly. All privileged accounts "
            "must use multi-factor authentication (MFA).\n\n"
            "The operational security risk level for this system is assessed as: "
            "**{{ ops_risk_level }}**.\n\n"
            "**6.2 Runtime Monitoring**\n\n"
            "{{ system_name }} must be monitored continuously for model performance "
            "degradation, input data drift, anomalous output distributions, and security "
            "events. Alerting thresholds must be defined, documented, and reviewed "
            "at least annually.\n\n"
            "**6.3 Incident Response**\n\n"
            "{{ system_owner }} must maintain an incident response plan that explicitly "
            "addresses AI-specific failure modes including model poisoning, adversarial "
            "inputs, harmful outputs, and discriminatory decisions. The plan must be "
            "tested at least annually through tabletop exercises or simulations.\n\n"
            "**6.4 Rollback and Recovery**\n\n"
            "A tested rollback capability must be in place for {{ system_name }}, "
            "enabling rapid reversion to the previous known-good model version. The "
            "Recovery Time Objective (RTO) and Recovery Point Objective (RPO) for the "
            "system must be documented and tested.\n\n"
            "**6.5 Change Management**\n\n"
            "All changes to the AI system — including model updates, retraining, "
            "configuration changes, and dependency updates — must follow the organisation's "
            "change management process. A formal approval gate is required before "
            "any change is promoted to production."
        ),
    },
    {
        "section_number": "7",
        "title": "Compliance and Audit",
        "template": (
            "**7.1 Regulatory Compliance**\n\n"
            "{{ system_owner }} is responsible for ensuring that {{ system_name }} "
            "complies with all applicable regulations and standards. This assessment "
            "has been aligned to the **{{ framework_label }}**.\n\n"
            "The compliance risk level for this system is assessed as: "
            "**{{ compliance_risk_level }}**.\n\n"
            "**7.2 Audit Trail**\n\n"
            "Comprehensive audit logs must be maintained for all material AI system "
            "events, including: model training and deployment events, data access and "
            "processing events, inference requests and outputs for high-stakes decisions, "
            "access control changes, and incident reports. Logs must be retained for "
            "a minimum of three years unless a shorter period is required by applicable law.\n\n"
            "**7.3 Third-Party Vendor Management**\n\n"
            "Any third-party vendors providing AI components, hosting, or data processing "
            "services for {{ system_name }} must be assessed under the organisation's "
            "vendor risk management programme before engagement and reviewed annually. "
            "Contracts must include AI-specific data processing clauses and the right "
            "to audit.\n\n"
            "**7.4 Internal Audit**\n\n"
            "{{ system_name }} must be included in the organisation's internal audit "
            "programme, with a minimum annual review covering governance controls, "
            "model performance, bias metrics, and policy compliance.\n\n"
            "**7.5 Reporting**\n\n"
            "Material AI incidents, significant performance degradations, or identified "
            "compliance gaps must be reported to the AI governance authority within "
            "24 hours of discovery, with a full incident report submitted within "
            "5 business days."
        ),
    },
    {
        "section_number": "8",
        "title": "Acceptable Use and Prohibited Activities",
        "template": (
            "**8.1 Permitted Use**\n\n"
            "{{ system_name }} may be used only for its documented business purpose: "
            "{{ system_purpose }}\n\n"
            "Use must remain within the boundaries of this Policy, the system's "
            "operating procedures, and applicable laws and regulations.\n\n"
            "**8.2 Prohibited Activities**\n\n"
            "The following activities are strictly prohibited in connection with "
            "{{ system_name }}:\n\n"
            "- Using the system for purposes other than its documented business purpose "
            "without prior written approval from the AI governance authority\n"
            "- Processing data categories not covered by the system's data classification "
            "and legal basis documentation\n"
            "- Attempting to circumvent access controls, monitoring, or safety measures\n"
            "- Deploying model updates or configuration changes without following the "
            "approved change management process\n"
            "- Using AI-generated outputs as the sole basis for high-stakes decisions "
            "that affect individuals without mandated human review\n"
            "- Disclosing training data, model weights, or proprietary system details "
            "to unauthorised parties\n\n"
            "**8.3 Consequences of Policy Violation**\n\n"
            "Violations of this Policy may result in disciplinary action up to and "
            "including termination of employment or contract, civil liability, and/or "
            "referral to law enforcement where applicable."
        ),
    },
    {
        "section_number": "9",
        "title": "Training and Awareness",
        "template": (
            "All personnel with roles covered by this Policy must complete role-specific "
            "AI governance training before being granted access to {{ system_name }} and "
            "annually thereafter. Training must cover:\n\n"
            "- AI risk principles and the {{ framework_label }}\n"
            "- Responsible use guidelines specific to {{ system_name }}\n"
            "- Data protection obligations applicable to the system\n"
            "- Incident identification and reporting procedures\n"
            "- Human oversight responsibilities for high-stakes outputs\n\n"
            "Training completion records must be maintained by {{ system_owner }} and "
            "made available on request for audit purposes."
        ),
    },
    {
        "section_number": "10",
        "title": "Risk Register and Remediation Priorities",
        "template": (
            "The following risk areas have been identified through the AI risk assessment "
            "conducted on {{ generated_date }}. Items are ordered by risk severity.\n\n"
            "{% if high_risk_categories %}"
            "**Categories Requiring Priority Attention:**\n\n"
            "{% for cat in high_risk_categories %}"
            "- **{{ cat.category_label }}** — Risk Level: {{ cat.risk_level }} "
            "(Score: {{ cat.normalised_score | round(1) }}/100)\n"
            "{% endfor %}"
            "\n{% endif %}"
            "{% if all_categories %}"
            "**Full Category Risk Summary:**\n\n"
            "{% for cat in all_categories %}"
            "- {{ cat.category_label }}: {{ cat.risk_level }} "
            "({{ cat.normalised_score | round(1) }}/100)\n"
            "{% endfor %}"
            "\n{% endif %}"
            "{{ system_owner }} must develop a time-bound remediation plan addressing "
            "all High and Critical risk findings within 90 days of this Policy's "
            "issuance. Progress against the remediation plan must be reported to the "
            "AI governance authority monthly until all Critical findings are resolved."
        ),
    },
    {
        "section_number": "11",
        "title": "Document Control",
        "template": (
            "| Field | Value |\n"
            "|---|---|\n"
            "| Document Title | AI Use Policy — {{ system_name }} |\n"
            "| Document ID | {{ document_id }} |\n"
            "| Version | {{ version }} |\n"
            "| System Owner | {{ system_owner }} |\n"
            "| Compliance Framework | {{ framework_label }} |\n"
            "| Generated Date | {{ generated_date }} |\n"
            "| Overall Risk Level | {{ overall_risk_level }} |\n"
            "| Next Review Date | (12 months from generated date) |\n"
            "| Classification | Internal — Restricted |\n"
            "\nThis document was generated automatically by AI Gov Gen using responses "
            "to the structured AI risk assessment questionnaire. It must be reviewed "
            "by a qualified compliance or legal professional before formal adoption."
        ),
    },
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _determine_implementation_status_and_finding(
    control_template: dict[str, Any],
    responses: dict[str, Any],
) -> tuple[str, str]:
    """Determine SSP implementation status and finding narrative for a control.

    Uses the ``finding_question`` and ``finding_map`` / ``status_map``
    defined in the control template to look up the appropriate text based
    on the response to that question.

    Args:
        control_template: An entry from :data:`_SSP_CONTROL_TEMPLATES`.
        responses: The raw questionnaire responses dict.

    Returns:
        Tuple of ``(implementation_status, assessment_finding)``.
    """
    q_id = control_template.get("finding_question", "")
    answer = responses.get(q_id)

    finding_map: dict[str, str] = control_template.get("finding_map", {})
    status_map: dict[str, str] = control_template.get("status_map", {})

    # For checkbox questions, use the first matching key
    if isinstance(answer, list):
        for val in answer:
            if val in finding_map:
                return (
                    status_map.get(val, "Partially Implemented"),
                    finding_map[val],
                )
        # None matched — treat as unanswered
        return (
            "Not Implemented",
            "Assessment question was not answered. Status assumed not implemented.",
        )

    answer_str = str(answer) if answer is not None else ""
    if answer_str in finding_map:
        return (
            status_map.get(answer_str, "Partially Implemented"),
            finding_map[answer_str],
        )

    return (
        "Not Implemented",
        "Assessment question was not answered. Status assumed not implemented.",
    )


def _determine_remediation_action(
    control_template: dict[str, Any],
    implementation_status: str,
) -> str:
    """Generate a remediation action statement based on implementation status.

    Args:
        control_template: The SSP control template dict.
        implementation_status: Current implementation status string.

    Returns:
        Remediation action string.
    """
    if implementation_status == "Implemented":
        return (
            "No immediate remediation required. Maintain current controls and "
            "schedule periodic review to ensure continued effectiveness."
        )
    if implementation_status == "Partially Implemented":
        return (
            f"Complete implementation of {control_template['control_name']}. "
            "Document gaps, assign an owner, and set a target completion date within 90 days."
        )
    if implementation_status == "Planned":
        return (
            f"Accelerate implementation of {control_template['control_name']} in accordance "
            "with the agreed plan. Escalate if the target date cannot be met."
        )
    if implementation_status == "Not Applicable":
        return "No remediation required — control is not applicable to this system."
    # Not Implemented
    return (
        f"Immediately initiate implementation of {control_template['control_name']}. "
        "Assign an accountable owner, allocate resources, and report progress to the "
        "AI governance authority within 30 days."
    )


def _select_checklist_items(
    assessment: AssessmentResult,
) -> list[dict[str, Any]]:
    """Select and annotate checklist items triggered by the assessment.

    An item from :data:`_CHECKLIST_LIBRARY` is included when:
    * Its ``trigger_values`` list is empty (always include), OR
    * The response to its ``triggered_by`` question(s) matches one of the
      ``trigger_values``.

    The effective risk level of each item is the maximum of its
    ``base_risk_level`` and the category's assessed risk level.

    Args:
        assessment: The scored :class:`AssessmentResult`.

    Returns:
        List of annotated checklist item dicts ready for
        :class:`ChecklistItem` construction.
    """
    responses = assessment.responses
    framework_id = assessment.framework_id

    selected: list[dict[str, Any]] = []
    counters: dict[str, int] = {}

    for lib_item in _CHECKLIST_LIBRARY:
        # Framework filter
        if framework_id not in lib_item["frameworks"]:
            continue

        triggered = False
        trigger_questions = lib_item.get("triggered_by", [])
        trigger_values = lib_item.get("trigger_values", [])

        if not trigger_questions or not trigger_values:
            # Always include
            triggered = True
        else:
            for q_id in trigger_questions:
                answer = responses.get(q_id)
                if answer is None:
                    # Unanswered — include as a gap
                    triggered = True
                    break
                if isinstance(answer, list):
                    if any(v in trigger_values for v in answer):
                        triggered = True
                        break
                else:
                    if str(answer) in trigger_values:
                        triggered = True
                        break

        if not triggered:
            continue

        cat_id = lib_item["category_id"]
        counters[cat_id] = counters.get(cat_id, 0) + 1

        # Determine effective risk level
        base_level = lib_item["base_risk_level"]
        cat_result = assessment.get_category_result(cat_id)
        cat_risk = cat_result.risk_level if cat_result else "Low"

        from ai_gov_gen.assessor import RISK_LEVELS  # local import

        base_idx = RISK_LEVELS.index(base_level) if base_level in RISK_LEVELS else 0
        cat_idx = RISK_LEVELS.index(cat_risk) if cat_risk in RISK_LEVELS else 0
        effective_level = RISK_LEVELS[max(base_idx, cat_idx)]

        selected.append(
            {
                **lib_item,
                "seq": counters[cat_id],
                "effective_risk_level": effective_level,
            }
        )

    return selected


# ---------------------------------------------------------------------------
# Public generator functions
# ---------------------------------------------------------------------------


def generate_checklist(assessment: AssessmentResult) -> GovernanceChecklist:
    """Generate a governance checklist from an assessment result.

    The checklist is organised by risk category and contains actionable
    control items triggered by the questionnaire responses.  Items are
    ordered within each category by risk severity (Critical → Low).

    Args:
        assessment: A :class:`~ai_gov_gen.assessor.AssessmentResult`
            produced by :func:`~ai_gov_gen.assessor.score_responses`.

    Returns:
        A fully populated :class:`GovernanceChecklist` instance.
    """
    logger.info(
        "Generating governance checklist for '%s' (framework: %s).",
        assessment.system_name,
        assessment.framework_id,
    )

    from ai_gov_gen.assessor import RISK_LEVELS  # local import

    selected_items = _select_checklist_items(assessment)

    # Group items by category
    items_by_cat: dict[str, list[dict[str, Any]]] = {}
    for item_data in selected_items:
        cat_id = item_data["category_id"]
        items_by_cat.setdefault(cat_id, []).append(item_data)

    # Build category objects in the CATEGORIES order
    from ai_gov_gen.questions import CATEGORIES  # local import

    checklist_categories: list[ChecklistCategory] = []
    for cat in CATEGORIES:
        cat_id = cat["id"]
        cat_items_data = items_by_cat.get(cat_id, [])

        # Sort by risk level descending (Critical first)
        cat_items_data.sort(
            key=lambda x: RISK_LEVELS.index(x["effective_risk_level"])
            if x["effective_risk_level"] in RISK_LEVELS
            else 0,
            reverse=True,
        )

        checklist_items: list[ChecklistItem] = []
        for idx, item_data in enumerate(cat_items_data, start=1):
            risk_lvl = item_data["effective_risk_level"]
            checklist_items.append(
                ChecklistItem(
                    item_id=f"{cat_id}-{idx}",
                    category_id=cat_id,
                    category_label=cat["label"],
                    control_ref=item_data["control_ref"],
                    action=item_data["action"],
                    rationale=item_data["rationale"],
                    risk_level=risk_lvl,
                    priority=RISK_LEVEL_PRIORITY.get(risk_lvl, risk_lvl),
                    badge_class=RISK_LEVEL_BADGE_CLASS.get(risk_lvl, "secondary"),
                    frameworks=item_data["frameworks"],
                    completed=False,
                )
            )

        cat_result = assessment.get_category_result(cat_id)
        checklist_categories.append(
            ChecklistCategory(
                category_id=cat_id,
                category_label=cat["label"],
                risk_level=cat_result.risk_level if cat_result else "Low",
                normalised_score=cat_result.normalised_score if cat_result else 0.0,
                items=checklist_items,
            )
        )

    return GovernanceChecklist(
        system_name=assessment.system_name,
        system_owner=assessment.system_owner,
        framework_id=assessment.framework_id,
        framework_label=assessment.framework_label,
        overall_risk_level=assessment.overall_risk_level,
        overall_score=assessment.overall_score,
        generated_date=date.today().isoformat(),
        categories=checklist_categories,
        warnings=list(assessment.warnings),
    )


def generate_ssp_entries(
    assessment: AssessmentResult,
) -> list[SSPEntry]:
    """Generate System Security Plan control entries from an assessment result.

    Each entry maps to a specific control reference and is populated with
    implementation status and assessment findings derived from the
    questionnaire responses.

    Args:
        assessment: A :class:`~ai_gov_gen.assessor.AssessmentResult`
            produced by :func:`~ai_gov_gen.assessor.score_responses`.

    Returns:
        Ordered list of :class:`SSPEntry` objects.
    """
    logger.info(
        "Generating SSP entries for '%s' (framework: %s).",
        assessment.system_name,
        assessment.framework_id,
    )

    entries: list[SSPEntry] = []
    for tmpl in _SSP_CONTROL_TEMPLATES:
        # Framework filter
        if assessment.framework_id not in tmpl["frameworks"] and "enterprise" not in tmpl["frameworks"]:
            continue

        impl_status, finding = _determine_implementation_status_and_finding(
            tmpl, assessment.responses
        )
        remediation = _determine_remediation_action(tmpl, impl_status)

        # Personalise the implementation detail with system-specific context
        impl_detail = (
            f"For the AI system '{assessment.system_name}', operated by "
            f"'{assessment.system_owner}': {finding}"
        )

        entry_id = f"{tmpl['entry_id_prefix']}-{tmpl['seq']:03d}"

        entries.append(
            SSPEntry(
                entry_id=entry_id,
                control_family=tmpl["control_family"],
                control_ref=tmpl["control_ref"],
                control_name=tmpl["control_name"],
                control_description=tmpl["control_description"],
                implementation_status=impl_status,
                implementation_detail=impl_detail,
                responsible_role=tmpl["responsible_role"],
                assessment_finding=finding,
                risk_level=_derive_ssp_risk_level(assessment, tmpl),
                remediation_action=remediation,
                evidence_artifacts=list(tmpl["evidence_artifacts"]),
                frameworks=list(tmpl["frameworks"]),
            )
        )

    return entries


def _derive_ssp_risk_level(
    assessment: AssessmentResult,
    tmpl: dict[str, Any],
) -> str:
    """Derive a risk level for an SSP entry from category results.

    Uses the overall risk level as a fallback, but elevates to the
    category-specific risk level when available.

    Args:
        assessment: The scored assessment result.
        tmpl: The SSP control template dict.

    Returns:
        Risk level string.
    """
    # Infer category from entry_id_prefix
    prefix = tmpl.get("entry_id_prefix", "")
    cat_id: str | None = None
    if "DATA" in prefix:
        cat_id = "data"
    elif "MODEL" in prefix:
        cat_id = "model"
    elif "OPS" in prefix:
        cat_id = "ops"
    elif "COMP" in prefix:
        cat_id = "compliance"

    if cat_id:
        cat_result = assessment.get_category_result(cat_id)
        if cat_result:
            return cat_result.risk_level

    return assessment.overall_risk_level


def generate_policy_document(
    assessment: AssessmentResult,
) -> PolicyDocument:
    """Generate a full AI use policy document from an assessment result.

    Each section of the policy is rendered from a Jinja2 template string
    populated with system-specific details from the assessment.

    Args:
        assessment: A :class:`~ai_gov_gen.assessor.AssessmentResult`
            produced by :func:`~ai_gov_gen.assessor.score_responses`.

    Returns:
        A fully rendered :class:`PolicyDocument` instance.
    """
    logger.info(
        "Generating policy document for '%s' (framework: %s).",
        assessment.system_name,
        assessment.framework_id,
    )

    try:
        fw_meta = get_framework_metadata(assessment.framework_id)
        framework_description = fw_meta.get("description", assessment.framework_label)
    except ValueError:
        framework_description = assessment.framework_label

    cat_by_id = assessment.category_results_by_id
    data_risk = cat_by_id.get("data")
    model_risk = cat_by_id.get("model")
    ops_risk = cat_by_id.get("ops")
    comp_risk = cat_by_id.get("compliance")

    generated_date = date.today().isoformat()
    document_id = (
        f"AI-POL-{assessment.system_name[:8].upper().replace(' ', '-')}-"
        f"{generated_date.replace('-', '')}"
    )

    base_context: dict[str, Any] = {
        "system_name": assessment.system_name,
        "system_owner": assessment.system_owner,
        "system_purpose": assessment.system_purpose,
        "framework_id": assessment.framework_id,
        "framework_label": assessment.framework_label,
        "framework_description": framework_description,
        "overall_risk_level": assessment.overall_risk_level,
        "overall_score": assessment.overall_score,
        "generated_date": generated_date,
        "document_id": document_id,
        "version": "1.0",
        "data_risk_level": data_risk.risk_level if data_risk else "Unknown",
        "model_risk_level": model_risk.risk_level if model_risk else "Unknown",
        "ops_risk_level": ops_risk.risk_level if ops_risk else "Unknown",
        "compliance_risk_level": comp_risk.risk_level if comp_risk else "Unknown",
        "high_risk_categories": [
            cr for cr in assessment.category_results
            if cr.risk_level in {"High", "Critical"}
        ],
        "all_categories": assessment.category_results,
    }

    sections: list[PolicySection] = []
    for sec_tmpl in _POLICY_SECTION_TEMPLATES:
        try:
            rendered_content = _render(sec_tmpl["template"], base_context)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to render policy section '%s': %s",
                sec_tmpl["title"],
                exc,
            )
            rendered_content = (
                f"[Content generation error for section '{sec_tmpl['title']}': {exc}]"
            )
        sections.append(
            PolicySection(
                section_number=sec_tmpl["section_number"],
                title=sec_tmpl["title"],
                content=rendered_content,
            )
        )

    return PolicyDocument(
        title=f"AI Use Policy — {assessment.system_name}",
        document_id=document_id,
        version="1.0",
        system_name=assessment.system_name,
        system_owner=assessment.system_owner,
        system_purpose=assessment.system_purpose,
        framework_id=assessment.framework_id,
        framework_label=assessment.framework_label,
        overall_risk_level=assessment.overall_risk_level,
        generated_date=generated_date,
        sections=sections,
        warnings=list(assessment.warnings),
    )


def render_policy_html(
    policy_document: PolicyDocument,
    assessment: AssessmentResult,
    checklist: GovernanceChecklist | None = None,
    ssp_entries: list[SSPEntry] | None = None,
) -> str:
    """Render the policy document and supporting artifacts to an HTML string.

    This function uses the Flask application's Jinja2 template environment
    to render the ``policy_doc.html`` template, which is designed for
    PDF generation via WeasyPrint.  An active Flask application context
    is required.

    Args:
        policy_document: The :class:`PolicyDocument` to render.
        assessment: The source :class:`~ai_gov_gen.assessor.AssessmentResult`.
        checklist: Optional :class:`GovernanceChecklist` to embed in the HTML.
        ssp_entries: Optional list of :class:`SSPEntry` objects to embed.

    Returns:
        Rendered HTML string suitable for WeasyPrint PDF conversion.

    Raises:
        RuntimeError: If called outside a Flask application context.
    """
    try:
        from flask import current_app, render_template  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "render_policy_html requires Flask to be installed."
        ) from exc

    try:
        _ = current_app._get_current_object()  # type: ignore[attr-defined]
    except RuntimeError as exc:
        raise RuntimeError(
            "render_policy_html must be called within an active Flask application context."
        ) from exc

    logger.info(
        "Rendering policy HTML for '%s'.",
        policy_document.system_name,
    )

    return render_template(
        "policy_doc.html",
        policy=policy_document,
        policy_dict=policy_document.to_dict(),
        assessment=assessment,
        assessment_dict=assessment.to_dict(),
        checklist=checklist,
        checklist_dict=checklist.to_dict() if checklist else None,
        ssp_entries=ssp_entries,
        ssp_entries_dicts=[e.to_dict() for e in ssp_entries] if ssp_entries else [],
        risk_badge_classes=RISK_LEVEL_BADGE_CLASS,
        risk_priorities=RISK_LEVEL_PRIORITY,
    )


def generate_all(assessment: AssessmentResult) -> GeneratedArtifacts:
    """Generate all three governance artifacts from an assessment result.

    This is a convenience wrapper that calls :func:`generate_checklist`,
    :func:`generate_ssp_entries`, and :func:`generate_policy_document` in
    sequence and bundles the results.

    Args:
        assessment: A :class:`~ai_gov_gen.assessor.AssessmentResult`
            produced by :func:`~ai_gov_gen.assessor.score_responses`.

    Returns:
        A :class:`GeneratedArtifacts` bundle containing all three artifact
        types alongside the source assessment.
    """
    logger.info(
        "Generating all artifacts for '%s'.",
        assessment.system_name,
    )
    checklist = generate_checklist(assessment)
    ssp_entries = generate_ssp_entries(assessment)
    policy_document = generate_policy_document(assessment)

    return GeneratedArtifacts(
        checklist=checklist,
        ssp_entries=ssp_entries,
        policy_document=policy_document,
        assessment=assessment,
    )
