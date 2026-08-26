"""
Projector API Test — Based on official API_Call_Guide 1.md
Handles OAuth2 Authorization Code flow, then tests REST + SOAP endpoints.

For sandbox (app4):
  - REST base: from token response rest_service_authority 
  - SOAP base: from token response soap_service_authority
  - OAuth authorize: https://app4.projectorpsa.com/oauth2authorize/Cprime-sandbox
  - OAuth token: https://app4.projectorpsa.com/oauth2token
  - grant_type: authorization_code
  - Redirect URI: http://localhost:8080/callback (must be registered in Projector)
"""
import requests
import os
import json
import webbrowser
import http.server
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("PROJECTOR_BASE_URL")          # https://app4.projectorpsa.com
CLIENT_ID = os.getenv("PROJECTOR_CLIENT_ID")
CLIENT_SECRET = os.getenv("PROJECTOR_CLIENT_SECRET")
ACCOUNT_CODE = os.getenv("PROJECTOR_ACCOUNT_CODE")   # Cprime-sandbox
TOKEN_URL = os.getenv("PROJECTOR_TOKEN_URL")          # https://app4.projectorpsa.com/oauth2token

REDIRECT_PORT = 8080
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"

auth_code = None

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization successful! Go back to the terminal.</h1>")
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            error = params.get("error", ["unknown"])[0]
            desc = params.get("error_description", [""])[0]
            self.wfile.write(f"<h1>Failed: {error}</h1><p>{desc}</p>".encode())
    def log_message(self, *a): pass

# ============================================================
# Check for existing token
# ============================================================
TOKEN_FILE = "token.json"
token_json = None

if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE) as f:
        token_json = json.load(f)
    print(f"Found existing {TOKEN_FILE}")
    print(f"  access_token: {str(token_json.get('access_token',''))[:20]}...")
    print(f"  rest_service_authority: {token_json.get('rest_service_authority')}")
    print(f"  soap_service_authority: {token_json.get('soap_service_authority')}")
    
    use_existing = input("\nUse existing token? (y/n): ").strip().lower()
    if use_existing != "y":
        token_json = None

if not token_json:
    # ============================================================
    # STEP 1: OAuth2 Authorization Code Flow
    # ============================================================
    print("=" * 60)
    print("STEP 1: OAuth2 Authorization — Opening browser")
    print("=" * 60)

    auth_url = (
        f"{BASE_URL}/oauth2authorize/{ACCOUNT_CODE}?"
        f"response_type=code&"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
        f"scope=allowFullPermissions"
    )

    print(f"\nRedirect URI: {REDIRECT_URI}")
    print(f"Auth URL: {auth_url[:120]}...")
    print("\nOpening browser — log in and click Authorize...")
    webbrowser.open(auth_url)

    print(f"Listening on port {REDIRECT_PORT} for callback...")
    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), CallbackHandler)
    server.handle_request()

    if not auth_code:
        print("ERROR: No auth code received. Exiting.")
        exit(1)
    print(f"\nAuth code received: {auth_code[:30]}...")

    # ============================================================
    # STEP 2: Exchange code for token
    # ============================================================
    print("\n" + "=" * 60)
    print("STEP 2: Exchange code for access token")
    print("=" * 60)

    token_data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
    }

    resp = requests.post(TOKEN_URL, data=token_data)
    print(f"Status: {resp.status_code}")

    if resp.status_code != 200:
        print(f"ERROR: {resp.text[:400]}")
        exit(1)

    token_json = resp.json()

    # Save token for reuse
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_json, f, indent=2)
    print(f"Token saved to {TOKEN_FILE}")

# ============================================================
# Extract token info
# ============================================================
access_token = token_json.get("access_token")
rest_authority = token_json.get("rest_service_authority", BASE_URL)
soap_authority = token_json.get("soap_service_authority", "")

print(f"\n{'=' * 60}")
print(f"TOKEN INFO")
print(f"{'=' * 60}")
print(f"  Access Token:  {str(access_token)[:30]}...")
print(f"  Token Type:    {token_json.get('token_type')}")
print(f"  Expires In:    {token_json.get('expires_in')} seconds")
print(f"  REST Base:     {rest_authority}")
print(f"  SOAP Base:     {soap_authority}")
print(f"  Scope:         {token_json.get('scope')}")

# ============================================================
# STEP 3: Test REST endpoints (from API guide)
# ============================================================
print(f"\n{'=' * 60}")
print("STEP 3: Testing REST API Endpoints")
print(f"{'=' * 60}")

headers = {
    "Authorization": f"Bearer {access_token}",
    "Accept": "application/json",
}

rest_endpoints = [
    "/api/v1/projects",
    "/api/v1/resources",
    "/api/v1/timesheets",
    "/api/v1/invoices",
    "/api/v1/expenses",
]

for ep in rest_endpoints:
    url = f"{rest_authority}{ep}"
    try:
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=False)
        if r.status_code == 200:
            data = r.text[:300]
            print(f"\n  [OK]  {ep}")
            print(f"        Status: 200")
            print(f"        Response: {data}")
            # Try to count items if JSON array
            try:
                items = r.json()
                if isinstance(items, list):
                    print(f"        Items: {len(items)}")
                elif isinstance(items, dict):
                    print(f"        Keys: {list(items.keys())[:10]}")
            except:
                pass
        elif r.status_code == 302:
            loc = r.headers.get("Location", "")
            print(f"  [->]  {ep} => REDIRECT to {loc[:80]}")
        elif r.status_code == 401:
            print(f"  [!!]  {ep} => 401 UNAUTHORIZED (token expired or invalid)")
        elif r.status_code == 404:
            print(f"  [--]  {ep} => 404 NOT FOUND")
        else:
            print(f"  [{r.status_code}]  {ep} => {r.text[:100]}")
    except Exception as e:
        print(f"  [ERR] {ep} => {e}")

# ============================================================
# STEP 4: Test SOAP endpoint — PwsGetProjectList
# ============================================================
print(f"\n{'=' * 60}")
print("STEP 4: Testing SOAP API — PwsGetProjectList")
print(f"{'=' * 60}")

if soap_authority:
    soap_url = f"{soap_authority}/OpsProjectorWcfSvc/PwsProjectorServices.svc"
    ns = "http://projectorpsa.com/PwsProjectorServices/"
    action_base = "http://projectorpsa.com/PwsProjectorServices/IPwsProjectorServices/"

    # PwsGetProjectList SOAP envelope (using Ticket in body per guide)
    envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:pws="{ns}">
  <soapenv:Header/>
  <soapenv:Body>
    <pws:PwsGetProjectList>
      <pws:request>
        <pws:Ticket>{access_token}</pws:Ticket>
      </pws:request>
    </pws:PwsGetProjectList>
  </soapenv:Body>
</soapenv:Envelope>"""

    soap_headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{action_base}PwsGetProjectList"',
    }

    print(f"\n  SOAP URL: {soap_url}")
    try:
        r = requests.post(soap_url, data=envelope.encode("utf-8"), headers=soap_headers, timeout=30)
        print(f"  Status: {r.status_code}")
        
        if r.status_code == 200:
            # Check for project data in response
            if "ProjectName" in r.text or "ProjectIdentity" in r.text:
                print(f"  *** SUCCESS — Got project data! ***")
                # Count projects
                count = r.text.count("ProjectIdentity")
                print(f"  Projects found: ~{count}")
            print(f"  Response (first 500 chars):\n{r.text[:500]}")
        else:
            print(f"  Response: {r.text[:300]}")
    except Exception as e:
        print(f"  Error: {e}")
else:
    print("  No soap_service_authority in token response. Skipping SOAP test.")

# ============================================================
# SUMMARY
# ============================================================
print(f"\n{'=' * 60}")
print("SUMMARY")
print(f"{'=' * 60}")
print(f"  REST Base URL:  {rest_authority}")
print(f"  SOAP Base URL:  {soap_authority}")
print(f"  Token saved to: {TOKEN_FILE}")
print(f"\n  Use this info to configure Moveworks HTTP Actions:")
print(f"  - For REST: GET {rest_authority}/api/v1/projects")
print(f"  - For SOAP: POST {soap_authority}/OpsProjectorWcfSvc/PwsProjectorServices.svc")
