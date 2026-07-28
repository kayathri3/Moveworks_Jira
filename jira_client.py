"""
Jira REST API v3 client.

Wraps the Jira Cloud REST API to provide simple Python methods for
the common issue-management operations used by the Moveworks integration.

Jira API docs: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
"""

from __future__ import annotations

import requests
from requests.auth import HTTPBasicAuth
from typing import Any, Dict, List, Optional


class JiraClient:
    """Thin wrapper around the Jira Cloud REST API v3."""

    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._auth = HTTPBasicAuth(email, api_token)
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        return f"{self.base_url}/rest/api/3/{path.lstrip('/')}"

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        resp = requests.get(
            self._url(path),
            auth=self._auth,
            headers=self._headers,
            params=params,
            timeout=15,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: Dict[str, Any]) -> Optional[Any]:
        resp = requests.post(
            self._url(path),
            auth=self._auth,
            headers=self._headers,
            json=payload,
            timeout=15,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, payload: Dict[str, Any]) -> Optional[Any]:
        resp = requests.put(
            self._url(path),
            auth=self._auth,
            headers=self._headers,
            json=payload,
            timeout=15,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        # Jira returns 204 (no body) for successful field updates
        return {} if resp.status_code == 204 else resp.json()

    @staticmethod
    def _adf_text(text: str) -> Dict[str, Any]:
        """Build a minimal Atlassian Document Format (ADF) paragraph node."""
        return {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": text}],
                }
            ],
        }

    @staticmethod
    def _extract_description(description: Any) -> str:
        """Extract plain text from an ADF description field (or plain string)."""
        if description is None:
            return ""
        if isinstance(description, str):
            return description
        texts: List[str] = []
        for block in description.get("content", []):
            for item in block.get("content", []):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
        return " ".join(texts)

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def create_issue(
        self,
        project_key: str,
        summary: str,
        issue_type: str,
        description: str = "",
        priority: str = "Medium",
        assignee: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new Jira issue and return its key, id, and URL."""
        fields: Dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
            "description": self._adf_text(description or summary),
        }
        if assignee:
            fields["assignee"] = {"accountId": assignee}
        if labels:
            fields["labels"] = labels

        result = self._post("issue", {"fields": fields})
        return {
            "key": result["key"],
            "id": result["id"],
            "url": f"{self.base_url}/browse/{result['key']}",
        }

    def get_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """Return a normalised dict for a Jira issue, or None if not found."""
        result = self._get(f"issue/{issue_key}")
        if result is None:
            return None
        f = result.get("fields", {})
        return {
            "key": result["key"],
            "id": result["id"],
            "summary": f.get("summary", ""),
            "status": (f.get("status") or {}).get("name", ""),
            "priority": (f.get("priority") or {}).get("name", ""),
            "issue_type": (f.get("issuetype") or {}).get("name", ""),
            "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
            "reporter": (f.get("reporter") or {}).get("displayName", ""),
            "created": f.get("created", ""),
            "updated": f.get("updated", ""),
            "description": self._extract_description(f.get("description")),
            "url": f"{self.base_url}/browse/{result['key']}",
        }

    def update_issue(
        self, issue_key: str, fields: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update one or more fields on an existing issue."""
        payload: Dict[str, Any] = {}
        if "summary" in fields:
            payload["summary"] = fields["summary"]
        if "priority" in fields:
            payload["priority"] = {"name": fields["priority"]}
        if "assignee" in fields:
            payload["assignee"] = {"accountId": fields["assignee"]}
        if "labels" in fields:
            payload["labels"] = fields["labels"]
        if "description" in fields:
            payload["description"] = self._adf_text(fields["description"])

        result = self._put(f"issue/{issue_key}", {"fields": payload})
        if result is None:
            return None
        return self.get_issue(issue_key)

    def add_comment(self, issue_key: str, body: str) -> Optional[Dict[str, Any]]:
        """Add a comment to a Jira issue."""
        result = self._post(
            f"issue/{issue_key}/comment",
            {"body": self._adf_text(body)},
        )
        if result is None:
            return None
        return {
            "id": result["id"],
            "author": (result.get("author") or {}).get("displayName", ""),
            "created": result.get("created", ""),
            "body": body,
        }

    def search_issues(
        self, jql: str, max_results: int = 10
    ) -> Dict[str, Any]:
        """Search issues with a JQL query and return a list of normalised dicts."""
        result = self._get(
            "search",
            params={
                "jql": jql,
                "maxResults": max_results,
                "fields": "summary,status,priority,issuetype,assignee,created,updated",
            },
        )
        if result is None:
            return {"issues": [], "total": 0}
        issues = [
            {
                "key": issue["key"],
                "summary": (issue.get("fields") or {}).get("summary", ""),
                "status": ((issue.get("fields") or {}).get("status") or {}).get("name", ""),
                "priority": ((issue.get("fields") or {}).get("priority") or {}).get("name", ""),
                "issue_type": ((issue.get("fields") or {}).get("issuetype") or {}).get("name", ""),
                "assignee": (
                    (issue.get("fields") or {}).get("assignee") or {}
                ).get("displayName", "Unassigned"),
                "url": f"{self.base_url}/browse/{issue['key']}",
            }
            for issue in result.get("issues", [])
        ]
        return {"issues": issues, "total": result.get("total", 0)}

    def transition_issue(
        self, issue_key: str, transition_name: str
    ) -> Optional[Dict[str, Any]]:
        """Move an issue to a new status by transition name.

        Returns the updated issue dict, or a dict with an 'error' key listing
        available transitions when the requested name is not found.
        Returns None when the issue itself does not exist.
        """
        transitions_resp = self._get(f"issue/{issue_key}/transitions")
        if transitions_resp is None:
            return None
        transitions = transitions_resp.get("transitions", [])
        match = next(
            (t for t in transitions if t["name"].lower() == transition_name.lower()),
            None,
        )
        if not match:
            return {
                "error": (
                    f"Transition '{transition_name}' not found. "
                    f"Available: {[t['name'] for t in transitions]}"
                )
            }
        resp = requests.post(
            self._url(f"issue/{issue_key}/transitions"),
            auth=self._auth,
            headers=self._headers,
            json={"transition": {"id": match["id"]}},
            timeout=15,
        )
        resp.raise_for_status()
        return self.get_issue(issue_key)

    def assign_issue(
        self,
        issue_key: str,
        account_id: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Assign an issue to a user (by accountId or email lookup)."""
        if not account_id and email:
            users = self._get("user/search", params={"query": email})
            if not users:
                return None
            account_id = users[0]["accountId"]

        resp = requests.put(
            self._url(f"issue/{issue_key}/assignee"),
            auth=self._auth,
            headers=self._headers,
            json={"accountId": account_id},
            timeout=15,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return self.get_issue(issue_key)
