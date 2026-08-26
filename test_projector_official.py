"""
Projector API Test - Using OFFICIAL OAuth2 Developer Guide
Ref: https://projectorpsa.atlassian.net/wiki/spaces/AD/pages/9372088

Key findings from docs:
1. grant_type must be "code" (NOT "authorization_code")
2. Token response includes soap_service_authority and rest_service_authority
3. Access token is a "projector_session_ticket" (NOT a Bearer token)
4. API uses SOAP methods (PwsGetProjectList, etc.) not REST endpoints
"""
import requests
import os
import webbrowser
import http.server
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("PROJECTOR_BASE_URL")  # https://app4.projectorpsa.com
CLIENT_ID = os.getenv("PROJECTOR_CLIENT_ID")
CLIENT_SECRET = os.getenv("PROJECTOR_CLIENT_SECRET")
ACCOUNT_CODE = os.getenv("PROJECTOR_ACCOUNT_CODE")
TOKEN_URL = os.getenv("PROJECTOR_TOKEN_URL")

REDIRECT_PORT = 8765
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
            self.wfile.write(b"<h1>Success! Go back to terminal.</h1>")
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<h1>Failed: {params}</h1>".encode())
    def log_message(self, *a): pass

# ============================================================
# STEP 1: OAuth2 Authorization (browser-based)
# ============================================================
print("=" * 60)
print("STEP 1: OAuth2 Authorization Code Flow")
print("=" * 60)

auth_url = (
    f"{BASE_URL}/oauth2authorize/{ACCOUNT_CODE}?"
    f"response_type=code&"
    f"client_id={CLIENT_ID}&"
    f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
    f"scope=allowFullPermissions"
)

print(f"\nOpening browser for login...")
print(f"URL: {auth_url[:100]}...")
webbrowser.open(auth_url)

print("\nWaiting for callback (log in and click Authorize in browser)...")
server = http.server.HTTPServer(("localhost", REDIRECT_PORT), CallbackHandler)
server.handle_request()

if not auth_code:
    print("ERROR: No auth code received.")
    exit(1)
print(f"Auth code: {auth_code[:30]}...")

# ============================================================
# STEP 2: Exchange code for token (grant_type = "code" per docs!)
# ============================================================
print("\n" + "=" * 60)
print("STEP 2: Exchange code for token")
print("=" * 60)

token_data = {
    "grant_type": "code",          # Per Projector docs: "code" not "authorization_code"
    "code": auth_code,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
}

resp = requests.post(TOKEN_URL, data=token_data)
print(f"Status: {resp.status_code}")

if resp.status_code != 200:
    print(f"Response: {resp.text[:300]}")
    # Fallback: try standard "authorization_code" grant type
    print("\nTrying grant_type=authorization_code as fallback...")
    token_data["grant_type"] = "authorization_code"
    resp = requests.post(TOKEN_URL, data=token_data)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:300]}")

if resp.status_code != 200:
    print("FAILED to get token.")
    exit(1)

token_json = resp.json()
print(f"\nToken Response Keys: {list(token_json.keys())}")
print(f"Token Type: {token_json.get('token_type')}")
print(f"Expires In: {token_json.get('expires_in')} seconds")
print(f"Scope: {token_json.get('scope')}")

access_token = token_json.get("access_token")
soap_authority = token_json.get("soap_service_authority", "not provided")
rest_authority = token_json.get("rest_service_authority", "not provided")

print(f"\nAccess Token: {str(access_token)[:30]}...")
print(f"SOAP Service Authority: {soap_authority}")
print(f"REST Service Authority: {rest_authority}")

# ============================================================
# STEP 3: Test SOAP endpoints (the actual API)
# ============================================================
print("\n" + "=" * 60)
print("STEP 3: Testing SOAP Web Services")
print("=" * 60)

# The access token is a Projector Session Ticket
# Try SOAP call to PwsGetProjectList
soap_base = soap_authority if soap_authority != "not provided" else BASE_URL
soap_url = f"{soap_base}/OpsProjectorWcfSvc/PwsProjectorServices.svc"

print(f"\nSOAP endpoint: {soap_url}")

# Simple SOAP request for PwsGetProjectList
soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:pws="http://projectorpsa.com/PwsProjectorServices/IProjectorServices">
  <soap:Header>
    <pws:PwsAuthentication>
      <pws:SessionTicket>{access_token}</pws:SessionTicket>
    </pws:PwsAuthentication>
  </soap:Header>
  <soap:Body>
    <pws:PwsGetProjectList>
      <pws:projectListRequest>
        <pws:IncludeInactive>false</pws:IncludeInactive>
      </pws:projectListRequest>
    </pws:PwsGetProjectList>
  </soap:Body>
</soap:Envelope>"""

soap_headers = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": "http://projectorpsa.com/PwsProjectorServices/IProjectorServices/PwsGetProjectList",
}

try:
    r = requests.post(soap_url, data=soap_body, headers=soap_headers, timeout=30)
    print(f"SOAP Status: {r.status_code}")
    print(f"Response (first 500 chars): {r.text[:500]}")
    
    if r.status_code == 200 and "ProjectName" in r.text:
        print("\n*** SUCCESS! Got project list from SOAP API! ***")
except Exception as e:
    print(f"SOAP Error: {e}")

# ============================================================
# STEP 4: Test REST Report Services
# ============================================================
print("\n" + "=" * 60)
print("STEP 4: Testing REST Report Services")
print("=" * 60)

rest_base = rest_authority if rest_authority != "not provided" else BASE_URL

# Session ticket is used as a query param for REST services
rest_endpoints = [
    f"/report/code/test?format=json&SessionTicket={access_token}",
    f"/timesheet?SessionTicket={access_token}",
]

for ep in rest_endpoints:
    url = f"{rest_base}{ep}"
    try:
        r = requests.get(url, timeout=10, allow_redirects=False)
        print(f"  [{r.status_code}] {ep[:60]}...")
        if r.status_code == 200:
            print(f"        Response: {r.text[:200]}")
    except Exception as e:
        print(f"  [ERR] {ep[:60]}... => {e}")

# ============================================================
# STEP 5: Also try Bearer-style auth on REST
# ============================================================
print("\n" + "=" * 60)
print("STEP 5: Testing with Bearer-style auth on various paths")
print("=" * 60)

headers = {
    "Authorization": f"Bearer {access_token}",
    "Accept": "application/json",
}

rest_paths = [
    "/v1/users/lookup",
    "/v1/projects",
    "/api/v1/projects",
    "/odata/Projects",
]

for ep in rest_paths:
    url = f"{rest_base}{ep}"
    try:
        r = requests.get(url, headers=headers, timeout=10, allow_redirects=False)
        if r.status_code == 200:
            print(f"  [OK]  {ep} => {r.text[:200]}")
        elif r.status_code in (401, 403):
            print(f"  [!!]  {ep} => {r.status_code} (exists but auth issue)")
        elif r.status_code == 302:
            loc = r.headers.get("Location", "")
            if "Error" not in loc:
                print(f"  [->]  {ep} => {loc[:60]}")
    except:
        pass

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
print(f"\nKey info to use in Moveworks:")
print(f"  SOAP Authority: {soap_authority}")
print(f"  REST Authority: {rest_authority}")
print(f"  Token Type: {token_json.get('token_type')}")
