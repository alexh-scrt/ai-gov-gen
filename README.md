# AI Gov Gen

> From questionnaire to compliance-ready governance docs in seconds.

**AI Gov Gen** is a web application that guides teams through a structured AI risk assessment questionnaire and automatically generates governance checklists, System Security Plan (SSP) entries, and policy documents for AI tool deployments. Built on the **HKS AI Risk Framework** and **NIST AI RMF**, it produces compliance-ready artifacts tailored for CMMC Level 2, Lloyd's market requirements, and general enterprise AI governance. Teams answer categorized questions about their AI system and receive downloadable, formatted policy documents instantly.

---

## Quick Start

**Requirements:** Python 3.11+

```bash
# 1. Clone the repository
git clone https://github.com/your-org/ai_gov_gen.git
cd ai_gov_gen

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the development server
flask --app ai_gov_gen run --debug
```

Open your browser at **http://localhost:5000**, select a compliance framework, and start your AI risk assessment.

---

## Features

- **Multi-step questionnaire wizard** — four risk categories (Data Governance, Model Risk, Operational Security, Compliance & Audit) aligned with HKS AI Risk Framework and NIST AI RMF
- **Automated risk scoring engine** — weighted scoring maps responses to Low / Medium / High / Critical risk levels per category and produces an overall AI deployment risk posture
- **One-click document generation** — governance checklist, SSP control entries, and a full AI use policy document populated with your team's specific details
- **DOCX and PDF export** — formatted files ready for compliance reviewers or direct insertion into existing security documentation
- **Framework selector** — target output for CMMC Level 2, Lloyd's market AI guidelines, or generic enterprise governance

---

## Usage Examples

### Running the web application

```bash
# Development
flask --app ai_gov_gen run --debug

# Production (example with gunicorn)
gunicorn -w 4 'ai_gov_gen:create_app()'
```

### Using the application factory directly

```python
from ai_gov_gen import create_app

app = create_app()

# Override config via environment variables
import os
os.environ["SECRET_KEY"] = "your-secret-key"
os.environ["OUTPUT_FOLDER"] = "/tmp/ai_gov_gen_exports"

app = create_app()
app.run()
```

### Generating documents programmatically

```python
from ai_gov_gen import create_app
from ai_gov_gen.assessor import score_responses
from ai_gov_gen.generator import generate_all
from ai_gov_gen.exporter import export_docx_to_bytes

app = create_app()

with app.app_context():
    # Score a set of questionnaire responses
    responses = {
        "data_01": "yes",
        "data_02": ["encryption", "access_control"],
        "model_01": "third_party",
        # ... additional responses
    }
    assessment = score_responses(responses, framework_id="cmmc_l2")

    # Generate all governance artifacts
    artifacts = generate_all(assessment)

    # Export to DOCX bytes for download or storage
    docx_bytes = export_docx_to_bytes(
        artifacts.checklist,
        artifacts.ssp_entries,
        artifacts.policy_document
    )

    with open("ai_governance_report.docx", "wb") as f:
        f.write(docx_bytes)
```

### Running tests

```bash
pytest

# With coverage report
pytest --cov=ai_gov_gen --cov-report=term-missing
```

---

## Project Structure

```
ai_gov_gen/
├── pyproject.toml                  # Project metadata and build config
├── requirements.txt                # Pinned runtime dependencies
├── README.md                       # This file
│
├── ai_gov_gen/
│   ├── __init__.py                 # Flask application factory
│   ├── questions.py                # Question bank organized by risk category
│   ├── assessor.py                 # Risk scoring engine and AssessmentResult
│   ├── generator.py                # Document generation (checklist, SSP, policy)
│   ├── exporter.py                 # DOCX and PDF export via python-docx / WeasyPrint
│   ├── routes.py                   # Flask route handlers and wizard logic
│   │
│   └── templates/
│       ├── base.html               # Bootstrap 5 base layout
│       ├── index.html              # Landing page / framework selector
│       ├── questionnaire.html      # Multi-step wizard form
│       ├── results.html            # Risk scores, checklist, and download links
│       ├── policy_doc.html         # Print-ready policy document (WeasyPrint)
│       ├── about.html              # Framework and usage information
│       └── error.html              # Generic HTTP error page
│
└── tests/
    ├── __init__.py
    ├── test_app_factory.py         # Application factory tests
    ├── test_questions.py           # Question bank structure tests
    ├── test_assessor.py            # Scoring and risk-level mapping tests
    ├── test_generator.py           # Document generation tests
    └── test_exporter.py            # DOCX and PDF export tests
```

---

## Configuration

AI Gov Gen is configured via environment variables. All settings have sensible defaults for local development.

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key` | Flask session secret key — **change in production** |
| `OUTPUT_FOLDER` | `./exports` | Directory where generated DOCX/PDF files are written |
| `FLASK_ENV` | `production` | Set to `development` to enable debug mode |
| `MAX_CONTENT_LENGTH` | `16777216` (16 MB) | Maximum request body size |

**Example `.env` setup:**

```bash
export SECRET_KEY="your-strong-random-secret"
export OUTPUT_FOLDER="/var/app/exports"
export FLASK_ENV="production"
```

For production deployments, ensure `SECRET_KEY` is set to a cryptographically random value and `OUTPUT_FOLDER` is writable by the application process.

---

## Supported Frameworks

| Framework | Description |
|---|---|
| **NIST AI RMF** | NIST AI Risk Management Framework — general-purpose AI governance baseline |
| **CMMC Level 2** | Cybersecurity Maturity Model Certification — defense contractor requirements |
| **Lloyd's Market** | Lloyd's of London AI guidelines for insurance market participants |
| **Enterprise Generic** | Framework-agnostic governance suitable for internal enterprise policies |

---

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

*Built with [Jitter](https://github.com/jitter-ai) - an AI agent that ships code daily.*
