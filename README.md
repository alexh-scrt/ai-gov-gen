# AI Gov Gen

**AI Gov Gen** is a web application that guides teams through a structured AI risk assessment questionnaire and automatically generates governance checklists, System Security Plan (SSP) entries, and policy documents for AI tool deployments.

Built on established frameworks including the **HKS AI Risk Framework** and **NIST AI RMF**, it produces compliance-ready artifacts tailored for contexts such as CMMC Level 2, Lloyd's market requirements, and general enterprise AI governance.

---

## Features

- **Multi-step questionnaire wizard** covering data governance, model risk, operational security, and compliance categories aligned with HKS AI Risk Framework and NIST AI RMF
- **Automated risk scoring engine** that maps answers to Low / Medium / High / Critical risk levels per category and produces an overall AI deployment risk posture
- **One-click document generation** — governance checklist, SSP control entries, and a full AI use policy document populated with team-specific details
- **Export to DOCX and PDF** — formatted files ready for compliance reviewers or insertion into existing security documentation
- **Framework selector** — target output for CMMC Level 2, Lloyd's market AI guidelines, or generic enterprise governance

---

## Prerequisites

- Python 3.11 or newer
- `pip` package manager
- On Linux, WeasyPrint requires system libraries for PDF rendering:
  ```bash
  sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b
  ```
  See the [WeasyPrint installation docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) for macOS and Windows instructions.

---

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/ai_gov_gen.git
   cd ai_gov_gen
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

---

## Running the Application

```bash
# Development server (auto-reload enabled)
flask --app ai_gov_gen run --debug
```

Open your browser at `http://127.0.0.1:5000`.

To bind to a different host or port:
```bash
flask --app ai_gov_gen run --host 0.0.0.0 --port 8080
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FLASK_SECRET_KEY` | `dev-secret-change-me` | Secret key for session signing. **Must be changed in production.** |
| `FLASK_ENV` | `production` | Set to `development` for debug mode |
| `AI_GOV_GEN_UPLOAD_FOLDER` | `./output` | Directory where generated documents are saved |

Create a `.env` file in the project root to override defaults:
```dotenv
FLASK_SECRET_KEY=your-very-long-random-secret
FLASK_ENV=development
```

---

## Running Tests

```bash
pytest
```

To include coverage reporting:
```bash
pytest --cov=ai_gov_gen --cov-report=term-missing
```

---

## Project Structure

```
ai_gov_gen/
├── __init__.py          # Flask application factory
├── questions.py         # Full categorized question bank
├── assessor.py          # Risk scoring engine
├── generator.py         # Jinja2-powered document renderer
├── exporter.py          # DOCX and PDF export
├── routes.py            # Flask route handlers
└── templates/
    ├── base.html        # Bootstrap 5 base layout
    ├── questionnaire.html
    ├── results.html
    └── policy_doc.html  # PDF-optimized policy document template
tests/
├── test_assessor.py
└── test_generator.py
pyproject.toml
requirements.txt
README.md
```

---

## Compliance Frameworks Supported

| Framework | Description |
|---|---|
| **NIST AI RMF** | National Institute of Standards and Technology AI Risk Management Framework |
| **HKS AI Risk Framework** | Harvard Kennedy School Responsible AI framework |
| **CMMC Level 2** | Cybersecurity Maturity Model Certification — AI-adjacent controls |
| **Lloyd's Market** | Lloyd's of London AI guidelines for insurance underwriting contexts |
| **Enterprise Generic** | General-purpose enterprise AI governance baseline |

---

## License

MIT License — see [LICENSE](LICENSE) for details.
