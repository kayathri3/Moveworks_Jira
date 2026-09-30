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

### Phase 8 — Pivoted from hosted relay to a GitHub-Actions-based relay (no server) and got it fully working end-to-end (2026-09-29)
- User had no hosting account/payment method available (Azure/Render/Fly.io all required either existing access or a card on file), so the plan changed: **use GitHub itself as the "relay"** instead of deploying [token_relay_service.py](token_relay_service.py) anywhere.
- Built a new mechanism:
  - [scripts/refresh_projector_token.py](scripts/refresh_projector_token.py) — refreshes the Projector token via `grant_type=refresh_token` and overwrites [token_relay/token_public.json](token_relay/token_public.json).
  - [.github/workflows/refresh-projector-token.yml](.github/workflows/refresh-projector-token.yml) — GitHub Actions workflow, scheduled daily (`cron: 0 3 * * *`, well inside the 7-day token lifetime), commits the refreshed token back to the repo.
  - Seeded [token_relay/token_public.json](token_relay/token_public.json) from a verified-live token before first run.
- Verified the workflow manually via "Run workflow": first attempt failed (`MissingSchema` — repo secrets `PROJECTOR_TOKEN_URL`/`PROJECTOR_CLIENT_ID`/`PROJECTOR_CLIENT_SECRET` not yet added), second attempt succeeded and committed a freshly rotated token.
- Created a **fine-grained GitHub PAT** (Contents: Read-only, scoped to this one repo) so Moveworks can read the token file via `GET https://api.github.com/repos/kayathri3/Moveworks_Jira/contents/token_relay/token_public.json` with header `Accept: application/vnd.github.raw+json` — confirmed working via a local curl test (returns raw JSON, not the base64-wrapped GitHub metadata).
- **Built the Moveworks side in Tool Studio:**
  - HTTP Action `Get_GitHub_Relay_Token` (No-Auth connector, `Authorization: Bearer <PAT>` + `Accept: application/vnd.github.raw+json` headers) — tested standalone, returns `200` with the live token JSON.
  - Updated `Projector_Get_PM_Projects`: added a proper **Input Argument** `access_token` (previously it only had a manually-typed literal, which was the Phase 5 root cause repeating itself), changed `SessionTicket` query param to `{{access_token}}`, and switched its connector from the broken `Projector_Sandbox_2` OAuth2 connector to a **new No-Auth connector** (the OAuth2 connector was still auto-injecting a stale/broken `Authorization` header even though it was unused, causing the same `unauthenticated` error page).
  - Created **Compound Action `Get_PM_Projects_With_Relay_Token`** (description: *"Fetches a live Projector OAuth token from the GitHub relay, then calls Projector's PM Projects report to return active project details (name, SFDC code, PM, client, end date) for Jira allocation requests — no manual token entry needed."*) with two steps: `get_github_relay_token` (Output Key `relay_token_result`) → `projector_get_pm_projects` (Data Mapper: `access_token: relay_token_result.access_token`).
- **Debugging along the way** (useful lessons for next time):
  - Individual HTTP Actions tested standalone can't resolve cross-step `{{step.output}}` references — that only resolves when run as part of a Compound Action.
  - Compound Action Data Mapper is literal YAML — `key:value` (no space) fails with `ORCHESTRATION_STUDIO_INVALID_SYNTAX_ERROR`; needs `key: value`.
  - Compound Action descriptions are capped at 256 characters.
  - Publishing matters: a Compound Action can run against a **stale published version** of a referenced Tool even after the Tool's draft was edited — must **Publish** the Tool after each fix.
  - `Projector_Sandbox_2`'s OAuth2 refresh broke separately (`invalid_grant: Refresh Token not Found`) because it and the new GitHub-Actions refresh cycle both draw from Projector's shared, limited pool of concurrent OAuth connections for the same `client_id` (the `OauthConnectionsCulledWarning` seen back in Phase 6) — they evict each other. Since this flow no longer needs `Projector_Sandbox_2` at all, the plan is to disconnect/remove it once confirmed unused elsewhere.
- **Confirmed fully working end-to-end** (2026-09-29 13:20 UTC run): Compound Action returned real rows — `ProjectName`, `ProjectManager`, `ProjectCode`, `ClientName`, `ProjectEndDate` for Cprime Internal, Cprime West/East/Central, and several employee/intern projects — with zero manual token entry anywhere in the chain.
- Sent final short thank-you reply to Barkha closing out ticket CS9539089.

### Phase 9 — Analysis of the live plugin flow and remaining build plan (2026-09-29)
- Process analysed: `Jira ticketing process - 2` (V3 published). Top-level Policy with 2 cases:
  - Software request case: `get_jira_account_id` → `get_user_manager` → `jira_search_existing_tickets` → Policy on `data.add_comments` (`approve_reject_action`) → `create_installation_request` → `get_jira_account_id` → `add_approver_to_ticket` → `notify_managers_jira` → Exit.
  - `data.request_type == "Allocations"` case: Content (rules text) → `Jira_Create_allocations_request` (consent required, Output Key `allocation_request_data`) → Content (success message) → Exit. Default case: "Sorry, your request cannot be processed. Please contact support".
- `Jira_Create_allocations_request` required slots: `allocation_data`, `summary`, `priority`, `region`, `due_date`, `sfdc`, `client_name`; data mapper also passes `requested_for: meta_info.user.email_addr`.
- Slot `allocation_data` is a plain `string`; its description already lists the mandatory fields per request type (New: full name, hours/week, rate/hour, start, end; Extension: full name, hours/week, start, end; Removal: full name, remove-from, remove-until), resources comma-separated. Mandatory-field checking therefore relies on this description — to be reinforced with explicit "ask for missing data, do not proceed" wording.
- Today `client_name`, `sfdc`, `due_date`, `priority`, `summary` are all asked from the user; the enhancement must fill them from Projector (client, SFDC = `ProjectCode`, project end date) and auto-calculate priority/summary.
- The action's response schema shows `{}` — the Jira ticket portal-link field name is unknown until the action is run once; needed for the success message ("only provide portal link").
- **Known gap:** the Projector report is `For Entire Organization` (all projects, ~118 KB), not filtered to the logged-in PM; `ProjectManager` is formatted `Name (EmployeeID)`. A script/filter step is needed to match the user to their projects.
- Required success message: Ticket (portal link only), Summary, Client name, Region, Priority, Due date, SFDC Opportunity Code, Allocation details.

---

## 4. Current Status / Blockers

| Item | Status |
|---|---|
| Projector OAuth "Custom Grant Type" fix | ✅ Confirmed working (Callback Request Successful) |
| Legacy report endpoint (`/report/code/pm_projects`) via Postman | ✅ Returns correct data with manual token |
| Moveworks HTTP Action auto-injecting token into `SessionTicket` query param | ❌ Confirmed unsupported by Moveworks support — official platform limitation, logged as a feature request |
| Path A (header-based `/api/v1/projects`) | ⚠️ Untested/unconfirmed — currently returns 302 redirect to error page in sandbox; abandoned in favor of Path B |
| Path B, hosted Flask relay ([token_relay_service.py](token_relay_service.py)) | ⚠️ Superseded — no hosting/payment method available (Azure/Render/Fly.io all blocked); replaced by the GitHub Actions-based relay below |
| **Path B, final: GitHub Actions relay** ([.github/workflows/refresh-projector-token.yml](.github/workflows/refresh-projector-token.yml) + [token_relay/token_public.json](token_relay/token_public.json)) | ✅ **Live and working** — daily cron refresh confirmed committing new tokens; Moveworks reads the file via GitHub Contents API with a fine-grained PAT |
| Moveworks Compound Action `Get_PM_Projects_With_Relay_Token` | ✅ **Confirmed working end-to-end** (2026-09-29) — returns real project rows (name, PM, code, client, end date) with zero manual token entry |
| Moveworks support ticket | CS9539089 — closed out with a brief thank-you reply to Barkha |
| `Projector_Sandbox_2` OAuth2 connector | No longer needed by this flow; broke separately due to shared OAuth-grant-pool contention with the GitHub refresh cycle — pending confirmation it's unused elsewhere, then to be disconnected |
| Fine-grained GitHub PAT used by `Get_GitHub_Relay_Token` | ⚠️ Expires **Oct 29, 2026** — plan is to replace it with a **classic PAT (No expiration, `repo` scope)** for a true "set and forget" setup |

## 5. Next Steps

1. ~~Send the closing reply to Barkha~~ — done.
2. ~~Deploy the relay~~ — done via GitHub Actions instead of a hosted server.
3. ~~Configure the Moveworks HTTP Actions + Compound Action~~ — done and verified working.
4. **Replace the fine-grained PAT with a non-expiring classic PAT** (`repo` scope) in `Get_GitHub_Relay_Token`'s Authorization header, so this never needs manual renewal.
5. **Wire `Get_PM_Projects_With_Relay_Token` into the Allocations case of `Jira ticketing process - 2`** (before `Jira_Create_allocations_request`), then: filter rows to the logged-in PM, let the user pick a project, map `client_name`/`sfdc`/`due_date` from it, auto-calc `priority`/`summary` (script action), drop those slots from the required list, and rebuild the success message with only the portal link. Also reinforce the `allocation_data` slot description with "ask for missing mandatory fields; do not proceed".
6. Confirm `Projector_Sandbox_2` is unused elsewhere in the plugin, then disconnect/remove it to stop the OAuth-grant-pool contention with the GitHub refresh cycle.
7. Once wired into the live flow, capture real screenshots to replace the "Live Demo" placeholder in [Allocation_Request_Enhanced.html](Allocation_Request_Enhanced.html).
