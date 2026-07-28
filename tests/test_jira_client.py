"""
Tests for JiraClient.

All HTTP calls are intercepted by the `responses` library so no real
Jira instance is required.
"""

from __future__ import annotations

import json
import pytest
import responses as resp_mock

from jira_client import JiraClient

BASE = "https://test.atlassian.net"
CLIENT = JiraClient(base_url=BASE, email="test@example.com", api_token="token123")


def _url(path: str) -> str:
    return f"{BASE}/rest/api/3/{path.lstrip('/')}"


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

ISSUE_PAYLOAD = {
    "key": "OPS-42",
    "id": "10042",
    "fields": {
        "summary": "Test issue",
        "status": {"name": "To Do"},
        "priority": {"name": "Medium"},
        "issuetype": {"name": "Task"},
        "assignee": {"displayName": "Alice"},
        "reporter": {"displayName": "Bob"},
        "created": "2024-01-01T00:00:00.000+0000",
        "updated": "2024-01-02T00:00:00.000+0000",
        "description": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Test description"}],
                }
            ],
        },
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# create_issue
# ──────────────────────────────────────────────────────────────────────────────


@resp_mock.activate
def test_create_issue_returns_key_and_url():
    resp_mock.add(
        resp_mock.POST,
        _url("issue"),
        json={"key": "OPS-42", "id": "10042"},
        status=201,
    )
    result = CLIENT.create_issue(
        project_key="OPS",
        summary="Test issue",
        issue_type="Task",
    )
    assert result["key"] == "OPS-42"
    assert result["url"] == f"{BASE}/browse/OPS-42"


@resp_mock.activate
def test_create_issue_with_optional_fields():
    resp_mock.add(
        resp_mock.POST,
        _url("issue"),
        json={"key": "OPS-43", "id": "10043"},
        status=201,
    )
    result = CLIENT.create_issue(
        project_key="OPS",
        summary="Bug report",
        issue_type="Bug",
        description="Something is broken",
        priority="High",
        assignee="account-abc",
        labels=["backend", "urgent"],
    )
    assert result["key"] == "OPS-43"
    # Verify the request body included the optional fields
    sent = json.loads(resp_mock.calls[0].request.body)
    assert sent["fields"]["priority"]["name"] == "High"
    assert sent["fields"]["assignee"]["accountId"] == "account-abc"
    assert "backend" in sent["fields"]["labels"]


# ──────────────────────────────────────────────────────────────────────────────
# get_issue
# ──────────────────────────────────────────────────────────────────────────────


@resp_mock.activate
def test_get_issue_returns_normalised_dict():
    resp_mock.add(resp_mock.GET, _url("issue/OPS-42"), json=ISSUE_PAYLOAD, status=200)
    result = CLIENT.get_issue("OPS-42")
    assert result is not None
    assert result["key"] == "OPS-42"
    assert result["summary"] == "Test issue"
    assert result["status"] == "To Do"
    assert result["assignee"] == "Alice"
    assert result["description"] == "Test description"
    assert result["url"] == f"{BASE}/browse/OPS-42"


@resp_mock.activate
def test_get_issue_returns_none_for_404():
    resp_mock.add(resp_mock.GET, _url("issue/OPS-999"), status=404)
    assert CLIENT.get_issue("OPS-999") is None


@resp_mock.activate
def test_get_issue_unassigned():
    payload = dict(ISSUE_PAYLOAD)
    payload = json.loads(json.dumps(ISSUE_PAYLOAD))
    payload["fields"]["assignee"] = None
    resp_mock.add(resp_mock.GET, _url("issue/OPS-42"), json=payload, status=200)
    result = CLIENT.get_issue("OPS-42")
    assert result["assignee"] == "Unassigned"


# ──────────────────────────────────────────────────────────────────────────────
# update_issue
# ──────────────────────────────────────────────────────────────────────────────


@resp_mock.activate
def test_update_issue_returns_updated_issue():
    resp_mock.add(resp_mock.PUT, _url("issue/OPS-42"), status=204)
    updated_payload = json.loads(json.dumps(ISSUE_PAYLOAD))
    updated_payload["fields"]["priority"]["name"] = "High"
    resp_mock.add(resp_mock.GET, _url("issue/OPS-42"), json=updated_payload, status=200)

    result = CLIENT.update_issue("OPS-42", {"priority": "High"})
    assert result is not None
    assert result["priority"] == "High"


@resp_mock.activate
def test_update_issue_returns_none_for_404():
    resp_mock.add(resp_mock.PUT, _url("issue/OPS-999"), status=404)
    assert CLIENT.update_issue("OPS-999", {"priority": "Low"}) is None


# ──────────────────────────────────────────────────────────────────────────────
# add_comment
# ──────────────────────────────────────────────────────────────────────────────


@resp_mock.activate
def test_add_comment_returns_comment_dict():
    resp_mock.add(
        resp_mock.POST,
        _url("issue/OPS-42/comment"),
        json={
            "id": "100",
            "author": {"displayName": "Alice"},
            "created": "2024-01-03T00:00:00.000+0000",
        },
        status=201,
    )
    result = CLIENT.add_comment("OPS-42", "Server restarted")
    assert result["id"] == "100"
    assert result["author"] == "Alice"
    assert result["body"] == "Server restarted"


@resp_mock.activate
def test_add_comment_returns_none_for_404():
    resp_mock.add(resp_mock.POST, _url("issue/OPS-999/comment"), status=404)
    assert CLIENT.add_comment("OPS-999", "hello") is None


# ──────────────────────────────────────────────────────────────────────────────
# search_issues
# ──────────────────────────────────────────────────────────────────────────────


@resp_mock.activate
def test_search_issues_returns_list():
    resp_mock.add(
        resp_mock.GET,
        _url("search"),
        json={
            "total": 2,
            "issues": [
                {
                    "key": "OPS-1",
                    "fields": {
                        "summary": "Issue one",
                        "status": {"name": "In Progress"},
                        "priority": {"name": "High"},
                        "issuetype": {"name": "Bug"},
                        "assignee": {"displayName": "Alice"},
                    },
                },
                {
                    "key": "OPS-2",
                    "fields": {
                        "summary": "Issue two",
                        "status": {"name": "To Do"},
                        "priority": None,
                        "issuetype": {"name": "Task"},
                        "assignee": None,
                    },
                },
            ],
        },
        status=200,
    )
    result = CLIENT.search_issues('project = "OPS"')
    assert result["total"] == 2
    assert len(result["issues"]) == 2
    assert result["issues"][0]["key"] == "OPS-1"
    assert result["issues"][1]["assignee"] == "Unassigned"


@resp_mock.activate
def test_search_issues_returns_empty_on_404():
    resp_mock.add(resp_mock.GET, _url("search"), status=404)
    result = CLIENT.search_issues("project = MISSING")
    assert result == {"issues": [], "total": 0}


# ──────────────────────────────────────────────────────────────────────────────
# transition_issue
# ──────────────────────────────────────────────────────────────────────────────


@resp_mock.activate
def test_transition_issue_succeeds():
    resp_mock.add(
        resp_mock.GET,
        _url("issue/OPS-42/transitions"),
        json={"transitions": [{"id": "21", "name": "In Progress"}]},
        status=200,
    )
    resp_mock.add(resp_mock.POST, _url("issue/OPS-42/transitions"), status=204)
    in_progress = json.loads(json.dumps(ISSUE_PAYLOAD))
    in_progress["fields"]["status"]["name"] = "In Progress"
    resp_mock.add(resp_mock.GET, _url("issue/OPS-42"), json=in_progress, status=200)

    result = CLIENT.transition_issue("OPS-42", "In Progress")
    assert result is not None
    assert result["status"] == "In Progress"


@resp_mock.activate
def test_transition_issue_unknown_name_returns_error():
    resp_mock.add(
        resp_mock.GET,
        _url("issue/OPS-42/transitions"),
        json={"transitions": [{"id": "21", "name": "In Progress"}]},
        status=200,
    )
    result = CLIENT.transition_issue("OPS-42", "NonExistent")
    assert "error" in result
    assert "NonExistent" in result["error"]


@resp_mock.activate
def test_transition_issue_returns_none_for_404():
    resp_mock.add(resp_mock.GET, _url("issue/OPS-999/transitions"), status=404)
    assert CLIENT.transition_issue("OPS-999", "Done") is None


# ──────────────────────────────────────────────────────────────────────────────
# _extract_description
# ──────────────────────────────────────────────────────────────────────────────


def test_extract_description_plain_string():
    assert JiraClient._extract_description("plain text") == "plain text"


def test_extract_description_none():
    assert JiraClient._extract_description(None) == ""


def test_extract_description_adf():
    adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Hello "},
                    {"type": "text", "text": "world"},
                ],
            }
        ],
    }
    assert JiraClient._extract_description(adf) == "Hello  world"
