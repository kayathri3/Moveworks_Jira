"""
Moveworks–Jira Integration API Server

This Flask application is the bridge between the Moveworks bot and Jira.
Moveworks Action Plugins (defined in moveworks/plugins/) call these
endpoints to perform Jira operations on behalf of employees.

Quick-start
-----------
1. Copy .env.example to .env and fill in your credentials.
2. pip install -r requirements.txt
3. python app.py
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from jira_client import JiraClient

load_dotenv()

app = Flask(__name__)

_jira = JiraClient(
    base_url=os.environ["JIRA_BASE_URL"],
    email=os.environ["JIRA_EMAIL"],
    api_token=os.environ["JIRA_API_TOKEN"],
)


# ──────────────────────────────────────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────────────────────────────────────


@app.route("/health", methods=["GET"])
def health():
    """Liveness probe used by deployment platforms and Moveworks."""
    return jsonify({"status": "ok"})


# ──────────────────────────────────────────────────────────────────────────────
# Issue CRUD
# ──────────────────────────────────────────────────────────────────────────────


@app.route("/jira/issue", methods=["POST"])
def create_issue():
    """Create a new Jira issue.

    Request body (JSON)
    -------------------
    project_key  : str  – required, e.g. "OPS"
    summary      : str  – required
    issue_type   : str  – required, e.g. "Bug", "Task", "Story"
    description  : str  – optional
    priority     : str  – optional, default "Medium"
    assignee     : str  – optional, Jira accountId
    labels       : list – optional
    """
    data = request.get_json(force=True, silent=True) or {}
    for field in ("project_key", "summary", "issue_type"):
        if not data.get(field):
            return jsonify({"error": f"Missing required field: {field}"}), 400

    result = _jira.create_issue(
        project_key=data["project_key"],
        summary=data["summary"],
        issue_type=data["issue_type"],
        description=data.get("description", ""),
        priority=data.get("priority", "Medium"),
        assignee=data.get("assignee"),
        labels=data.get("labels", []),
    )
    return jsonify(result), 201


@app.route("/jira/issue/<issue_key>", methods=["GET"])
def get_issue(issue_key: str):
    """Retrieve details for a specific Jira issue (e.g. OPS-42)."""
    result = _jira.get_issue(issue_key)
    if result is None:
        return jsonify({"error": f"Issue {issue_key} not found"}), 404
    return jsonify(result)


@app.route("/jira/issue/<issue_key>", methods=["PUT"])
def update_issue(issue_key: str):
    """Update one or more fields on an existing Jira issue.

    Request body (JSON) – all fields optional:
    summary, description, priority, assignee (accountId), labels
    """
    data = request.get_json(force=True, silent=True) or {}
    result = _jira.update_issue(issue_key, data)
    if result is None:
        return jsonify({"error": f"Issue {issue_key} not found"}), 404
    return jsonify(result)


# ──────────────────────────────────────────────────────────────────────────────
# Comments
# ──────────────────────────────────────────────────────────────────────────────


@app.route("/jira/issue/<issue_key>/comment", methods=["POST"])
def add_comment(issue_key: str):
    """Add a comment to a Jira issue.

    Request body (JSON)
    -------------------
    body : str – required, the comment text
    """
    data = request.get_json(force=True, silent=True) or {}
    if not data.get("body"):
        return jsonify({"error": "Missing required field: body"}), 400

    result = _jira.add_comment(issue_key, data["body"])
    if result is None:
        return jsonify({"error": f"Issue {issue_key} not found"}), 404
    return jsonify(result), 201


# ──────────────────────────────────────────────────────────────────────────────
# Workflow transitions
# ──────────────────────────────────────────────────────────────────────────────


@app.route("/jira/issue/<issue_key>/transition", methods=["POST"])
def transition_issue(issue_key: str):
    """Transition a Jira issue to a new workflow status.

    Request body (JSON)
    -------------------
    transition_name : str – required, e.g. "In Progress", "Done", "Resolve Issue"
    """
    data = request.get_json(force=True, silent=True) or {}
    if not data.get("transition_name"):
        return jsonify({"error": "Missing required field: transition_name"}), 400

    result = _jira.transition_issue(issue_key, data["transition_name"])
    if result is None:
        return jsonify({"error": f"Issue {issue_key} not found"}), 404
    if "error" in result:
        return jsonify(result), 422
    return jsonify(result)


# ──────────────────────────────────────────────────────────────────────────────
# Search
# ──────────────────────────────────────────────────────────────────────────────


@app.route("/jira/issues/search", methods=["GET"])
def search_issues():
    """Search Jira issues.

    Query parameters (all optional, at least one recommended)
    ---------------------------------------------------------
    jql         : str  – raw JQL query (takes precedence when provided)
    keyword     : str  – free-text keyword search
    assignee    : str  – filter by assignee display name or accountId
    max_results : int  – maximum number of results (default 10)
    """
    jql = request.args.get("jql")
    keyword = request.args.get("keyword")
    assignee = request.args.get("assignee")
    max_results = min(int(request.args.get("max_results", 10)), 50)

    if not jql:
        parts: list[str] = []
        if keyword:
            parts.append(f'text ~ "{keyword}"')
        if assignee:
            parts.append(f'assignee = "{assignee}"')
        jql = " AND ".join(parts) if parts else "ORDER BY created DESC"

    result = _jira.search_issues(jql, max_results)
    return jsonify(result)


# ──────────────────────────────────────────────────────────────────────────────
# Assignment
# ──────────────────────────────────────────────────────────────────────────────


@app.route("/jira/issue/<issue_key>/assign", methods=["PUT"])
def assign_issue(issue_key: str):
    """Assign a Jira issue to a user.

    Request body (JSON) – supply one of:
    account_id : str – Jira accountId
    email      : str – user's email (accountId will be looked up automatically)
    """
    data = request.get_json(force=True, silent=True) or {}
    if not data.get("account_id") and not data.get("email"):
        return jsonify({"error": "Provide account_id or email"}), 400

    result = _jira.assign_issue(
        issue_key, data.get("account_id"), data.get("email")
    )
    if result is None:
        return jsonify({"error": f"Issue {issue_key} not found or assignee invalid"}), 404
    return jsonify(result)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
