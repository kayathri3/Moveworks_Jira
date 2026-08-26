# API Call Guide — Projector PSA

Reference for making API calls against **Projector PSA** (Cprime instance).
Covers OAuth flow, REST endpoints, and SOAP endpoints actually used in this project.

---

## 1. Prerequisites

| Item | Value |
|------|-------|
| **App base URL** | `https://app3.projectorpsa.com` |
| **SOAP base URL** | `https://secure3.projectorpsa.com` |
| **OAuth Client ID** | `<YOUR_CLIENT_ID>` (see `.env`) |
| **OAuth Client Secret** | `<YOUR_CLIENT_SECRET>` (see `.env`) |
| **Redirect URI** | `http://localhost:8080/callback` (must be registered in Projector Admin) |
| **Scope** | `allowFullPermissions` |
| **HTTP Client** | `curl` (used in scripts), `requests` (Python alternative) |

---

## 2. Anatomy of an API Request

### REST (JSON)
```
GET  https://app3.projectorpsa.com/api/v1/resources
Headers:
  Authorization: Bearer <ACCESS_TOKEN>
  Accept: application/json
```

### SOAP
```
POST  https://secure3.projectorpsa.com/OpsProjectorWcfSvc/PwsProjectorServices.svc
Headers:
  Content-Type: text/xml; charset=utf-8
  SOAPAction: "http://projectorpsa.com/PwsProjectorServices/IPwsProjectorServices/<MethodName>"
Body: <SOAP envelope XML>
```

### HTTP Methods used in this project

| Method | Used for |
|--------|---------|
| `GET` | All REST data pulls (`/api/v1/*`) |
| `POST` | OAuth token exchange + all SOAP calls |

---

## 3. Authentication — Projector OAuth 2.0 (Authorization Code Flow)

### Step 1 — Open browser for user login
```
https://app.projectorpsa.com/oauth2authorize/Cprime
  ?response_type=code
  &client_id=<YOUR_CLIENT_ID>
  &redirect_uri=http://localhost:8080/callback
  &scope=allowFullPermissions
```

### Step 2 — Exchange authorization code for token
```http
POST https://app.projectorpsa.com/oauth2token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=<AUTH_CODE>
&redirect_uri=http://localhost:8080/callback
&client_id=<YOUR_CLIENT_ID>
&client_secret=<YOUR_CLIENT_SECRET>
```

Response saved to `token.json`:
```json
{
  "access_token": "<ACCESS_TOKEN>",
  "token_type": "Bearer",
  "expires_in": 3600,
  "rest_service_authority": "https://app3.projectorpsa.com",
  "soap_service_authority": "https://secure3.projectorpsa.com"
}
```

> The `rest_service_authority` and `soap_service_authority` fields in the token response give you the correct base URLs to use for all subsequent calls. Always prefer these over hardcoded fallbacks.

---

## 4. REST API Endpoints

Base URL (from `rest_service_authority` in `token.json`): `https://app3.projectorpsa.com`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/projects` | `GET` | List all projects |
| `/api/v1/resources` | `GET` | List all resources (people) |
| `/api/v1/timesheets` | `GET` | List timesheets |
| `/api/v1/invoices` | `GET` | List invoices |
| `/api/v1/expenses` | `GET` | List expenses |

All REST calls use the same header:
```http
Authorization: Bearer <ACCESS_TOKEN>
Accept: application/json
```

### Internal AJAX endpoint (session-based, no token)
```
POST https://app3.projectorpsa.com/profile/home/AjxGetProfileLandingData
```
Used by `projector_profile_pull.py`. Requires a browser session cookie instead of Bearer token.

---

## 5. SOAP API Endpoints

Base URL (from `soap_service_authority` in `token.json`): `https://secure3.projectorpsa.com`

| Resource | URL |
|----------|-----|
| **SOAP Service** | `https://secure3.projectorpsa.com/OpsProjectorWcfSvc/PwsProjectorServices.svc` |
| **WSDL** | `https://secure3.projectorpsa.com/OpsProjectorWcfSvc/PwsProjectorServices.svc?wsdl` |
| **XSD Schema** | `https://secure3.projectorpsa.com/OpsProjectorWcfSvc/PwsProjectorServices.svc?xsd=xsd3` |

**SOAPAction header format:**
```
SOAPAction: "http://projectorpsa.com/PwsProjectorServices/IPwsProjectorServices/<MethodName>"
```

### Available SOAP Methods (read-only `PwsGet*`)

| Method | SOAPAction |
|--------|-----------|
| `PwsGetResource` | `...IPwsProjectorServices/PwsGetResource` |
| `PwsGetResourceList` | `...IPwsProjectorServices/PwsGetResourceList` |
| `PwsGetSkillList` | `...IPwsProjectorServices/PwsGetSkillList` |
| `PwsGetSkillGroupList` | `...IPwsProjectorServices/PwsGetSkillGroupList` |
| `PwsGetUserList` | `...IPwsProjectorServices/PwsGetUserList` |
| `PwsGetTitleList` | `...IPwsProjectorServices/PwsGetTitleList` |
| `PwsGetDepartmentList` | `...IPwsProjectorServices/PwsGetDepartmentList` |
| `PwsGetCostCenterList` | `...IPwsProjectorServices/PwsGetCostCenterList` |
| `PwsGetLocations` | `...IPwsProjectorServices/PwsGetLocations` |
| `PwsGetProjectList` | `...IPwsProjectorServices/PwsGetProjectList` |
| `PwsGetClientList` | `...IPwsProjectorServices/PwsGetClientList` |
| `PwsGetResourceSchedule` | `...IPwsProjectorServices/PwsGetResourceSchedule` |
| `PwsGetOnBehalfOfResources` | `...IPwsProjectorServices/PwsGetOnBehalfOfResources` |

## 6. Code Examples

### REST — Python (`requests`)

```python
import requests, json

with open("token.json") as f:
    tok = json.load(f)

BASE = tok["rest_service_authority"].rstrip("/")  # https://app3.projectorpsa.com
TOKEN = tok["access_token"]

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json",
}

# GET resources
response = requests.get(f"{BASE}/api/v1/resources", headers=headers)
response.raise_for_status()
resources = response.json()

# GET projects
response = requests.get(f"{BASE}/api/v1/projects", headers=headers)
response.raise_for_status()
projects = response.json()
```

### REST — cURL

```bash
# Replace <ACCESS_TOKEN> with the value from token.json

# Get resources
curl -X GET "https://app3.projectorpsa.com/api/v1/resources" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Accept: application/json"

# Get projects
curl -X GET "https://app3.projectorpsa.com/api/v1/projects" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Accept: application/json"

# Get timesheets
curl -X GET "https://app3.projectorpsa.com/api/v1/timesheets" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Accept: application/json"
```

### SOAP — Python (`requests`)

```python
import requests, json

with open("token.json") as f:
    tok = json.load(f)

SOAP_URL = tok["soap_service_authority"].rstrip("/") + "/OpsProjectorWcfSvc/PwsProjectorServices.svc"
TOKEN = tok["access_token"]
NS = "http://projectorpsa.com/PwsProjectorServices/"
ACTION_BASE = "http://projectorpsa.com/PwsProjectorServices/IPwsProjectorServices/"

envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:pws="{NS}">
  <soapenv:Header/>
  <soapenv:Body>
    <pws:PwsGetSkillList>
      <pws:request>
        <pws:Ticket>{TOKEN}</pws:Ticket>
      </pws:request>
    </pws:PwsGetSkillList>
  </soapenv:Body>
</soapenv:Envelope>"""

response = requests.post(
    SOAP_URL,
    data=envelope.encode("utf-8"),
    headers={
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{ACTION_BASE}PwsGetSkillList"',
    },
)
response.raise_for_status()
print(response.text)
```

### SOAP — cURL

```bash
curl -X POST "https://secure3.projectorpsa.com/OpsProjectorWcfSvc/PwsProjectorServices.svc" \
  -H 'Content-Type: text/xml; charset=utf-8' \
  -H 'SOAPAction: "http://projectorpsa.com/PwsProjectorServices/IPwsProjectorServices/PwsGetSkillList"' \
  -d @request.xml
```

Where `request.xml` contains the SOAP envelope with your `<Ticket><ACCESS_TOKEN></Ticket>`.

---

## 6. HTTP Response Codes

| Code | Meaning |
|------|---------|
| `200 OK` | Success (GET, PUT, PATCH) |
| `201 Created` | Resource created (POST) |
| `204 No Content` | Success, no body (DELETE) |
| `400 Bad Request` | Invalid input / malformed request |
| `401 Unauthorized` | Missing or invalid credentials |
| `403 Forbidden` | Authenticated but not authorized |
| `404 Not Found` | Resource does not exist |
| `422 Unprocessable Entity` | Validation error |
| `429 Too Many Requests` | Rate limit exceeded |
| `500 Internal Server Error` | Server-side failure |

---

## 7. Pagination

APIs typically paginate large result sets. Common patterns:

**Offset / Page-based:**
```
GET /users?page=2&per_page=50
```

**Cursor-based:**
```
GET /users?cursor=eyJpZCI6MTAwfQ==&limit=50
```

Response usually includes:
```json
{
  "data": [...],
  "meta": {
    "total": 500,
    "page": 2,
    "per_page": 50,
    "next_cursor": "eyJpZCI6MTUwfQ=="
  }
}
```

---

## 8. Error Handling Best Practices

```python
import requests
from requests.exceptions import HTTPError, Timeout, ConnectionError

try:
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()

except HTTPError as e:
    print(f"HTTP error {response.status_code}: {response.text}")
except Timeout:
    print("Request timed out")
except ConnectionError:
    print("Network connection failed")
```

---

## 9. Storing Credentials Safely

- **Never hardcode** tokens or secrets in source code.
- Use environment variables:
  ```python
  import os
  TOKEN = os.environ["API_TOKEN"]
  ```
- Use a `.env` file with `python-dotenv`:
  ```
  API_TOKEN=your_token_here
  BASE_URL=https://api.example.com/v1
  ```
  ```python
  from dotenv import load_dotenv
  load_dotenv()
  TOKEN = os.getenv("API_TOKEN")
  ```
- Add `.env` to `.gitignore`.

---

## 10. Rate Limiting

Check response headers for rate limit info:

| Header | Meaning |
|--------|---------|
| `X-RateLimit-Limit` | Max requests allowed in window |
| `X-RateLimit-Remaining` | Requests left in current window |
| `X-RateLimit-Reset` | Unix timestamp when limit resets |
| `Retry-After` | Seconds to wait (on 429) |

```python
import time

if response.status_code == 429:
    retry_after = int(response.headers.get("Retry-After", 60))
    time.sleep(retry_after)
    # retry request
```

---

## 11. Quick Checklist Before First Call

- [ ] Run `projector_oauth_curl.py` to generate `token.json`
- [ ] `token.json` contains `access_token`, `rest_service_authority`, and `soap_service_authority`
- [ ] `CLIENT_ID` and `CLIENT_SECRET` stored in `.env` (not hardcoded)
- [ ] `.env` is listed in `.gitignore`
- [ ] Redirect URI `http://localhost:8080/callback` registered in Projector Admin
- [ ] Using `rest_service_authority` (not hardcoded fallback) for REST calls
- [ ] Using `soap_service_authority` (not hardcoded fallback) for SOAP calls
- [ ] SOAP envelope includes `<Ticket>` element with the access token
- [ ] `SOAPAction` header exactly matches `http://projectorpsa.com/PwsProjectorServices/IPwsProjectorServices/<Method>`
- [ ] Token expiry handled — re-run OAuth flow when `401` is returned
