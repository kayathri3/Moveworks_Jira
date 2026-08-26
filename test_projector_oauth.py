"""
Projector API Tester with Authorization Code Flow
Opens a browser for OAuth login, captures the token, then tests endpoints.
"""
import requests
import os
import webbrowser
import http.server
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("PROJECTOR_BASE_URL")
CLIENT_ID = os.getenv("PROJECTOR_CLIENT_ID")
CLIENT_SECRET = os.getenv("PROJECTOR_CLIENT_SECRET")
ACCOUNT_CODE = os.getenv("PROJECTOR_ACCOUNT_CODE")
TOKEN_URL = os.getenv("PROJECTOR_TOKEN_URL")

REDIRECT_PORT = 8765
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"
AUTH_URL = f"{BASE_URL}/oauth2authorize/{ACCOUNT_CODE}"

auth_code = None

class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization successful!</h1><p>You can close this window and go back to the terminal.</p>")
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            error = params.get("error", ["unknown"])[0]
            self.wfile.write(f"<h1>Authorization failed: {error}</h1>".encode())
    
    def log_message(self, format, *args):
        pass  # Suppress server logs

# Step 1: Open browser for authorization
print("=" * 60)
print("STEP 1: Browser-based OAuth2 Authorization")
print("=" * 60)

authorize_url = (
    f"{AUTH_URL}?"
    f"response_type=code&"
    f"client_id={CLIENT_ID}&"
    f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
)

print(f"\nOpening browser for Projector login...")
print(f"If browser doesn't open, visit:\n{authorize_url}\n")
webbrowser.open(authorize_url)

# Start local server to capture callback
print("Waiting for authorization callback...")
server = http.server.HTTPServer(("localhost", REDIRECT_PORT), OAuthCallbackHandler)
server.handle_request()  # Handle single request

if not auth_code:
    print("ERROR: No authorization code received. Exiting.")
    exit(1)

print(f"Authorization code received: {auth_code[:20]}...")

# Step 2: Exchange code for token
print("\n" + "=" * 60)
print("STEP 2: Exchanging code for access token...")
print("=" * 60)

token_data = {
    "grant_type": "authorization_code",
    "code": auth_code,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
}

resp = requests.post(TOKEN_URL, data=token_data)
print(f"Token response status: {resp.status_code}")
print(f"Token response: {resp.text[:300]}")

if resp.status_code != 200:
    # Try with AccountCode
    token_data["AccountCode"] = ACCOUNT_CODE
    resp = requests.post(TOKEN_URL, data=token_data)
    print(f"\nRetry with AccountCode - Status: {resp.status_code}")
    print(f"Response: {resp.text[:300]}")

if resp.status_code != 200:
    print("Failed to get token. Exiting.")
    exit(1)

token_json = resp.json()
access_token = token_json.get("access_token") or token_json.get("AccessToken")
print(f"\nAccess token obtained: {str(access_token)[:20]}...")
print(f"Token response keys: {list(token_json.keys())}")

# Step 3: Test endpoints with real token
print("\n" + "=" * 60)
print("STEP 3: Testing ALL possible endpoints...")
print("=" * 60)

headers = {
    "Authorization": f"Bearer {access_token}",
    "Accept": "application/json",
}

endpoints = [
    # Common REST patterns
    "/v1/users/lookup",
    "/v1/projects",
    "/v1/engagements",
    "/v1/resources",
    "/v1/clients",
    "/v1/me",
    "/v1/account",
    "/v1/timesheets",
    # API prefix
    "/api/v1/projects",
    "/api/v1/me",
    "/api/v1/users",
    "/api/v2/projects",
    "/api/v2/me",
    "/api/projects",
    "/api/me",
    # OData
    "/odata/Projects",
    "/odata/Engagements",
    "/odata/Resources",
    "/odata/$metadata",
    # REST
    "/rest/v1/projects",
    "/rest/v1/me",
    # Projector-specific paths
    "/PwsProjectorSvc/projects",
    "/timesheet",
    "/projects",
    "/engagements",
    "/resources",
    # Web services
    "/OpsProjectorWebSvc/OpsProjectorSvc.asmx",
    "/OpsProjectorWcfSvc/PwsProjectorServices.svc",
]

working = []
for ep in endpoints:
    url = f"{BASE_URL}{ep}"
    try:
        r = requests.get(url, headers=headers, timeout=10, allow_redirects=False)
        if r.status_code == 200:
            preview = r.text[:200].replace("\n", " ")
            print(f"\n  [OK]  {ep}")
            print(f"        {preview}")
            working.append(ep)
        elif r.status_code in (301, 302):
            loc = r.headers.get("Location", "")
            if "Error" not in loc and "login" not in loc.lower():
                print(f"  [->]  {ep} -> {loc[:80]}")
            # skip error redirects silently
        elif r.status_code == 404:
            pass  # skip not found silently
        elif r.status_code == 401:
            print(f"  [!!]  {ep} | 401 UNAUTHORIZED (endpoint exists but no access)")
        else:
            print(f"  [??]  {ep} | {r.status_code} | {r.text[:80]}")
    except Exception as e:
        pass

# Summary
print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)
if working:
    print(f"\nWorking endpoints ({len(working)}):")
    for ep in working:
        print(f"   {ep}")
else:
    print("\nNo standard REST endpoints found.")
    print("Projector PSA uses SOAP Web Services + Report Web Services only.")
    print("\nNEXT STEPS:")
    print("1. Ask your team for the specific API endpoints")
    print("2. Or create a Report in Projector and use Report Web Services")
    print(f"   Format: {BASE_URL}/report/code/{{WebServiceCode}}?format=json")
