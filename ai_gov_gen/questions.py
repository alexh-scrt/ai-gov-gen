"""Question bank for the AI Gov Gen risk assessment questionnaire.

This module defines the full categorized question bank used throughout the
questionnaire wizard.  Questions are organized into four risk categories
aligned with the HKS AI Risk Framework and NIST AI RMF:

* **data** — Data governance, provenance, privacy, and quality
* **model** — Model risk, explainability, bias, and validation
* **ops** — Operational security, monitoring, access control, and incident response
* **compliance** — Regulatory compliance, framework alignment, and audit readiness

Each question is a ``dict`` with the following schema::

    {
        "id": str,                  # Unique identifier, e.g. "data_01"
        "category": str,            # One of: data, model, ops, compliance
        "text": str,                # Human-readable question text
        "help_text": str,           # Explanatory hint shown beneath the question
        "input_type": str,          # "radio", "checkbox", "text", "select", "textarea"
        "options": list[dict],      # For radio/checkbox/select: [{"value": str, "label": str, "risk_weight": int}]
        "required": bool,           # Whether an answer is mandatory
        "frameworks": list[str],    # Framework IDs for which this question is relevant
        "nist_function": str,       # NIST AI RMF function: GOVERN, MAP, MEASURE, MANAGE
        "hks_dimension": str,       # HKS dimension tag
        "weight": float,            # Relative importance weight within category (0.0–1.0)
    }

The ``risk_weight`` on each option is an integer from 0 (no risk) to 3
(highest risk) used by the scoring engine in ``assessor.py``.

Module-level constants
-----------------------
:data:`CATEGORIES` — ordered list of category metadata dicts.
:data:`FRAMEWORK_METADATA` — framework selector options with descriptions.
:data:`QUESTIONS` — the master list of all question dicts.
:data:`QUESTIONS_BY_CATEGORY` — ``dict`` mapping category id → list of questions.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------

CATEGORIES: list[dict[str, Any]] = [
    {
        "id": "data",
        "label": "Data Governance",
        "description": (
            "Covers data provenance, quality, privacy, consent, and lifecycle "
            "management for data used to train or operate the AI system."
        ),
        "icon": "database",
        "order": 1,
    },
    {
        "id": "model",
        "label": "Model Risk",
        "description": (
            "Covers model development practices, explainability, bias and "
            "fairness testing, validation, and version control."
        ),
        "icon": "cpu",
        "order": 2,
    },
    {
        "id": "ops",
        "label": "Operational Security",
        "description": (
            "Covers deployment architecture, access control, runtime monitoring, "
            "adversarial robustness, and incident response for AI systems."
        ),
        "icon": "shield-lock",
        "order": 3,
    },
    {
        "id": "compliance",
        "label": "Compliance & Audit",
        "description": (
            "Covers regulatory obligations, framework alignment, documentation "
            "completeness, third-party obligations, and audit readiness."
        ),
        "icon": "clipboard-check",
        "order": 4,
    },
]


# ---------------------------------------------------------------------------
# Framework selector metadata
# ---------------------------------------------------------------------------

FRAMEWORK_METADATA: list[dict[str, Any]] = [
    {
        "id": "nist_ai_rmf",
        "label": "NIST AI RMF",
        "full_name": "NIST AI Risk Management Framework (NIST AI 100-1)",
        "description": (
            "The National Institute of Standards and Technology AI Risk Management "
            "Framework organizes AI risk activities into four functions: GOVERN, MAP, "
            "MEASURE, and MANAGE.  Outputs are aligned to RMF subcategories."
        ),
        "version": "1.0 (2023)",
        "contexts": ["federal", "enterprise", "research"],
    },
    {
        "id": "hks",
        "label": "HKS AI Risk Framework",
        "full_name": "Harvard Kennedy School Responsible AI Framework",
        "description": (
            "The HKS framework emphasizes societal impact, accountability, "
            "transparency, and fairness dimensions of AI deployments, particularly "
            "in public-sector and policy contexts."
        ),
        "version": "2023 Edition",
        "contexts": ["public_sector", "policy", "research"],
    },
    {
        "id": "cmmc_l2",
        "label": "CMMC Level 2",
        "full_name": "Cybersecurity Maturity Model Certification Level 2",
        "description": (
            "CMMC Level 2 aligns to NIST SP 800-171 and is required for defense "
            "contractors handling Controlled Unclassified Information (CUI).  "
            "AI-adjacent controls for access, audit, and configuration management "
            "are included."
        ),
        "version": "CMMC 2.0",
        "contexts": ["defense", "federal", "contractor"],
    },
    {
        "id": "lloyds",
        "label": "Lloyd's Market AI Guidelines",
        "full_name": "Lloyd's of London AI Principles and Market Guidance",
        "description": (
            "Lloyd's market guidance addresses AI use in insurance underwriting, "
            "claims processing, and risk modelling.  It emphasises model "
            "explainability, regulatory compliance, and customer fairness."
        ),
        "version": "2023 Guidance",
        "contexts": ["insurance", "financial_services"],
    },
    {
        "id": "enterprise",
        "label": "Enterprise Generic",
        "full_name": "General Enterprise AI Governance Baseline",
        "description": (
            "A technology-neutral baseline suitable for any organization deploying "
            "AI systems.  Draws from ISO/IEC 42001, NIST AI RMF, and common "
            "enterprise risk management practices."
        ),
        "version": "Baseline 1.0",
        "contexts": ["enterprise", "commercial", "startup"],
    },
]

# Convenience lookup: framework_id → metadata dict
FRAMEWORK_BY_ID: dict[str, dict[str, Any]] = {
    fw["id"]: fw for fw in FRAMEWORK_METADATA
}


# ---------------------------------------------------------------------------
# Master question bank
# ---------------------------------------------------------------------------
# fmt: off

QUESTIONS: list[dict[str, Any]] = [

    # ===================================================================
    # CATEGORY: DATA GOVERNANCE
    # ===================================================================

    {
        "id": "data_01",
        "category": "data",
        "text": "What types of data does the AI system process or was trained on?",
        "help_text": (
            "Select all data types that apply.  Personal data, protected health "
            "information, and financial records increase regulatory exposure."
        ),
        "input_type": "checkbox",
        "options": [
            {"value": "public_open",      "label": "Publicly available / open datasets",         "risk_weight": 0},
            {"value": "anonymised",       "label": "Anonymised or pseudonymised personal data",   "risk_weight": 1},
            {"value": "pii",              "label": "Personally Identifiable Information (PII)",    "risk_weight": 2},
            {"value": "phi",              "label": "Protected Health Information (PHI / HIPAA)",  "risk_weight": 3},
            {"value": "financial",        "label": "Financial or payment card data",              "risk_weight": 2},
            {"value": "cui",              "label": "Controlled Unclassified Information (CUI)",   "risk_weight": 3},
            {"value": "proprietary",      "label": "Proprietary business / trade secret data",    "risk_weight": 2},
            {"value": "biometric",        "label": "Biometric data",                              "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "MAP",
        "hks_dimension": "Data Stewardship",
        "weight": 1.0,
    },
    {
        "id": "data_02",
        "category": "data",
        "text": "Is a formal data provenance and lineage record maintained for all training and inference data?",
        "help_text": (
            "Data provenance tracks the origin, transformations, and custody chain of "
            "datasets.  Without it, data quality issues and bias sources are difficult "
            "to audit."
        ),
        "input_type": "radio",
        "options": [
            {"value": "yes_automated",   "label": "Yes — automated lineage tracking is in place",       "risk_weight": 0},
            {"value": "yes_manual",      "label": "Yes — manual documentation exists",                  "risk_weight": 1},
            {"value": "partial",         "label": "Partially — some datasets are documented",           "risk_weight": 2},
            {"value": "no",              "label": "No — provenance is not tracked",                     "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Data Stewardship",
        "weight": 0.9,
    },
    {
        "id": "data_03",
        "category": "data",
        "text": "Has the organization obtained appropriate consent or legal basis for using personal data in the AI system?",
        "help_text": (
            "Under GDPR, CCPA, and equivalent regulations, processing personal data "
            "requires a documented lawful basis such as consent, legitimate interest, "
            "or contractual necessity."
        ),
        "input_type": "radio",
        "options": [
            {"value": "not_applicable",   "label": "Not applicable — no personal data used",            "risk_weight": 0},
            {"value": "yes_documented",   "label": "Yes — consent/legal basis is formally documented",  "risk_weight": 0},
            {"value": "yes_assumed",      "label": "Yes — assumed but not formally documented",          "risk_weight": 2},
            {"value": "uncertain",        "label": "Uncertain — legal basis not fully assessed",         "risk_weight": 3},
            {"value": "no",              "label": "No — personal data used without documented basis",    "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Privacy & Rights",
        "weight": 1.0,
    },
    {
        "id": "data_04",
        "category": "data",
        "text": "What data quality controls are applied before data enters the AI pipeline?",
        "help_text": (
            "Poor data quality (missing values, duplicates, label errors, distribution "
            "shift) degrades model performance and can amplify bias."
        ),
        "input_type": "checkbox",
        "options": [
            {"value": "schema_validation",  "label": "Schema / format validation",                      "risk_weight": 0},
            {"value": "completeness",       "label": "Completeness and missing-value checks",            "risk_weight": 0},
            {"value": "statistical_profile","label": "Statistical profiling and distribution checks",    "risk_weight": 0},
            {"value": "bias_scan",          "label": "Bias and fairness scanning of datasets",           "risk_weight": 0},
            {"value": "manual_review",      "label": "Manual human review of samples",                  "risk_weight": 0},
            {"value": "none",              "label": "No formal data quality controls",                  "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
        "nist_function": "MEASURE",
        "hks_dimension": "Data Stewardship",
        "weight": 0.8,
    },
    {
        "id": "data_05",
        "category": "data",
        "text": "Is data encrypted at rest and in transit throughout the AI pipeline?",
        "help_text": (
            "Encryption protects training data, inference inputs, and model outputs "
            "from unauthorized access.  CMMC Level 2 requires encryption for CUI."
        ),
        "input_type": "radio",
        "options": [
            {"value": "both",             "label": "Yes — encrypted both at rest and in transit",        "risk_weight": 0},
            {"value": "transit_only",     "label": "In transit only",                                   "risk_weight": 1},
            {"value": "rest_only",        "label": "At rest only",                                     "risk_weight": 2},
            {"value": "neither",          "label": "Not encrypted",                                    "risk_weight": 3},
            {"value": "not_applicable",   "label": "Not applicable — no sensitive data",               "risk_weight": 0},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "MANAGE",
        "hks_dimension": "Data Stewardship",
        "weight": 0.9,
    },
    {
        "id": "data_06",
        "category": "data",
        "text": "Is there a documented data retention and deletion policy covering AI training and inference data?",
        "help_text": (
            "Retention policies limit legal liability and ensure personal data is not "
            "held longer than necessary.  GDPR Article 5(e) requires storage limitation."
        ),
        "input_type": "radio",
        "options": [
            {"value": "yes_enforced",     "label": "Yes — policy exists and is technically enforced",    "risk_weight": 0},
            {"value": "yes_manual",       "label": "Yes — policy exists but deletion is manual",         "risk_weight": 1},
            {"value": "partial",          "label": "Partial — some data categories covered",             "risk_weight": 2},
            {"value": "no",              "label": "No retention/deletion policy exists",                "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Privacy & Rights",
        "weight": 0.7,
    },
    {
        "id": "data_07",
        "category": "data",
        "text": "Are third-party or vendor-supplied datasets subject to the same data governance controls as internally produced data?",
        "help_text": (
            "Third-party data carries supply-chain risk — it may contain hidden biases, "
            "license restrictions, or privacy violations that pass through to the AI system."
        ),
        "input_type": "radio",
        "options": [
            {"value": "not_applicable",   "label": "Not applicable — no third-party datasets used",     "risk_weight": 0},
            {"value": "yes_equivalent",   "label": "Yes — same controls applied to all data sources",    "risk_weight": 0},
            {"value": "partial",          "label": "Partially — reviewed on a case-by-case basis",       "risk_weight": 2},
            {"value": "no",              "label": "No — third-party data is used without review",       "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "enterprise"],
        "nist_function": "MAP",
        "hks_dimension": "Data Stewardship",
        "weight": 0.7,
    },
    {
        "id": "data_08",
        "category": "data",
        "text": "Is a Data Protection Impact Assessment (DPIA) or Privacy Impact Assessment (PIA) completed for this AI system?",
        "help_text": (
            "A DPIA/PIA systematically identifies privacy risks before processing begins. "
            "GDPR Article 35 mandates a DPIA for high-risk processing."
        ),
        "input_type": "radio",
        "options": [
            {"value": "yes_completed",    "label": "Yes — DPIA/PIA completed and approved",             "risk_weight": 0},
            {"value": "in_progress",      "label": "In progress",                                      "risk_weight": 1},
            {"value": "not_applicable",   "label": "Not applicable — no personal data processed",       "risk_weight": 0},
            {"value": "no",              "label": "No — DPIA/PIA not conducted",                      "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["hks", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Privacy & Rights",
        "weight": 0.8,
    },

    # ===================================================================
    # CATEGORY: MODEL RISK
    # ===================================================================

    {
        "id": "model_01",
        "category": "model",
        "text": "How was the AI model developed?",
        "help_text": (
            "Foundation models and third-party solutions introduce supply-chain risk "
            "and may have limited explainability.  Custom-built models offer more "
            "control but require more rigorous internal validation."
        ),
        "input_type": "radio",
        "options": [
            {"value": "custom_internal",  "label": "Built entirely in-house on internal data",           "risk_weight": 1},
            {"value": "custom_external",  "label": "Developed by a third-party vendor for us",           "risk_weight": 2},
            {"value": "foundation_finetuned", "label": "Foundation model fine-tuned on our data",        "risk_weight": 2},
            {"value": "foundation_vanilla",   "label": "Foundation model used without fine-tuning",      "risk_weight": 2},
            {"value": "saas_api",         "label": "Third-party SaaS / API (black-box)",                "risk_weight": 3},
            {"value": "open_source",      "label": "Open-source model deployed self-hosted",            "risk_weight": 1},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "MAP",
        "hks_dimension": "Accountability",
        "weight": 1.0,
    },
    {
        "id": "model_02",
        "category": "model",
        "text": "What is the intended use case and decision-making impact of the AI system?",
        "help_text": (
            "High-stakes decisions (hiring, lending, medical, criminal justice) attract "
            "greater regulatory scrutiny and require more rigorous validation and "
            "explainability controls."
        ),
        "input_type": "radio",
        "options": [
            {"value": "low_stakes",       "label": "Low-stakes / informational (e.g., content recommendations)", "risk_weight": 0},
            {"value": "moderate",         "label": "Moderate impact (e.g., internal process automation)",         "risk_weight": 1},
            {"value": "high_stakes",      "label": "High-stakes decisions affecting individuals (e.g., credit, hiring)", "risk_weight": 3},
            {"value": "safety_critical",  "label": "Safety-critical / life-affecting (e.g., medical, autonomous systems)", "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
        "nist_function": "MAP",
        "hks_dimension": "Societal Impact",
        "weight": 1.0,
    },
    {
        "id": "model_03",
        "category": "model",
        "text": "Has the model undergone formal bias and fairness testing across demographic sub-groups?",
        "help_text": (
            "Bias testing identifies whether model outputs systematically disadvantage "
            "groups based on protected characteristics such as race, gender, age, or disability."
        ),
        "input_type": "radio",
        "options": [
            {"value": "comprehensive",    "label": "Yes — comprehensive testing across all relevant sub-groups",  "risk_weight": 0},
            {"value": "partial",          "label": "Partial — some sub-groups tested",                           "risk_weight": 1},
            {"value": "planned",          "label": "Planned but not yet conducted",                              "risk_weight": 2},
            {"value": "no",              "label": "No bias testing conducted",                                  "risk_weight": 3},
            {"value": "not_applicable",   "label": "Not applicable — model does not operate on personal data",   "risk_weight": 0},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
        "nist_function": "MEASURE",
        "hks_dimension": "Fairness & Equity",
        "weight": 1.0,
    },
    {
        "id": "model_04",
        "category": "model",
        "text": "Can the model's predictions or recommendations be explained to end users and oversight teams?",
        "help_text": (
            "Explainability (interpretability) is required by EU AI Act Article 13, "
            "GDPR Article 22, and Lloyd's market guidance.  It is critical for "
            "auditing and contesting AI-assisted decisions."
        ),
        "input_type": "radio",
        "options": [
            {"value": "inherently_interpretable", "label": "Yes — model is inherently interpretable (e.g., decision tree, linear model)", "risk_weight": 0},
            {"value": "xai_tooling",    "label": "Yes — post-hoc XAI tooling in place (e.g., SHAP, LIME)",      "risk_weight": 0},
            {"value": "partial",        "label": "Partial — some explanation capability exists",                 "risk_weight": 1},
            {"value": "no",            "label": "No — model is a black box with no explanation",               "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
        "nist_function": "MEASURE",
        "hks_dimension": "Transparency",
        "weight": 0.9,
    },
    {
        "id": "model_05",
        "category": "model",
        "text": "Is a formal model validation process in place, including independent validation separate from the development team?",
        "help_text": (
            "Independent validation (champion-challenger testing, out-of-time samples, "
            "adversarial testing) reduces groupthink and catches errors the development "
            "team may miss.  This is a core requirement for financial services AI."
        ),
        "input_type": "radio",
        "options": [
            {"value": "independent",      "label": "Yes — independent validation team reviews all models",       "risk_weight": 0},
            {"value": "internal_only",    "label": "Internal validation only — same team that built the model",  "risk_weight": 2},
            {"value": "ad_hoc",           "label": "Ad-hoc — validation done informally",                        "risk_weight": 2},
            {"value": "no",              "label": "No validation process",                                      "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
        "nist_function": "MEASURE",
        "hks_dimension": "Accountability",
        "weight": 0.9,
    },
    {
        "id": "model_06",
        "category": "model",
        "text": "Is the model version-controlled and is a model registry maintained?",
        "help_text": (
            "A model registry records which model version is in production, its "
            "training metadata, performance benchmarks, and sign-off history.  This "
            "is essential for reproducibility and incident investigation."
        ),
        "input_type": "radio",
        "options": [
            {"value": "full_registry",    "label": "Yes — formal model registry with metadata and approvals",    "risk_weight": 0},
            {"value": "version_control",  "label": "Version control only (e.g., Git) — no registry",            "risk_weight": 1},
            {"value": "partial",          "label": "Partial — some models tracked, others not",                  "risk_weight": 2},
            {"value": "no",              "label": "No version control or registry",                             "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Accountability",
        "weight": 0.7,
    },
    {
        "id": "model_07",
        "category": "model",
        "text": "Has the model been tested for robustness against adversarial inputs or prompt injection attacks?",
        "help_text": (
            "Adversarial robustness testing probes whether the model can be manipulated "
            "by specially crafted inputs.  For LLMs and generative AI, prompt injection "
            "is a critical attack vector."
        ),
        "input_type": "radio",
        "options": [
            {"value": "comprehensive",    "label": "Yes — comprehensive adversarial and red-team testing",       "risk_weight": 0},
            {"value": "basic",            "label": "Basic robustness checks only",                              "risk_weight": 1},
            {"value": "planned",          "label": "Planned but not yet conducted",                             "risk_weight": 2},
            {"value": "no",              "label": "No robustness testing",                                     "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "enterprise"],
        "nist_function": "MEASURE",
        "hks_dimension": "Reliability & Safety",
        "weight": 0.8,
    },
    {
        "id": "model_08",
        "category": "model",
        "text": "Is there a human-in-the-loop review process for high-stakes model outputs?",
        "help_text": (
            "Human oversight ensures that consequential decisions are reviewed before "
            "action is taken.  The EU AI Act requires human oversight for high-risk AI "
            "systems under Article 14."
        ),
        "input_type": "radio",
        "options": [
            {"value": "mandatory",        "label": "Yes — human review is mandatory for all high-stakes outputs",   "risk_weight": 0},
            {"value": "optional",         "label": "Human review is available but not mandatory",                   "risk_weight": 1},
            {"value": "exception_only",   "label": "Human review only triggered for flagged exceptions",           "risk_weight": 1},
            {"value": "no",              "label": "No human-in-the-loop — fully automated decisions",             "risk_weight": 3},
            {"value": "not_applicable",   "label": "Not applicable — model outputs are advisory only",             "risk_weight": 0},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
        "nist_function": "MANAGE",
        "hks_dimension": "Human Oversight",
        "weight": 1.0,
    },

    # ===================================================================
    # CATEGORY: OPERATIONAL SECURITY
    # ===================================================================

    {
        "id": "ops_01",
        "category": "ops",
        "text": "Where is the AI system deployed and hosted?",
        "help_text": (
            "Deployment environment determines applicable security controls.  "
            "On-premises deployments allow more direct control; cloud and SaaS "
            "deployments require careful shared-responsibility model review."
        ),
        "input_type": "radio",
        "options": [
            {"value": "on_premises",      "label": "On-premises (organization-owned infrastructure)",            "risk_weight": 1},
            {"value": "private_cloud",    "label": "Private cloud (dedicated tenant)",                          "risk_weight": 1},
            {"value": "public_cloud",     "label": "Public cloud (shared multi-tenant, e.g., AWS, Azure, GCP)",  "risk_weight": 2},
            {"value": "saas_vendor",      "label": "Third-party SaaS — vendor managed",                         "risk_weight": 2},
            {"value": "hybrid",           "label": "Hybrid (mix of on-premises and cloud)",                     "risk_weight": 2},
            {"value": "edge",             "label": "Edge deployment (IoT / device)",                           "risk_weight": 2},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "MAP",
        "hks_dimension": "Operational Security",
        "weight": 0.8,
    },
    {
        "id": "ops_02",
        "category": "ops",
        "text": "Is role-based access control (RBAC) implemented for all AI system components (training environment, model serving, data stores)?",
        "help_text": (
            "RBAC limits the blast radius of compromised credentials and is a "
            "baseline requirement under CMMC Level 2 (AC.L2-3.1.1) and NIST SP 800-171."
        ),
        "input_type": "radio",
        "options": [
            {"value": "comprehensive",    "label": "Yes — RBAC enforced across all components with least-privilege", "risk_weight": 0},
            {"value": "partial",          "label": "Partial — RBAC applied to some components",                     "risk_weight": 2},
            {"value": "basic",            "label": "Basic access controls (passwords only, no role separation)",     "risk_weight": 2},
            {"value": "no",              "label": "No access controls in place",                                   "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "MANAGE",
        "hks_dimension": "Operational Security",
        "weight": 0.9,
    },
    {
        "id": "ops_03",
        "category": "ops",
        "text": "Is multi-factor authentication (MFA) enforced for all accounts with access to AI system components?",
        "help_text": (
            "MFA significantly reduces the risk of credential-based attacks.  "
            "CMMC Level 2 (IA.L2-3.5.3) mandates MFA for privileged accounts."
        ),
        "input_type": "radio",
        "options": [
            {"value": "all_users",        "label": "Yes — MFA enforced for all users",                           "risk_weight": 0},
            {"value": "privileged_only",  "label": "MFA for privileged accounts only",                          "risk_weight": 1},
            {"value": "optional",         "label": "MFA available but not enforced",                            "risk_weight": 2},
            {"value": "no",              "label": "No MFA in place",                                           "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "MANAGE",
        "hks_dimension": "Operational Security",
        "weight": 0.8,
    },
    {
        "id": "ops_04",
        "category": "ops",
        "text": "Is runtime monitoring in place to detect model performance degradation, data drift, or anomalous behaviour?",
        "help_text": (
            "Continuous monitoring catches distribution shift, adversarial activity, "
            "and model degradation before they cause harm.  NIST AI RMF MANAGE function "
            "requires ongoing performance tracking."
        ),
        "input_type": "checkbox",
        "options": [
            {"value": "performance_metrics", "label": "Model performance metrics (accuracy, F1, etc.)",          "risk_weight": 0},
            {"value": "data_drift",           "label": "Input data distribution / drift monitoring",             "risk_weight": 0},
            {"value": "output_distribution",  "label": "Output distribution monitoring",                         "risk_weight": 0},
            {"value": "security_alerts",      "label": "Security and anomaly detection alerts",                  "risk_weight": 0},
            {"value": "audit_logs",           "label": "Comprehensive audit logging of queries and outputs",      "risk_weight": 0},
            {"value": "none",                "label": "No runtime monitoring",                                  "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "MANAGE",
        "hks_dimension": "Reliability & Safety",
        "weight": 0.9,
    },
    {
        "id": "ops_05",
        "category": "ops",
        "text": "Is there a documented incident response plan that explicitly covers AI system failures, adversarial attacks, or harmful outputs?",
        "help_text": (
            "A purpose-built AI incident response plan defines escalation paths, "
            "containment procedures, and communication protocols specific to AI failure "
            "modes such as model poisoning, hallucination, or discriminatory outputs."
        ),
        "input_type": "radio",
        "options": [
            {"value": "ai_specific",      "label": "Yes — AI-specific incident response plan exists and is tested",  "risk_weight": 0},
            {"value": "general_ir",       "label": "General IT incident response plan covers AI systems",           "risk_weight": 1},
            {"value": "draft",            "label": "Draft plan exists but not formally approved or tested",         "risk_weight": 2},
            {"value": "no",              "label": "No incident response plan",                                    "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "MANAGE",
        "hks_dimension": "Accountability",
        "weight": 0.9,
    },
    {
        "id": "ops_06",
        "category": "ops",
        "text": "Is there a tested rollback or kill-switch capability to disable or revert the AI system rapidly?",
        "help_text": (
            "Rapid response capability limits harm when an AI system produces "
            "dangerous or unacceptable outputs.  Rollback should restore a known-good "
            "model version within a defined recovery time objective (RTO)."
        ),
        "input_type": "radio",
        "options": [
            {"value": "tested_automated", "label": "Yes — automated kill-switch and rollback, regularly tested",   "risk_weight": 0},
            {"value": "tested_manual",    "label": "Manual rollback procedure, documented and tested",             "risk_weight": 1},
            {"value": "untested",         "label": "Rollback capability exists but has not been tested",           "risk_weight": 2},
            {"value": "no",              "label": "No rollback or kill-switch capability",                       "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "enterprise"],
        "nist_function": "MANAGE",
        "hks_dimension": "Reliability & Safety",
        "weight": 0.8,
    },
    {
        "id": "ops_07",
        "category": "ops",
        "text": "Are software supply-chain risks managed for AI dependencies (model weights, ML libraries, Python packages)?",
        "help_text": (
            "AI systems depend on complex software supply chains including ML frameworks, "
            "pre-trained weights, and external APIs.  Compromised dependencies can "
            "introduce malicious behaviour (e.g., supply-chain model poisoning)."
        ),
        "input_type": "checkbox",
        "options": [
            {"value": "sbom",             "label": "Software Bill of Materials (SBOM) maintained",                "risk_weight": 0},
            {"value": "dependency_scan",  "label": "Automated dependency vulnerability scanning",                 "risk_weight": 0},
            {"value": "pin_versions",     "label": "All dependencies pinned to verified versions",                "risk_weight": 0},
            {"value": "model_hash",       "label": "Cryptographic verification of model weights",                  "risk_weight": 0},
            {"value": "none",            "label": "No supply-chain controls in place",                           "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "enterprise"],
        "nist_function": "MAP",
        "hks_dimension": "Operational Security",
        "weight": 0.7,
    },
    {
        "id": "ops_08",
        "category": "ops",
        "text": "Is there a formal change management process for promoting model updates from development to production?",
        "help_text": (
            "Uncontrolled model updates can introduce regressions, bias, or security "
            "vulnerabilities.  A change management gate ensures each update is reviewed, "
            "tested, and approved before deployment."
        ),
        "input_type": "radio",
        "options": [
            {"value": "formal_gated",     "label": "Yes — formal gated process with documented approvals",          "risk_weight": 0},
            {"value": "informal",         "label": "Informal peer review before deployment",                         "risk_weight": 1},
            {"value": "ci_cd_no_gate",    "label": "CI/CD pipeline but no explicit approval gate",                  "risk_weight": 2},
            {"value": "no",              "label": "No change management — ad-hoc updates",                        "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "MANAGE",
        "hks_dimension": "Accountability",
        "weight": 0.7,
    },

    # ===================================================================
    # CATEGORY: COMPLIANCE & AUDIT
    # ===================================================================

    {
        "id": "comp_01",
        "category": "compliance",
        "text": "Which regulatory or compliance frameworks apply to this AI system?",
        "help_text": (
            "Identify all applicable frameworks.  Multiple frameworks may apply "
            "simultaneously (e.g., a healthcare AI might be subject to HIPAA, "
            "EU AI Act, and NIST AI RMF simultaneously)."
        ),
        "input_type": "checkbox",
        "options": [
            {"value": "nist_ai_rmf",      "label": "NIST AI RMF",                                              "risk_weight": 0},
            {"value": "eu_ai_act",        "label": "EU AI Act",                                               "risk_weight": 0},
            {"value": "gdpr",             "label": "GDPR",                                                    "risk_weight": 0},
            {"value": "ccpa",             "label": "CCPA / CPRA",                                            "risk_weight": 0},
            {"value": "hipaa",            "label": "HIPAA",                                                   "risk_weight": 0},
            {"value": "cmmc_l2",          "label": "CMMC Level 2",                                           "risk_weight": 0},
            {"value": "lloyds",           "label": "Lloyd's Market AI Guidelines",                           "risk_weight": 0},
            {"value": "iso_42001",        "label": "ISO/IEC 42001 (AI Management System)",                   "risk_weight": 0},
            {"value": "sox",              "label": "SOX (Sarbanes-Oxley)",                                   "risk_weight": 0},
            {"value": "none_known",       "label": "No specific compliance framework identified",             "risk_weight": 2},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Compliance",
        "weight": 1.0,
    },
    {
        "id": "comp_02",
        "category": "compliance",
        "text": "Is there a designated AI governance role or committee with authority over AI deployment decisions?",
        "help_text": (
            "Clear ownership prevents diffusion of responsibility.  An AI governance "
            "committee or designated Chief AI Officer (CAIO) role provides accountability "
            "for AI risk decisions."
        ),
        "input_type": "radio",
        "options": [
            {"value": "dedicated_committee","label": "Yes — dedicated AI governance committee with C-suite sponsorship", "risk_weight": 0},
            {"value": "existing_role",     "label": "Existing risk or compliance role covers AI governance",           "risk_weight": 1},
            {"value": "informal",          "label": "Informal ownership — no formal designation",                     "risk_weight": 2},
            {"value": "no",               "label": "No AI governance role or committee",                             "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Accountability",
        "weight": 1.0,
    },
    {
        "id": "comp_03",
        "category": "compliance",
        "text": "Is a written AI use policy published and acknowledged by all staff who use or oversee AI systems?",
        "help_text": (
            "A published AI use policy sets boundaries for acceptable use, clarifies "
            "employee responsibilities, and is a prerequisite for enforcement.  "
            "Acknowledgement creates an audit trail."
        ),
        "input_type": "radio",
        "options": [
            {"value": "published_signed",  "label": "Yes — published, and all relevant staff have signed acknowledgement",  "risk_weight": 0},
            {"value": "published_no_ack",  "label": "Policy published but acknowledgement not tracked",                     "risk_weight": 1},
            {"value": "draft",             "label": "Draft policy under development",                                       "risk_weight": 2},
            {"value": "no",               "label": "No AI use policy exists",                                             "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Transparency",
        "weight": 0.9,
    },
    {
        "id": "comp_04",
        "category": "compliance",
        "text": "Have third-party AI vendors been assessed under the organization's vendor risk management (VRM) programme?",
        "help_text": (
            "Third-party AI vendors may process sensitive data or provide core decision "
            "logic.  VRM assessments verify their security posture, contractual obligations, "
            "and sub-processor practices."
        ),
        "input_type": "radio",
        "options": [
            {"value": "not_applicable",    "label": "Not applicable — no third-party AI vendors used",                    "risk_weight": 0},
            {"value": "full_vrm",          "label": "Yes — all vendors assessed under formal VRM programme",             "risk_weight": 0},
            {"value": "partial",           "label": "Partial — major vendors assessed, others not",                      "risk_weight": 2},
            {"value": "no",               "label": "No — third-party vendors not assessed",                             "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "MAP",
        "hks_dimension": "Accountability",
        "weight": 0.8,
    },
    {
        "id": "comp_05",
        "category": "compliance",
        "text": "Is there a mechanism for affected individuals to contest or seek redress for AI-assisted decisions?",
        "help_text": (
            "The right to contestation and redress is enshrined in GDPR Article 22, "
            "EU AI Act Article 85, and various consumer protection laws.  This right "
            "must be operationalised, not just stated in policy."
        ),
        "input_type": "radio",
        "options": [
            {"value": "operational_process","label": "Yes — documented and operational redress process",               "risk_weight": 0},
            {"value": "policy_only",        "label": "Stated in policy but no operational process exists",              "risk_weight": 2},
            {"value": "not_applicable",     "label": "Not applicable — system does not make decisions affecting individuals", "risk_weight": 0},
            {"value": "no",               "label": "No contestation or redress mechanism",                            "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["hks", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Fairness & Equity",
        "weight": 0.8,
    },
    {
        "id": "comp_06",
        "category": "compliance",
        "text": "Is the AI system subject to regular internal or external audits?",
        "help_text": (
            "Periodic audits verify that controls remain effective over time and "
            "provide evidence of compliance for regulators.  Lloyd's market guidance "
            "and ISO/IEC 42001 both require periodic review cycles."
        ),
        "input_type": "radio",
        "options": [
            {"value": "external_internal",  "label": "Yes — both internal and external audits on a defined schedule",   "risk_weight": 0},
            {"value": "internal_only",      "label": "Internal audits only",                                            "risk_weight": 1},
            {"value": "ad_hoc",             "label": "Ad-hoc reviews with no defined schedule",                         "risk_weight": 2},
            {"value": "no",               "label": "No audits conducted",                                             "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Compliance",
        "weight": 0.8,
    },
    {
        "id": "comp_07",
        "category": "compliance",
        "text": "Is AI-related training provided to employees who build, deploy, or oversee AI systems?",
        "help_text": (
            "Security awareness and AI literacy training reduces human error, improves "
            "responsible use, and is required under CMMC Level 2 (AT.L2-3.2.1) and "
            "encouraged by NIST AI RMF GOVERN function."
        ),
        "input_type": "radio",
        "options": [
            {"value": "role_specific",     "label": "Yes — role-specific AI risk and governance training",              "risk_weight": 0},
            {"value": "general",           "label": "General AI awareness training for all relevant staff",             "risk_weight": 1},
            {"value": "ad_hoc",            "label": "Ad-hoc / self-directed training only",                            "risk_weight": 2},
            {"value": "no",               "label": "No AI-related training provided",                                 "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Accountability",
        "weight": 0.7,
    },
    {
        "id": "comp_08",
        "category": "compliance",
        "text": "Is the AI system documented in the organization's System Security Plan (SSP) or equivalent security baseline?",
        "help_text": (
            "The SSP documents the security controls applied to an information system. "
            "Including AI systems in the SSP ensures they are within scope for security "
            "reviews and CMMC or FedRAMP assessments."
        ),
        "input_type": "radio",
        "options": [
            {"value": "fully_documented",  "label": "Yes — fully documented in current SSP with control mappings",      "risk_weight": 0},
            {"value": "partially",         "label": "Partially documented — some components included",                  "risk_weight": 1},
            {"value": "not_included",      "label": "AI system not yet included in SSP",                               "risk_weight": 2},
            {"value": "no_ssp",            "label": "No SSP exists for this organization",                             "risk_weight": 3},
        ],
        "required": True,
        "frameworks": ["cmmc_l2", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Compliance",
        "weight": 0.9,
    },

    # ===================================================================
    # ADDITIONAL CONTEXTUAL QUESTIONS (all categories)
    # ===================================================================

    {
        "id": "meta_01",
        "category": "data",
        "text": "Provide the name of the AI system or tool being assessed.",
        "help_text": "This name will appear in all generated governance documents.",
        "input_type": "text",
        "options": [],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Accountability",
        "weight": 0.0,
    },
    {
        "id": "meta_02",
        "category": "data",
        "text": "Provide the name of the team or business unit responsible for this AI system.",
        "help_text": "This will appear as the system owner in all generated governance documents.",
        "input_type": "text",
        "options": [],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Accountability",
        "weight": 0.0,
    },
    {
        "id": "meta_03",
        "category": "compliance",
        "text": "Briefly describe the primary business purpose of the AI system (1–3 sentences).",
        "help_text": (
            "A clear purpose statement is required in SSP entries and policy documents. "
            "Be specific about what the system does and what decisions it supports."
        ),
        "input_type": "textarea",
        "options": [],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Transparency",
        "weight": 0.0,
    },
    {
        "id": "meta_04",
        "category": "compliance",
        "text": "Select the target compliance framework for the generated documents.",
        "help_text": (
            "The selected framework determines which controls and checklist items are "
            "emphasised in the output documents.  You can re-run the assessment with a "
            "different framework to generate alternative artifacts."
        ),
        "input_type": "select",
        "options": [
            {"value": "nist_ai_rmf",  "label": "NIST AI RMF",                        "risk_weight": 0},
            {"value": "hks",          "label": "HKS AI Risk Framework",              "risk_weight": 0},
            {"value": "cmmc_l2",      "label": "CMMC Level 2",                       "risk_weight": 0},
            {"value": "lloyds",       "label": "Lloyd's Market AI Guidelines",       "risk_weight": 0},
            {"value": "enterprise",   "label": "Enterprise Generic",                 "risk_weight": 0},
        ],
        "required": True,
        "frameworks": ["nist_ai_rmf", "hks", "cmmc_l2", "lloyds", "enterprise"],
        "nist_function": "GOVERN",
        "hks_dimension": "Compliance",
        "weight": 0.0,
    },
]

# fmt: on


# ---------------------------------------------------------------------------
# Derived lookup structures
# ---------------------------------------------------------------------------

def _build_questions_by_category(
    questions: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group questions by their ``category`` field.

    Args:
        questions: The master list of question dicts.

    Returns:
        A dict mapping each category id to its ordered list of questions.
        Categories are inserted in the order defined by :data:`CATEGORIES`.
    """
    result: dict[str, list[dict[str, Any]]] = {
        cat["id"]: [] for cat in CATEGORIES
    }
    for question in questions:
        cat_id = question["category"]
        if cat_id not in result:
            result[cat_id] = []
        result[cat_id].append(question)
    return result


QUESTIONS_BY_CATEGORY: dict[str, list[dict[str, Any]]] = (
    _build_questions_by_category(QUESTIONS)
)

# Convenience lookup: question_id → question dict
QUESTION_BY_ID: dict[str, dict[str, Any]] = {
    q["id"]: q for q in QUESTIONS
}

# Category ordered list for use in template iteration
CATEGORY_IDS: list[str] = [cat["id"] for cat in CATEGORIES]


# ---------------------------------------------------------------------------
# Public helper functions
# ---------------------------------------------------------------------------


def get_questions_for_framework(
    framework_id: str,
    include_meta: bool = True,
) -> list[dict[str, Any]]:
    """Return all questions relevant to a given compliance framework.

    Args:
        framework_id: One of the framework IDs defined in
            :data:`FRAMEWORK_METADATA` (e.g., ``"cmmc_l2"``).
        include_meta: If ``True`` (default), include metadata questions
            (those with ``weight == 0.0``) in the result.  Set to
            ``False`` to retrieve only scored questions.

    Returns:
        Ordered list of question dicts whose ``frameworks`` list contains
        ``framework_id``.

    Raises:
        ValueError: If ``framework_id`` is not a recognised framework.
    """
    if framework_id not in FRAMEWORK_BY_ID:
        valid = ", ".join(sorted(FRAMEWORK_BY_ID.keys()))
        raise ValueError(
            f"Unknown framework '{framework_id}'. Valid options: {valid}"
        )
    return [
        q for q in QUESTIONS
        if framework_id in q["frameworks"]
        and (include_meta or q["weight"] > 0.0)
    ]


def get_questions_for_category(
    category_id: str,
    framework_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return questions for a specific category, optionally filtered by framework.

    Args:
        category_id: One of ``"data"``, ``"model"``, ``"ops"``, or
            ``"compliance"``.
        framework_id: Optional framework filter.  When provided, only
            questions that include ``framework_id`` in their
            ``frameworks`` list are returned.

    Returns:
        Ordered list of question dicts for the requested category.

    Raises:
        ValueError: If ``category_id`` is not recognised.
    """
    valid_cats = {cat["id"] for cat in CATEGORIES}
    if category_id not in valid_cats:
        raise ValueError(
            f"Unknown category '{category_id}'. Valid options: {sorted(valid_cats)}"
        )
    questions = QUESTIONS_BY_CATEGORY.get(category_id, [])
    if framework_id is not None:
        if framework_id not in FRAMEWORK_BY_ID:
            valid = ", ".join(sorted(FRAMEWORK_BY_ID.keys()))
            raise ValueError(
                f"Unknown framework '{framework_id}'. Valid options: {valid}"
            )
        questions = [q for q in questions if framework_id in q["frameworks"]]
    return questions


def get_scored_questions(
    category_id: str | None = None,
    framework_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return questions that contribute to risk scoring (weight > 0).

    This excludes metadata/contextual questions such as system name,
    owner, and purpose that are used for document population but do not
    affect risk scores.

    Args:
        category_id: Optional category filter.  If provided, only
            questions from that category are returned.
        framework_id: Optional framework filter.

    Returns:
        List of scored question dicts.
    """
    base: list[dict[str, Any]] = QUESTIONS
    if category_id is not None:
        valid_cats = {cat["id"] for cat in CATEGORIES}
        if category_id not in valid_cats:
            raise ValueError(
                f"Unknown category '{category_id}'. "
                f"Valid options: {sorted(valid_cats)}"
            )
        base = QUESTIONS_BY_CATEGORY.get(category_id, [])
    if framework_id is not None:
        if framework_id not in FRAMEWORK_BY_ID:
            valid = ", ".join(sorted(FRAMEWORK_BY_ID.keys()))
            raise ValueError(
                f"Unknown framework '{framework_id}'. Valid options: {valid}"
            )
        base = [q for q in base if framework_id in q["frameworks"]]
    return [q for q in base if q["weight"] > 0.0]


def get_category_metadata(category_id: str) -> dict[str, Any]:
    """Return the metadata dict for a category by its id.

    Args:
        category_id: The category identifier string.

    Returns:
        Category metadata dict from :data:`CATEGORIES`.

    Raises:
        ValueError: If ``category_id`` is not found.
    """
    for cat in CATEGORIES:
        if cat["id"] == category_id:
            return cat
    raise ValueError(
        f"Unknown category '{category_id}'. "
        f"Valid options: {[c['id'] for c in CATEGORIES]}"
    )


def get_framework_metadata(framework_id: str) -> dict[str, Any]:
    """Return the metadata dict for a compliance framework by its id.

    Args:
        framework_id: The framework identifier string.

    Returns:
        Framework metadata dict from :data:`FRAMEWORK_METADATA`.

    Raises:
        ValueError: If ``framework_id`` is not found.
    """
    if framework_id not in FRAMEWORK_BY_ID:
        valid = ", ".join(sorted(FRAMEWORK_BY_ID.keys()))
        raise ValueError(
            f"Unknown framework '{framework_id}'. Valid options: {valid}"
        )
    return FRAMEWORK_BY_ID[framework_id]
