# AI Gov Gen

**AI Gov Gen** is a web application that guides teams through a structured AI risk
assessment questionnaire and automatically generates governance checklists, System
Security Plan (SSP) entries, and policy documents for AI tool deployments.

Built on established frameworks including the **HKS AI Risk Framework** and
**NIST AI RMF**, it produces compliance-ready artifacts tailored for contexts such
as CMMC Level 2, Lloyd's market requirements, and general enterprise AI governance.

---

## Features

| Feature | Details |
|---|---|
| **Multi-step questionnaire wizard** | 4 categories: Data Governance, Model Risk, Operational Security, Compliance & Audit |
| **Automated risk scoring** | Weighted scoring engine → Low / Medium / High / Critical per category and overall |
| **Governance checklist** | Actionable control items ordered by severity, mapped to framework control references |
| **SSP control entries** | System Security Plan entries with implementation status, findings, and remediation actions |
| **AI use policy document** | Full 11-section policy populated with system-specific details from questionnaire responses |
| **DOCX & PDF export** | Professionally formatted files ready for compliance reviewers |
| **Framework selector** | Target NIST AI RMF, HKS, CMMC Level 2, Lloyd's Market AI Guidelines, or Enterprise Generic |

---

## Compliance Frameworks Supported

| Framework | Description |
|---|---|
| **NIST AI RMF** | National Institute of Standards and Technology AI Risk Management Framework (AI 100-1) |
| **HKS AI Risk Framework** | Harvard Kennedy School Responsible AI Framework |
| **CMMC Level 2** | Cybersecurity Maturity Model Certification — AI-adjacent controls for defense contractors |
| **Lloyd's Market** | Lloyd's of London AI Principles and Market Guidance for insurance contexts |
| **Enterprise Generic** | ISO/IEC 42001-aligned baseline for any organization deploying AI systems |

---

## Prerequisites

- **Python 3.11 or newer**
- `pip` package manager
- On **Linux**, WeasyPrint requires system-level libraries for PDF rendering:
  ```bash
  # Debian/Ubuntu
  sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \
      libffi-dev libjpeg-dev libopenjp2-7 libssl-dev

  # Red Hat / CentOS / Fedora
  sudo dnf install pango harfbuzz fontconfig freetype
  ```
- On **macOS** (Homebrew):
  ```bash
  brew install pango
  ```
- On **Windows**: See the
  [WeasyPrint installation docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows)
  for GTK runtime instructions.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-org/ai_gov_gen.git
cd ai_gov_gen
```

### 2. Create and activate a virtual environment

```bash
# Create
python -m venv .venv

# Activate (macOS / Linux)
source .venv/bin/activate

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

For development (includes `pytest` and `pytest-cov`):

```bash
pip install -e ".[dev]"
```

---

## Running the Application

### Development server (auto-reload enabled)

```bash
flask --app ai_gov_gen run --debug
```

Open your browser at **http://127.0.0.1:5000**.

### Custom host and port

```bash
flask --app ai_gov_gen run --host 0.0.0.0 --port 8080 --debug
```

### Production (Gunicorn example)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 "ai_gov_gen:create_app()"
```

---

## Configuration

Configuration is applied via environment variables.  Create a `.env` file in the
project root and set any of the following:

```dotenv
# Required in production — use a long random string
FLASK_SECRET_KEY=your-very-long-random-secret-key

# Optional overrides
FLASK_ENV=development
AI_GOV_GEN_UPLOAD_FOLDER=./output
```

| Variable | Default | Description |
|---|---|---|
| `FLASK_SECRET_KEY` | `dev-secret-change-me` | Secret key for session signing. **Must be changed in production.** |
| `FLASK_ENV` | `production` | Set to `development` to enable debug mode and auto-reload |
| `AI_GOV_GEN_UPLOAD_FOLDER` | `./output` | Directory where generated documents are saved temporarily |

> **Security note:** The default secret key is a placeholder and must be replaced
> with a cryptographically random value in any environment accessible to others.
> Generate a suitable value with:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

---

## Usage Guide

### Step 1 — Open the application

Navigate to `http://127.0.0.1:5000` and click **Start Free Assessment** on the
landing page.

### Step 2 — System Setup (Step 1 of 5)

Provide:
- **AI system name** — this will appear in all generated documents
- **System owner / team name** — the responsible business unit
- **System purpose** — a 1–3 sentence description of what the AI system does
- **Target compliance framework** — select the standard most relevant to your context

### Step 3 — Answer questionnaire categories (Steps 2–5)

Progress through four risk categories. Each question includes:
- A **help text** explaining why the question matters
- **Risk indicator dots** (● green = low risk, ● orange = medium, ● red = high)
- A **NIST AI RMF function tag** and **HKS dimension tag** for traceability

> **Tip:** Unanswered questions are scored at the maximum risk weight.
> Answer as accurately as possible even if the situation is partial or in-progress.

Use the **Back** button or click any step pill at the top to revisit earlier answers.

### Step 4 — Submit and review results

After completing the final category step, click **Submit & Generate Documents**.

The Results page shows:
- **Overall risk score** (0–100) and risk level (Low / Medium / High / Critical)
- **Per-category scores** with progress bars
- **Governance Checklist** tab — actionable control items ordered by severity
- **SSP Entries** tab — System Security Plan control entries
- **AI Use Policy** tab — preview of the generated policy sections
- **Score Detail** tab — per-question breakdown of how the score was calculated

### Step 5 — Download documents

Click **Download DOCX** or **Download PDF** from the results page or the
download buttons in the left sidebar.

| Format | Best for |
|---|---|
| **DOCX** | Editing in Microsoft Word, adding organisation-specific content, mail merge |
| **PDF** | Sharing with reviewers, printing, submitting to auditors |

---

## Project Structure

```
ai_gov_gen/
├── __init__.py          # Flask application factory
├── questions.py         # Full categorized question bank (NIST AI RMF / HKS aligned)
├── assessor.py          # Weighted risk scoring engine
├── generator.py         # Jinja2-powered governance document renderer
├── exporter.py          # DOCX (python-docx) and PDF (WeasyPrint) export
├── routes.py            # Flask route handlers and Blueprint
└── templates/
    ├── base.html            # Bootstrap 5 base layout with navbar and footer
    ├── index.html           # Landing page
    ├── questionnaire.html   # Multi-step wizard form
    ├── results.html         # Risk scores, checklist, SSP, policy preview
    ├── about.html           # About / framework information page
    ├── error.html           # Generic HTTP error page
    └── policy_doc.html      # PDF-optimized policy document template
tests/
├── __init__.py
├── test_app_factory.py  # create_app factory tests
├── test_questions.py    # Question bank structure tests
├── test_assessor.py     # Scoring engine unit tests
├── test_generator.py    # Document generation tests
└── test_exporter.py     # DOCX/PDF export tests
pyproject.toml
requirements.txt
README.md
```

---

## Running Tests

```bash
pytest
```

With coverage reporting:

```bash
pytest --cov=ai_gov_gen --cov-report=term-missing
```

Run a specific test file:

```bash
pytest tests/test_assessor.py -v
```

Run tests matching a keyword:

```bash
pytest -k "test_score" -v
```

> **Note on PDF tests:** Tests that invoke WeasyPrint require the system-level
> Pango/HarfBuzz libraries to be installed (see Prerequisites above).
> On CI environments without these libraries, PDF tests will fail with an
> `ImportError` or `OSError`. The DOCX-only tests will still pass.

---

## Architecture Overview

```
Browser
  │
  ▼
Flask app (ai_gov_gen/__init__.py: create_app)
  │
  ├── Blueprint: main_bp (routes.py)
  │     ├── GET  /               → index.html
  │     ├── GET  /questionnaire  → questionnaire.html (wizard step)
  │     ├── POST /questionnaire  → save answers → redirect to next step
  │     ├── GET  /results        → score + generate → results.html
  │     ├── GET  /download/docx  → export_docx_from_assessment → send_file
  │     ├── GET  /download/pdf   → export_pdf_from_assessment → send_file
  │     ├── GET  /about          → about.html
  │     └── POST/GET /reset      → clear session → redirect
  │
  ├── questions.py  — Question bank, category metadata, framework metadata
  ├── assessor.py   — score_responses() → AssessmentResult
  ├── generator.py  — generate_all() → GeneratedArtifacts
  │                    ├── generate_checklist()       → GovernanceChecklist
  │                    ├── generate_ssp_entries()     → list[SSPEntry]
  │                    ├── generate_policy_document() → PolicyDocument
  │                    └── render_policy_html()       → HTML string
  └── exporter.py   — export_docx_to_bytes() / export_pdf_from_html()
```

### Session state

Questionnaire responses are stored in the Flask session (a signed cookie).
The session holds:

| Key | Type | Description |
|---|---|---|
| `responses` | `dict` | All question answers accumulated across wizard steps |
| `current_step` | `int` | Current wizard step index (0-based) |
| `framework_id` | `str` | Selected compliance framework id |

No database is required — all state is ephemeral per browser session.

---

## Extending the Question Bank

To add new questions, edit `ai_gov_gen/questions.py` and append entries to
the `QUESTIONS` list following the documented schema:

```python
{
    "id": "data_09",             # Unique identifier
    "category": "data",          # data | model | ops | compliance
    "text": "Question text?",
    "help_text": "Explanatory hint.",
    "input_type": "radio",        # radio | checkbox | text | select | textarea
    "options": [
        {"value": "yes", "label": "Yes",  "risk_weight": 0},
        {"value": "no",  "label": "No",   "risk_weight": 3},
    ],
    "required": True,
    "frameworks": ["nist_ai_rmf", "enterprise"],
    "nist_function": "GOVERN",   # GOVERN | MAP | MEASURE | MANAGE
    "hks_dimension": "Accountability",
    "weight": 0.8,                # 0.0 (meta/no scoring) to 1.0 (maximum weight)
}
```

> Questions with `weight == 0.0` are used for metadata collection only
> (system name, owner, purpose) and do not affect risk scores.

---

## Adding a New Compliance Framework

1. Add a framework entry to `FRAMEWORK_METADATA` in `ai_gov_gen/questions.py`.
2. Add the framework id to the `frameworks` lists of relevant questions.
3. Add checklist library items and SSP control templates in `ai_gov_gen/generator.py`
   referencing the new framework id.
4. Add the framework to `SUPPORTED_FRAMEWORKS` in `ai_gov_gen/__init__.py`.

---

## Development Notes

### Code style

- Python 3.11+ with type hints on all public functions.
- PEP 8 compliant; docstrings on all public functions and classes.
- No external dependencies beyond those declared in `pyproject.toml`.

### Running without WeasyPrint

PDF export depends on WeasyPrint and its system dependencies. If you only need
DOCX export during development, all PDF-related functionality is isolated in
`exporter.py` and will raise an `ExportError` rather than crashing the application
if WeasyPrint is unavailable.

### Templates

All Jinja2 templates extend `base.html`. The `policy_doc.html` template is
rendered separately for PDF generation and is optimised for WeasyPrint's CSS
print model (CSS `@page` rules, headers, footers, page-break control).

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/my-feature`.
3. Add tests for any new functionality.
4. Ensure all tests pass: `pytest`.
5. Submit a pull request with a clear description of the change.

---

## Acknowledgements

Built on:
- [NIST AI Risk Management Framework (AI 100-1)](https://airc.nist.gov/)
- [Harvard Kennedy School Responsible AI Framework](https://www.hks.harvard.edu/)
- [NIST SP 800-171 / CMMC 2.0](https://www.acq.osd.mil/cmmc/)
- [Lloyd's of London AI Principles](https://www.lloyds.com/)
- [ISO/IEC 42001 AI Management System Standard](https://www.iso.org/standard/81230.html)
