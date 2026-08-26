# API Call Guide

A general reference for making API calls — covers prerequisites, request structure, authentication, and common patterns.

---

## 1. Prerequisites

| Item | Description |
|------|-------------|
| **Base URL** | The root endpoint of the API (e.g., `https://api.example.com/v1`) |
| **API Key / Credentials** | Token, client ID/secret, or username/password |
| **HTTP Client** | `requests` (Python), `axios` (JS), `curl` (CLI), Postman |
| **Content Type** | Usually `application/json` or `application/x-www-form-urlencoded` |
| **API Docs** | Always check the official documentation for endpoint specs |

---

## 2. Anatomy of an API Request

```
METHOD  https://api.example.com/v1/resource?param=value
Headers:
  Authorization: Bearer <token>
  Content-Type: application/json
  Accept: application/json
Body (for POST/PUT/PATCH):
  { "key": "value" }
```

### HTTP Methods

| Method | Purpose |
|--------|---------|
| `GET` | Read / fetch data |
| `POST` | Create a new resource |
| `PUT` | Replace an existing resource |
| `PATCH` | Partially update a resource |
| `DELETE` | Remove a resource |

---

## 3. Authentication Types

### 3.1 API Key
Pass in a header or query string:
```http
GET /resource
X-API-Key: your_api_key_here
```
or
```
GET /resource?api_key=your_api_key_here
```

### 3.2 Bearer Token (OAuth 2.0)
```http
GET /resource
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
```

**Getting a token (Client Credentials flow):**
```http
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id=YOUR_CLIENT_ID
&client_secret=YOUR_CLIENT_SECRET
&scope=read write
```

Response:
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### 3.3 Basic Auth
```http
GET /resource
Authorization: Basic base64(username:password)
```

### 3.4 Session / Cookie
Login once to receive a session cookie; subsequent requests send it automatically.

---

## 4. Common Request Headers

| Header | Example Value | Purpose |
|--------|--------------|---------|
| `Authorization` | `Bearer <token>` | Authentication |
| `Content-Type` | `application/json` | Format of the request body |
| `Accept` | `application/json` | Expected response format |
| `X-Request-ID` | `uuid-1234` | Tracing / correlation |
| `User-Agent` | `MyApp/1.0` | Client identification |

---

## 5. Code Examples

### Python (`requests`)

```python
import requests

BASE_URL = "https://api.example.com/v1"
TOKEN = "your_token_here"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# GET
response = requests.get(f"{BASE_URL}/users", headers=headers, params={"page": 1})
response.raise_for_status()
data = response.json()

# POST
payload = {"name": "John", "email": "john@example.com"}
response = requests.post(f"{BASE_URL}/users", headers=headers, json=payload)
response.raise_for_status()
new_user = response.json()
```

### JavaScript (`fetch`)

```javascript
const BASE_URL = "https://api.example.com/v1";
const TOKEN = "your_token_here";

// GET
const res = await fetch(`${BASE_URL}/users?page=1`, {
  method: "GET",
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    Accept: "application/json",
  },
});
const data = await res.json();

// POST
const res2 = await fetch(`${BASE_URL}/users`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ name: "John", email: "john@example.com" }),
});
const newUser = await res2.json();
```

### cURL

```bash
# GET
curl -X GET "https://api.example.com/v1/users?page=1" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Accept: application/json"

# POST
curl -X POST "https://api.example.com/v1/users" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "John", "email": "john@example.com"}'
```

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

- [ ] Have the correct base URL and endpoint path
- [ ] Credentials obtained and stored securely (env var / vault)
- [ ] Know the required headers (`Content-Type`, `Authorization`)
- [ ] Understand the expected request body format (JSON, form data, XML)
- [ ] Know which HTTP method to use
- [ ] Handle response codes (especially 401, 429, 500)
- [ ] Add timeout to every request
- [ ] Review rate limits in the API docs
