# Moveworks ↔ Jira Integration

> End-to-end reference implementation for exposing Jira actions through a
> Moveworks bot, built with Python/Flask and Moveworks Creator Studio Action
> Plugins.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Supported Use Cases](#supported-use-cases)
4. [Prerequisites](#prerequisites)
5. [Quick Start](#quick-start)
6. [API Reference](#api-reference)
7. [Moveworks Integration](#moveworks-integration)
8. [Project Structure](#project-structure)
9. [Running Tests](#running-tests)
10. [Troubleshooting](#troubleshooting)

---

## Overview

This project bridges the **Moveworks AI platform** with **Jira Cloud** so that
employees can manage Jira tickets through natural-language conversation without
ever leaving Slack, Teams, or any other channel Moveworks is deployed in.

### What is Moveworks?

[Moveworks](https://www.moveworks.com/) is an AI-powered employee support
platform.  Its **Creator Studio** lets you build custom conversational
workflows that call external REST APIs via *Action Plugins*.  The bot handles
natural-language understanding, disambiguation, and response formatting; your
plugin just needs to expose clean HTTP endpoints.

### What does this project provide?

| Layer | Technology | Purpose |
|---|---|---|
| **Jira Client** | Python (`jira_client.py`) | Typed wrapper around Jira REST API v3 |
| **API Server** | Flask (`app.py`) | REST endpoints that Moveworks calls |
| **Moveworks Plugins** | YAML (`moveworks/plugins/`) | Action Plugin definitions to import into Creator Studio |

---

## Architecture

```
Employee (Slack / Teams)
        │ natural language
        ▼
┌─────────────────────────┐
│   Moveworks Bot Engine  │  ← NLU, disambiguation, response rendering
│  (Creator Studio flows) │
└────────────┬────────────┘
             │ HTTP (Action Plugin)
             ▼
┌─────────────────────────┐
│   Flask API  (app.py)   │  ← This repo – deployed in your infra
│   /jira/issue  etc.     │
└────────────┬────────────┘
             │ Jira REST API v3
             ▼
┌─────────────────────────┐
│   Jira Cloud            │
│   yourcompany.atlassian │
└─────────────────────────┘
```

The Flask API lives inside your network (or behind your API gateway) so your
Jira credentials are never exposed to Moveworks directly.

---

## Supported Use Cases

| # | Employee utterance (examples) | Plugin |
|---|---|---|
| 1 | *"Create a Jira bug in the OPS project"* | `create_issue` |
| 2 | *"What is the status of OPS-42?"* | `get_issue` |
| 3 | *"Update OPS-42 priority to High"* | `update_issue` |
| 4 | *"Find my open Jira tickets"* | `search_issues` |
| 5 | *"Add a comment to OPS-42: server restarted"* | `add_comment` |
| 6 | *"Move OPS-42 to In Progress"* | `transition_issue` |
| 7 | *"Assign IT-100 to alice@company.com"* | `assign_issue` |

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python ≥ 3.10 | `python --version` |
| Jira Cloud account | Site admin or project admin to generate an API token |
| Jira API token | [Generate here](https://id.atlassian.com/manage-profile/security/api-tokens) |
| Moveworks tenant | Creator Studio access required to import plugins |
| Public HTTPS endpoint | The Flask server must be reachable from Moveworks (e.g. behind a reverse proxy or deployed to cloud) |

---

## Quick Start

### 1. Clone and set up

```bash
git clone https://github.com/kayathri3/Moveworks_Jira.git
cd Moveworks_Jira
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your Jira URL, email, and API token
```

`.env` variables:

| Variable | Description | Example |
|---|---|---|
| `JIRA_BASE_URL` | Your Atlassian domain | `https://acme.atlassian.net` |
| `JIRA_EMAIL` | Jira account email | `bot@acme.com` |
| `JIRA_API_TOKEN` | Jira API token | `ATATxxxxxxx` |
| `PORT` | Server port (default `5000`) | `5000` |

### 3. Run the server

```bash
python app.py
# Server listening on http://0.0.0.0:5000
```

Verify it is up:

```bash
curl http://localhost:5000/health
# {"status": "ok"}
```

### 4. Expose the server to Moveworks

Moveworks must be able to reach your Flask server over HTTPS.  Options:

- **Cloud deployment**: Deploy to AWS ECS / GCP Cloud Run / Azure App Service
- **Local development**: Use [ngrok](https://ngrok.com/) — `ngrok http 5000`
- **Reverse proxy**: Sit behind nginx/Caddy with a TLS certificate

### 5. Import Action Plugins into Creator Studio

1. Open **Moveworks Creator Studio** → **Plugins** → **Action Plugins**.
2. Click **Import Plugin**.
3. Upload each YAML file from `moveworks/plugins/`.
4. Set the environment variable `JIRA_INTEGRATION_BASE_URL` to your server's
   public URL (e.g. `https://jira-bot.acme.com`).
5. Test each plugin using the Creator Studio playground.

---

## API Reference

All endpoints return JSON.  The server expects `Content-Type: application/json`
on requests with a body.

### `GET /health`

Liveness probe.

```json
{"status": "ok"}
```

---

### `POST /jira/issue` – Create issue

**Body**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `project_key` | string | ✅ | | e.g. `"OPS"` |
| `summary` | string | ✅ | | Issue title |
| `issue_type` | string | ✅ | | `"Bug"`, `"Task"`, `"Story"` |
| `description` | string | | `""` | Detailed description |
| `priority` | string | | `"Medium"` | `"Highest"` … `"Lowest"` |
| `assignee` | string | | | Jira `accountId` |
| `labels` | string[] | | `[]` | Label strings |

**Response** `201`

```json
{"key": "OPS-42", "id": "10042", "url": "https://acme.atlassian.net/browse/OPS-42"}
```

---

### `GET /jira/issue/<issue_key>` – Get issue

**Response** `200`

```json
{
  "key": "OPS-42",
  "summary": "Fix login bug",
  "status": "In Progress",
  "priority": "High",
  "issue_type": "Bug",
  "assignee": "Alice Smith",
  "reporter": "Bob Jones",
  "description": "Users cannot log in after the 2.1 release.",
  "created": "2024-01-01T10:00:00.000+0000",
  "updated": "2024-01-02T15:30:00.000+0000",
  "url": "https://acme.atlassian.net/browse/OPS-42"
}
```

---

### `PUT /jira/issue/<issue_key>` – Update issue

**Body** (all fields optional)

| Field | Type | Description |
|---|---|---|
| `summary` | string | New title |
| `description` | string | New description |
| `priority` | string | New priority |
| `assignee` | string | New assignee `accountId` |
| `labels` | string[] | Replacement labels |

**Response** `200` – updated issue object (same schema as GET)

---

### `POST /jira/issue/<issue_key>/comment` – Add comment

**Body**

| Field | Type | Required | Description |
|---|---|---|---|
| `body` | string | ✅ | Comment text |

**Response** `201`

```json
{"id": "100", "author": "Alice Smith", "created": "2024-01-03T...", "body": "Restarted the server"}
```

---

### `POST /jira/issue/<issue_key>/transition` – Transition issue

**Body**

| Field | Type | Required | Description |
|---|---|---|---|
| `transition_name` | string | ✅ | e.g. `"In Progress"`, `"Done"` |

**Response** `200` – updated issue object  
**Response** `422` – `{"error": "Transition 'X' not found. Available: [...]"}`

---

### `GET /jira/issues/search` – Search issues

**Query parameters** (all optional)

| Param | Type | Description |
|---|---|---|
| `jql` | string | Raw JQL (takes precedence) |
| `keyword` | string | Free-text search |
| `assignee` | string | Assignee display name or accountId |
| `max_results` | int | Max results (1–50, default 10) |

**Response** `200`

```json
{
  "total": 2,
  "issues": [
    {"key": "OPS-1", "summary": "...", "status": "To Do", "priority": "Medium",
     "issue_type": "Bug", "assignee": "Alice", "url": "..."},
    ...
  ]
}
```

---

### `PUT /jira/issue/<issue_key>/assign` – Assign issue

**Body** (provide one)

| Field | Type | Description |
|---|---|---|
| `account_id` | string | Jira accountId (preferred) |
| `email` | string | User email – accountId will be looked up automatically |

**Response** `200` – updated issue object

---

## Moveworks Integration

### How Action Plugins work

```
Creator Studio flow
  └─ Trigger (utterance / slot)
  └─ Action  ← calls your Flask API
  └─ Response template
```

Each YAML file in `moveworks/plugins/` maps directly to one Flask endpoint.
Import them into Creator Studio, set `JIRA_INTEGRATION_BASE_URL`, and wire
them into your conversational flows.

### Recommended Creator Studio flow design

| Step | Configuration |
|---|---|
| **Trigger** | Define a few example utterances per use case |
| **Slots** | Map NLU entities (e.g. `issue_key`, `project_key`) to plugin inputs |
| **Confirmation** | Add a confirmation step before destructive changes (e.g. transition, assign) |
| **Error handling** | Branch on `error` field in the response to show friendly messages |

### Authentication between Moveworks and your API

Add an `Authorization` header in each plugin definition.  Supported patterns:

- ******** – generate a static API key and validate it in a Flask
  `before_request` hook.
- **mTLS** – configure client certificates at the load-balancer layer.
- **IP allowlist** – restrict inbound traffic to Moveworks' IP ranges (see
  Moveworks documentation for the current list).

---

## Project Structure

```
Moveworks_Jira/
├── app.py                        # Flask API server
├── jira_client.py                # Jira REST API v3 wrapper
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variable template
├── .gitignore
├── moveworks/
│   └── plugins/
│       ├── create_issue.yaml     # Create Jira issue
│       ├── get_issue.yaml        # Get issue details
│       ├── update_issue.yaml     # Update issue fields
│       ├── search_issues.yaml    # Search / filter issues
│       ├── add_comment.yaml      # Add comment
│       ├── transition_issue.yaml # Change workflow status
│       └── assign_issue.yaml     # Assign to a user
└── tests/
    ├── test_jira_client.py       # Unit tests for JiraClient
    └── test_api.py               # Integration tests for Flask routes
```

---

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

Tests use `responses` (for HTTP mocking in JiraClient tests) and
`unittest.mock` (for Flask route tests).  No real Jira credentials are needed.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `401 Unauthorized` from Jira | Wrong email or API token | Re-check `.env`; ensure the API token belongs to the account in `JIRA_EMAIL` |
| `404` on issue key | Issue does not exist or you lack access | Verify the key and that the Jira user has Browse Projects permission |
| `400 Bad Request` creating issue | `issue_type` doesn't exist in the project | Check available issue types in Jira project settings |
| Transition returns 422 | Transition name misspelled or not available in current status | Call `GET /jira/issue/<key>` first; the error body lists available transitions |
| Moveworks plugin not triggering | Utterances don't match | Add more example utterances in Creator Studio and re-train |
| Connection refused from Moveworks | Flask not publicly reachable | Deploy behind HTTPS reverse proxy or use ngrok during development |
