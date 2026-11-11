<div align="center">

# ContentPilot AI

**AI content planning and publishing workflows for multi-channel marketing teams**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-REST%20API-009688?style=flat-square&logo=fastapi&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-content%20workspace-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-data%20layer-D71F00?style=flat-square)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?style=flat-square&logo=pytest&logoColor=white)

[Features](#features) · [Quick start](#quick-start) · [Architecture](#architecture) · [Current status](#current-status) · [Contributing](#contributing)

</div>

---

ContentPilot AI is a content marketing platform for managing brand projects, planning campaigns, generating channel-ready copy, and coordinating publishing workflows. It combines a FastAPI backend, a Streamlit workspace, and a SQLAlchemy data layer with SQLite or PostgreSQL.

The application brings the content workflow together:

**Brand brief → content calendar → AI-assisted copy → review → publishing workflow → performance insights**

![Projects workspace](docs/screenshots/01_projects.png)

## Features

| Area | What it does |
|---|---|
| Brand workspaces | Organize projects by niche, audience, website, and tone of voice. |
| Content planning | Generate monthly ideas, dates, channels, content types, and seasonal context. |
| AI-assisted writing | Generate copy from a content plan or a short brief using OpenAI when configured, with a local fallback. |
| A/B variants | Create and compare two copy variants for a content-plan item. |
| Publishing workflows | Approve planned content, request a publication, and inspect its status in the publication log. |
| Performance overview | Aggregate channel metrics and review content results. |
| REST API | Use the documented API for projects, accounts, plans, content, publications, analytics, and tests. |

### Integrations

The codebase contains channel adapters for Telegram, VK, Instagram, WordPress, and Mailchimp. Production use requires validating each adapter against the provider's current API, permissions, and account configuration. See [Current status](#current-status) before enabling real publishing.

See [channel setup and live acceptance notes](docs/INTEGRATIONS.md) for the required credentials, account prerequisites, and prototype limitations. Track remaining delivery steps in [submission readiness](docs/SUBMISSION_READINESS.md). A starter configuration is provided in `.env.example`; keep actual secrets in a local `.env` file, which must never be committed.

## Quick start

### Requirements

- Python 3.10+
- PostgreSQL for a shared deployment; SQLite is the local default
- An OpenAI API key only if you want to use OpenAI for content generation

### Install on Windows

Run these commands in PowerShell from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Run the application

Start the API in the first terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Start the web workspace in a second terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run frontend/streamlit_app.py
```

| Service | Address |
|---|---|
| Content workspace | <http://localhost:8501> |
| API documentation | <http://localhost:8000/docs> |
| Health endpoint | <http://localhost:8000/health> |

### Optional: load sample workspace data

```powershell
.\.venv\Scripts\python.exe scripts/seed_demo.py
```

The seed script creates a new sample project each time it runs. Use a separate database if you want a clean workspace.

## Configuration

Settings are read from environment variables or a local `.env` file. Keep credentials out of Git and logs.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/content_platform.db` | SQLAlchemy database URL. PostgreSQL uses `postgresql+psycopg://...`. |
| `POSTING_MODE` | `demo` | Selects the local no-send mode or the configured channel adapters. |
| `OPENAI_API_KEY` | empty | Enables OpenAI-backed plan and copy generation. |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name. |
| `AI_FALLBACK_LOCAL` | `true` | Allows local generation if an OpenAI request fails. |
| `API_BASE` | `http://localhost:8000` | FastAPI URL used by the Streamlit workspace. |
| `TELEGRAM_BOT_TOKEN` | empty | Telegram bot credentials. |
| `VK_ACCESS_TOKEN` | empty | VK API credentials. |
| `IG_ACCESS_TOKEN` | empty | Instagram Graph API credentials. |
| `WP_URL`, `WP_USER`, `WP_APP_PASSWORD` | empty | WordPress site and application credentials. |
| `MAILCHIMP_API_KEY`, `MAILCHIMP_SERVER`, `MAILCHIMP_AUDIENCE_ID`, `MAILCHIMP_REPLY_TO` | empty | Mailchimp API key, data-center prefix, audience, and authorized reply-to address. |

Never commit `.env` or production credentials. Before enabling real publishing, verify permissions and destinations using test accounts owned by you or explicitly authorized by the account owner.

## Architecture

```text
Streamlit workspace ── HTTP/JSON ──> FastAPI ──> application services
                                          │             ├── AI content generation
                                          │             ├── channel publishing adapters
                                          │             └── analytics and A/B evaluation
                                          └── SQLAlchemy ──> SQLite / PostgreSQL
```

| Path | Responsibility |
|---|---|
| `app/main.py` | FastAPI application, health endpoint, and application scheduler. |
| `app/api/routes/endpoints.py` | REST API routes. |
| `app/models/` and `app/schemas/` | SQLAlchemy models and Pydantic API schemas. |
| `app/services/ai/` | Content-plan and copy generation. |
| `app/services/posting/` | Channel adapters and publication records. |
| `app/services/analytics/` | Metric aggregation and A/B result calculations. |
| `app/workers/tasks.py` | Celery tasks for deployments using a worker and broker. |
| `frontend/streamlit_app.py` | Streamlit content workspace. |
| `tests/` | API tests. |

## API overview

Interactive API reference: <http://localhost:8000/docs>

| Method | Endpoint | Purpose |
|---|---|---|
| `GET`, `POST` | `/api/projects` | List and create brand projects. |
| `GET`, `POST` | `/api/projects/{id}/accounts` | List and connect project channels. |
| `GET`, `POST` | `/api/plans`, `/api/plans/generate` | List or generate content plans. |
| `PATCH` | `/api/plans/{id}/approve` | Approve a plan item. |
| `GET`, `POST` | `/api/content`, `/api/content/generate` | List content or generate plan variants. |
| `POST` | `/api/content/brief` | Generate content from a short brief. |
| `POST` | `/api/publish` | Start a publication workflow. |
| `POST` | `/api/autopost/run-due` | Process due approved items. |
| `GET`, `POST` | `/api/analytics/*` | Synchronize and retrieve analytics. |
| `GET`, `POST` | `/api/ab-tests` | List and create A/B tests. |
| `POST` | `/api/ab-tests/{id}/evaluate` | Refresh metrics and evaluate an A/B test. |

## Current status

The application runs locally and the API test suite covers project creation, plan generation, copy generation, publishing workflow, analytics, and A/B evaluation. Provider-specific publishing and analytics still need production verification.

| Capability | Current implementation |
|---|---|
| Content generation | OpenAI integration when configured; local template fallback otherwise. |
| Publishing | The default `POSTING_MODE=demo` records a local result without contacting a channel. Live adapters exist, but their provider APIs and credentials have not been verified end to end. See [channel setup and live acceptance notes](docs/INTEGRATIONS.md). |
| Channel credentials | The account API masks the submitted token; it does not persist that secret for later adapter use. Adapters currently read provider credentials from environment settings. |
| Analytics | Metrics are synthesized locally; provider-backed metric collection is not implemented. |
| A/B evaluation | Compares available metrics using a simple minimum-sample rule; it does not calculate statistical significance. |
| Authentication | End-user authentication, authorization, and tenant isolation are not implemented. |

Treat these as implementation boundaries, not claims about provider certification. Before using the service with production accounts or customer data, complete provider-specific integration tests, secure secret storage, access control, and deployment hardening.

## Tests

Install dependencies, then run the test suite against a temporary SQLite database:

```powershell
$db = Join-Path $env:TEMP ("contentpilot-tests-" + [guid]::NewGuid().ToString("N") + ".db")
$env:DATABASE_URL = "sqlite:///" + $db.Replace("\", "/")
.\.venv\Scripts\python.exe -m pytest -q
$testResult = $LASTEXITCODE
Remove-Item -LiteralPath $db, ($db + "-shm"), ($db + "-wal") -Force -ErrorAction SilentlyContinue
Remove-Item Env:DATABASE_URL
if ($testResult -ne 0) { exit $testResult }
```

## Screenshots and walkthrough

The [screenshots](docs/screenshots/01_projects.png) show the main workspace. A [full workflow recording](docs/screencast.webm) and the [technical specification](docs/Technical_Specification.docx) are also available.

To refresh the screenshots and recording, install Playwright's browser once:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

For evidence capture, use an isolated SQLite database and demo mode in each of the three PowerShell terminals. This keeps the capture records separate from your working data and prevents any real provider calls:

```powershell
New-Item -ItemType Directory -Force .capture-temp | Out-Null
$env:DATABASE_URL = "sqlite:///./.capture-temp/capture.db"
$env:POSTING_MODE = "demo"
$env:OPENAI_API_KEY = ""
```

In the first terminal, start the API; in the second, start Streamlit with the same variables set; then in the third, run:

```powershell
.\.venv\Scripts\python.exe scripts/make_screenshots.py
```

The capture script checks that the API is in demo mode, then adds a synthetic project, Instagram plan, A/B variants, demo publications, simulated analytics, and an A/B result before recording the UI. `.capture-temp/` is ignored by Git.

## Contributing

Contributions are welcome. Have an idea or found a bug? [Open an issue](https://github.com/nifontovoleg/ContentPilot-AI/issues) to discuss it, or submit a pull request with a focused change and tests. Useful contributions include provider integration tests, secure credential handling, real analytics adapters, and deployment hardening.

Before submitting a pull request:

1. Create a focused branch and describe the user impact of the change.
2. Run `python -m pytest -q` and add or update tests for changed behavior.
3. Never include API keys, account tokens, personal data, or `.env` files.
4. Document configuration changes and provider-specific requirements.

The repository does not yet include a `CONTRIBUTING.md` or a license. Contribution and reuse terms should be documented before accepting external contributions or describing the project as open source.

Want to help build ContentPilot AI? [Open an issue](https://github.com/nifontovoleg/ContentPilot-AI/issues) or send a focused pull request with tests.
