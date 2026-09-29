# Jira Allocation Request — Enhancement Chat History Summary

## 1. Use Case Overview

**Goal:** Enhance the existing Moveworks "Jira Allocation Request" bot/plugin so it can **auto-fetch project details** (Project Name, SFDC/Opportunity Code, Project Manager, Client Name, End Date, etc.) from **Projector PSA** instead of requiring the user to type them manually — reducing errors and speeding up new-allocation ticket creation.

**Current flow (before enhancement):**
```
Case: data.request_type == "Allocations"
  ↓
Bot asks user to manually type: project name, SFDC code, PM, client, dates, etc.
  ↓
Bot creates Jira ticket with the typed values
```

**Target flow (after enhancement):**
```
Case: data.request_type == "Allocations"
  ↓
HTTP Action → Projector PSA (auto-fetch project list for logged-in user)
  ↓
Bot pre-fills / auto-suggests project fields (name, SFDC code, PM, client, end date)
  ↓
User confirms/edits → Bot creates Jira ticket
```

**Reference artifact:** [Allocation_Request_Enhanced.html](Allocation_Request_Enhanced.html) — a presentation-style HTML slide (styled after `Reimbursement_Request_in_chat.html`) built to showcase this use case, including the "Picture This" scenario, flow diagram, and a "Live Demo" placeholder pending real screenshots.

---

## 2. Key Technical Components

| Component | Purpose |
|---|---|
| **Moveworks Agent Studio plugin** (`Jira_ticketing_plugin_upgrade`) | Owns the Allocations flow, slots, and Jira ticket creation logic |
| **Projector connector** (`Projector_Sandbox_2`, OAuth2) | Meant to auto-handle Projector login/token for HTTP Actions |
| **HTTP Action `Projector_Get_PM_Projects`** | Fetches active project details (name, SFDC code, end date, PM, client) from Projector for the logged-in user's allocation requests |
| **Projector Report** (`PM Projects Report`, type "Project List") | Custom Projector report exposing the fields needed (ProjectName, ProjectCode, ProjectManager, ClientName, end date) |
| **Report REST endpoint** | `GET https://app4.projectorpsa.com/report/code/pm_projects?format=json&SessionTicket={token}` |
| Local test/support scripts | [go.py](go.py), [exchange_code.py](exchange_code.py), [quick_token.py](quick_token.py), [test_projector_final.py](test_projector_final.py), [test_projector_oauth.py](test_projector_oauth.py), [token_relay_service.py](token_relay_service.py) |

### Data mapping discovered
| Jira Field | Projector Report Field |
|---|---|
| Project Name / Client | `ProjectName` + `ClientName` |
| SFDC / Opportunity Code | `ProjectCode` (confirmed by Satvika to be usable as the SFDC code) |
| Project Manager | `ProjectManager` |
| End Date | `ProjectEndDate` |

---

## 3. Timeline of Progress

### Phase 1 — Slide/showcase prep
- Built [Allocation_Request_Enhanced.html](Allocation_Request_Enhanced.html) matching the style of the existing Reimbursement-in-chat example.
- Reviewed and confirmed content accuracy; sent a short reply noting the "Live Demo" section needs real screenshots once the connector works.

### Phase 2 — Manual Postman testing of Projector API
- Learned to navigate the Projector sandbox **Report** screen (new to the user); created a report (`PM Projects Report`, "Project List" type).
- Identified that `2024-94968-001` is the **Project Code**, and confirmed with Satvika this doubles as the **SFDC Opportunity Code**.
- Walked through full OAuth2 authorization-code flow manually in a browser + Postman:
  1. Authorize URL → get `code`
  2. Exchange `code` for `access_token` at `/oauth2token`
  3. Call the report endpoint with `SessionTicket={access_token}`
- Successfully fetched real project JSON data via Postman — confirmed the report/API design works end-to-end outside Moveworks.

### Phase 3 — Building the Moveworks HTTP Action
- Learned Moveworks HTTP Actions reject query strings in the URL path ("Path must start with / and contain no query string") — parameters must go in the dedicated Query Params section instead.
- Named the action `Projector_Get_PM_Projects` with description: *"Fetches active project details (name, SFDC code, end date, PM, client) from Projector PSA for the logged-in user's allocation requests."*
- Clarified that no separate "get token" HTTP Action should be needed — the OAuth2 connector (`Projector_Sandbox_2`) is supposed to auto-inject `access_token` automatically (normally via the `Authorization` header).
- Reviewed the existing `Jira_ticketing_plugin_upgrade` flow to understand current slots/variables and where the Allocation branch lives, then designed the enhanced flow and new/updated slot descriptions (e.g., `priority` auto-set from allocation start date, `allocation_data` slot, etc.).
- Pushed all related changes to `main` (18 files).

### Phase 4 — Reporting progress to stakeholders
- Drafted a concise progress table for Ashwath/Piyush summarizing:
  - What's done: Projector connector configured, OAuth token exchange verified in Postman, report created and returning correct data.
  - Open item: Moveworks support ticket (CS9539089) tracking a connector callback issue blocking end-to-end testing (explicitly avoided asserting PKCE as the confirmed root cause until verified).
  - Future scope / target dates / resource owner.

### Phase 5 — Moveworks support back-and-forth (Barkha Bansal)
- Support confirmed the reported bug and asked technical questions, which were answered using data already gathered from testing.
- Support advised setting the connector's **Custom Grant Type = `code`** and using Projector's token URL — this fixed the callback: user saw **"Callback Request Successful"**, confirming Moveworks successfully exchanged the authorization code for an access token.
- However, the actual report API call inside Moveworks still failed with a generic Projector error page (`<body class="unauthenticated">`), even though the exact same call worked in Postman with a manually-pasted token.
- Root cause found: in the HTTP Action, `access_token` had been added as a plain **Input Argument** (a manually-typed string), **not** a system-level reference to the connector's live OAuth token — so it only worked when pasted in by hand, never automatically.
- Reported this back to Barkha, who confirmed a **hard platform limitation**: Moveworks' OAuth2 connector can only auto-inject the live access token into the `Authorization` **header** — not into a custom query parameter like `SessionTicket`. So `SessionTicket={{access_token}}` can never populate automatically as originally designed.

### Phase 6 — Workaround design (current/latest session)
Two possible paths were identified to work around the header-only injection limitation:

- **Path A — Switch to header-based auth:** If Projector's newer REST endpoints (e.g. `/api/v1/projects`) accept `Authorization: Bearer <token>` and return the same needed fields, reconfigure the HTTP Action to hit that endpoint instead — this lets Moveworks' default header auto-injection work with no extra plumbing.
- **Path B — Self-managed token refresh:** Add a dedicated HTTP Action that gets/refreshes the Projector token itself (independent of the OAuth2 connector) and feeds `access_token` into the existing `SessionTicket` query param as an output variable from that new step.

**Local verification (via [go.py](go.py)):**
- Ran the authorization-code exchange locally; confirmed Projector **does** return a `refresh_token` alongside the `access_token` (`token_type: projector_session_ticket`, `expires_in: 604800`, `scope: allowFullPermissions`).
- Discovered Projector's `refresh_token` is **single-use / rotating** — each refresh call invalidates the old refresh token and issues a new one. A static secret stored once in Moveworks would break after the first refresh.
- Tested the newer REST endpoints (`/api/v1/projects`, `/api/v1/resources`) — both currently return `302` redirects to an error page in this sandbox, so Path A (header-based REST) is **not yet confirmed usable**; the legacy report endpoint remains the only proven data source so far.
- Built [token_relay_service.py](token_relay_service.py) — a small Flask service that:
  - Caches the current `access_token`.
  - Only calls Projector's `/oauth2token` refresh endpoint when the cached token is near expiry.
  - Persists the newly-rotated `refresh_token` to [token_store.json](token_store.json) each time, solving the rotation/persistence problem.
  - Exposes a simple `GET /token` endpoint protected by an `X-Relay-Key` header, returning `{ "access_token": ..., "rest_service_authority": ... }`.
- Verified locally: auth check, caching, and refresh all work as expected.

**Moveworks-side configuration drafted for the relay approach:**
1. Store secrets in the plugin's Connectors/Properties section: `relay_api_key`, `relay_base_url` (never hardcode as literal text).
2. Add new HTTP Action **"Get Relay Access Token"** (No-Auth connector) that runs before the existing "Get PM Projects" action:
   - `GET {{relay_base_url}}/token`
   - Header: `X-Relay-Key: {{relay_api_key}}`
   - Returns `access_token` to be referenced by the next step.
3. Update the existing "Get PM Projects" HTTP Action to set `SessionTicket = {{get_relay_access_token.access_token}}`.

**Open question raised by user:** whether a simpler design — one new HTTP Action per run doing `grant_type=refresh_token` with a *statically stored* `refresh_token` secret, no relay — could work.
**Answer given:** No, not safely, because:
- Run 1 succeeds (Projector returns a new `access_token` **and** a new `refresh_token`, invalidating the old one).
- Run 2 would still send the old, now-dead `refresh_token` from the static secret → Projector returns `invalid_grant: Refresh Token not Found` (this exact failure was already reproduced during testing).
- Unless Moveworks can confirm it has a **writable Data Table** that a flow can update in-place (to persist the newest rotated `refresh_token` between runs), there's no way to avoid the relay service (or an equivalent persistence layer) — this is the whole reason the relay exists.

### Phase 7 — Moveworks support gives final, confirmed answer (2026-09-28)
- Barkha Bansal (Moveworks support, ticket CS9539089) replied: **"We investigated further and confirmed that we don't currently support injecting a live access token as a query parameter... this would be considered a feature enhancement."** She suggested raising it on the community ideas forum for others to vote on.
- This **officially closes** the investigation into native query-param token injection — it is a confirmed platform limitation, not a bug or misconfiguration.
- **Decision:** Proceed with **Path B (self-managed token relay)** as the concrete workaround, since Path A (`/api/v1/*` header-based REST endpoints) is still unconfirmed/returning 302 errors in the sandbox. The relay service ([token_relay_service.py](token_relay_service.py)) was already built and validated locally (including a `127.0.0.1:5000/token` header-auth check).
- Drafted closing reply to Barkha confirming the workaround plan and intent to file a community feature request.

---

## 4. Current Status / Blockers

| Item | Status |
|---|---|
| Projector OAuth "Custom Grant Type" fix | ✅ Confirmed working (Callback Request Successful) |
| Legacy report endpoint (`/report/code/pm_projects`) via Postman | ✅ Returns correct data with manual token |
| Moveworks HTTP Action auto-injecting token into `SessionTicket` query param | ❌ Confirmed unsupported by Moveworks support — official platform limitation, logged as a feature request |
| Path A (header-based `/api/v1/projects`) | ⚠️ Untested/unconfirmed — currently returns 302 redirect to error page in sandbox |
| Path B (self-managed refresh via relay service) | ✅ [token_relay_service.py](token_relay_service.py) rebuilt + verified locally (401 on bad key, 200 with valid token via [token_store.json](token_store.json) seeded from a fresh [go.py](go.py) run — `refresh_token` confirmed present, `expires_in: 604800`); **not yet deployed** |
| Moveworks support ticket | CS9539089 — closed out on the query-param injection question; workaround now owned internally |

## 5. Next Steps

1. Send the closing reply to Barkha confirming the workaround plan (drafted above) and, optionally, file the community ideas forum feature request for query-parameter token injection.
2. Deploy [token_relay_service.py](token_relay_service.py) to a publicly reachable HTTPS host (Azure App Service/Function, VM, Render, etc.) with env vars `PROJECTOR_TOKEN_URL`, `PROJECTOR_CLIENT_ID`, `PROJECTOR_CLIENT_SECRET`, `RELAY_API_KEY`, and persist [token_store.json](token_store.json) alongside it. Run behind a production WSGI server (gunicorn/waitress), not the Flask dev server.
3. Configure Moveworks Agent Studio: store `relay_api_key`/`relay_base_url` as secrets, add the "Get Relay Access Token" HTTP Action before "Get PM Projects", and wire `SessionTicket` to reference its output.
4. (Optional fallback) Separately confirm with Moveworks whether a writable Data Table exists that could persist a rotating `refresh_token` natively — would simplify things if available, but is not a blocker for proceeding now.
5. Once the relay is live and the flow works end-to-end, capture real screenshots to replace the "Live Demo" placeholder in [Allocation_Request_Enhanced.html](Allocation_Request_Enhanced.html).
