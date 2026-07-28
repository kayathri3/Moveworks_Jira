"""
Tests for the Flask API (app.py).

All Jira HTTP calls are mocked via unittest.mock so no real credentials
or Jira instance are required.
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock, patch

# Set dummy env vars before importing the app so it doesn't crash on startup
os.environ.setdefault("JIRA_BASE_URL", "https://test.atlassian.net")
os.environ.setdefault("JIRA_EMAIL", "test@example.com")
os.environ.setdefault("JIRA_API_TOKEN", "token123")

import app as app_module  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    """Flask test client with a mocked JiraClient."""
    mock_jira = MagicMock()
    monkeypatch.setattr(app_module, "_jira", mock_jira)
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c, mock_jira


# ──────────────────────────────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────────────────────────────


def test_health(client):
    c, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


# ──────────────────────────────────────────────────────────────────────────────
# POST /jira/issue
# ──────────────────────────────────────────────────────────────────────────────


def test_create_issue_success(client):
    c, mock_jira = client
    mock_jira.create_issue.return_value = {
        "key": "OPS-42",
        "id": "10042",
        "url": "https://test.atlassian.net/browse/OPS-42",
    }
    resp = c.post(
        "/jira/issue",
        json={"project_key": "OPS", "summary": "Test", "issue_type": "Task"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["key"] == "OPS-42"
    mock_jira.create_issue.assert_called_once()


def test_create_issue_missing_field(client):
    c, _ = client
    resp = c.post("/jira/issue", json={"project_key": "OPS", "summary": "Test"})
    assert resp.status_code == 400
    assert "issue_type" in resp.get_json()["error"]


def test_create_issue_empty_body(client):
    c, _ = client
    resp = c.post("/jira/issue", json={})
    assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────────────────
# GET /jira/issue/<key>
# ──────────────────────────────────────────────────────────────────────────────


def test_get_issue_success(client):
    c, mock_jira = client
    mock_jira.get_issue.return_value = {
        "key": "OPS-42",
        "summary": "Test issue",
        "status": "To Do",
        "priority": "Medium",
        "issue_type": "Task",
        "assignee": "Alice",
        "reporter": "Bob",
        "description": "details",
        "created": "2024-01-01",
        "updated": "2024-01-02",
        "url": "https://test.atlassian.net/browse/OPS-42",
    }
    resp = c.get("/jira/issue/OPS-42")
    assert resp.status_code == 200
    assert resp.get_json()["key"] == "OPS-42"


def test_get_issue_not_found(client):
    c, mock_jira = client
    mock_jira.get_issue.return_value = None
    resp = c.get("/jira/issue/OPS-999")
    assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# PUT /jira/issue/<key>
# ──────────────────────────────────────────────────────────────────────────────


def test_update_issue_success(client):
    c, mock_jira = client
    updated = {"key": "OPS-42", "priority": "High", "status": "To Do",
               "summary": "Test", "issue_type": "Task", "assignee": "Alice",
               "reporter": "Bob", "description": "", "created": "", "updated": "",
               "url": "https://test.atlassian.net/browse/OPS-42"}
    mock_jira.update_issue.return_value = updated
    resp = c.put("/jira/issue/OPS-42", json={"priority": "High"})
    assert resp.status_code == 200
    assert resp.get_json()["priority"] == "High"


def test_update_issue_not_found(client):
    c, mock_jira = client
    mock_jira.update_issue.return_value = None
    resp = c.put("/jira/issue/OPS-999", json={"priority": "High"})
    assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# POST /jira/issue/<key>/comment
# ──────────────────────────────────────────────────────────────────────────────


def test_add_comment_success(client):
    c, mock_jira = client
    mock_jira.add_comment.return_value = {
        "id": "100",
        "author": "Alice",
        "created": "2024-01-03",
        "body": "Test comment",
    }
    resp = c.post("/jira/issue/OPS-42/comment", json={"body": "Test comment"})
    assert resp.status_code == 201
    assert resp.get_json()["id"] == "100"


def test_add_comment_missing_body(client):
    c, _ = client
    resp = c.post("/jira/issue/OPS-42/comment", json={})
    assert resp.status_code == 400


def test_add_comment_not_found(client):
    c, mock_jira = client
    mock_jira.add_comment.return_value = None
    resp = c.post("/jira/issue/OPS-999/comment", json={"body": "hi"})
    assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# POST /jira/issue/<key>/transition
# ──────────────────────────────────────────────────────────────────────────────


def test_transition_issue_success(client):
    c, mock_jira = client
    mock_jira.transition_issue.return_value = {
        "key": "OPS-42", "status": "In Progress",
        "priority": "Medium", "summary": "Test",
        "issue_type": "Task", "assignee": "Alice",
        "reporter": "Bob", "description": "", "created": "", "updated": "",
        "url": "https://test.atlassian.net/browse/OPS-42",
    }
    resp = c.post("/jira/issue/OPS-42/transition", json={"transition_name": "In Progress"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "In Progress"


def test_transition_issue_unknown(client):
    c, mock_jira = client
    mock_jira.transition_issue.return_value = {
        "error": "Transition 'Fly' not found. Available: ['To Do', 'Done']"
    }
    resp = c.post("/jira/issue/OPS-42/transition", json={"transition_name": "Fly"})
    assert resp.status_code == 422


def test_transition_issue_missing_field(client):
    c, _ = client
    resp = c.post("/jira/issue/OPS-42/transition", json={})
    assert resp.status_code == 400


def test_transition_issue_not_found(client):
    c, mock_jira = client
    mock_jira.transition_issue.return_value = None
    resp = c.post("/jira/issue/OPS-999/transition", json={"transition_name": "Done"})
    assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# GET /jira/issues/search
# ──────────────────────────────────────────────────────────────────────────────


def test_search_issues_with_keyword(client):
    c, mock_jira = client
    mock_jira.search_issues.return_value = {"total": 1, "issues": [
        {"key": "OPS-1", "summary": "Found it", "status": "To Do",
         "priority": "Medium", "issue_type": "Task", "assignee": "Alice",
         "url": "https://test.atlassian.net/browse/OPS-1"}
    ]}
    resp = c.get("/jira/issues/search?keyword=Found")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 1
    # Verify JQL was built from keyword
    call_args = mock_jira.search_issues.call_args[0]
    assert 'text ~ "Found"' in call_args[0]


def test_search_issues_with_raw_jql(client):
    c, mock_jira = client
    mock_jira.search_issues.return_value = {"total": 0, "issues": []}
    resp = c.get("/jira/issues/search?jql=project%3DOPS")
    assert resp.status_code == 200
    call_args = mock_jira.search_issues.call_args[0]
    assert call_args[0] == "project=OPS"


def test_search_issues_max_results_capped(client):
    c, mock_jira = client
    mock_jira.search_issues.return_value = {"total": 0, "issues": []}
    c.get("/jira/issues/search?max_results=999")
    call_args = mock_jira.search_issues.call_args[0]
    assert call_args[1] <= 50


# ──────────────────────────────────────────────────────────────────────────────
# PUT /jira/issue/<key>/assign
# ──────────────────────────────────────────────────────────────────────────────


def test_assign_issue_by_account_id(client):
    c, mock_jira = client
    mock_jira.assign_issue.return_value = {
        "key": "OPS-42", "assignee": "Alice", "status": "To Do",
        "priority": "Medium", "summary": "Test", "issue_type": "Task",
        "reporter": "Bob", "description": "", "created": "", "updated": "",
        "url": "https://test.atlassian.net/browse/OPS-42",
    }
    resp = c.put("/jira/issue/OPS-42/assign", json={"account_id": "abc123"})
    assert resp.status_code == 200
    assert resp.get_json()["assignee"] == "Alice"


def test_assign_issue_missing_both(client):
    c, _ = client
    resp = c.put("/jira/issue/OPS-42/assign", json={})
    assert resp.status_code == 400


def test_assign_issue_not_found(client):
    c, mock_jira = client
    mock_jira.assign_issue.return_value = None
    resp = c.put("/jira/issue/OPS-999/assign", json={"account_id": "abc"})
    assert resp.status_code == 404
