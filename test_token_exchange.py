"""
Projector Token Exchange Test
Since we can't use localhost as redirect_uri, this script:
1. Opens the correct auth URL (with Moveworks redirect_uri)
2. You authorize, then COPY the 'code' from the browser URL when it fails
3. Paste it here — the script exchanges it for a token and tests APIs

The code is short-lived (~60 seconds), so be FAST when copying it!
"""
import requests
import os
import json
import webbrowser
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("PROJECTOR_BASE_URL")          # https://app4.projectorpsa.com
CLIENT_ID = os.getenv("PROJECTOR_CLIENT_ID")
CLIENT_SECRET = os.getenv("PROJECTOR_CLIENT_SECRET")
ACCOUNT_CODE = os.getenv("PROJECTOR_ACCOUNT_CODE")
TOKEN_URL = os.getenv("PROJECTOR_TOKEN_URL")

# The REGISTERED redirect URI (Moveworks callback)
REDIRECT_URI = "https://cprime.moveworks.com/auth/oauthCallback"

TOKEN_FILE = "token.json"

# ============================================================
# Check for existing token first
# ============================================================
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE) as f:
        token_json = json.load(f)
    print(f"Found existing {TOKEN_FILE}")
    print(f"  access_token: {str(token_json.get('access_token',''))[:30]}...")
    print(f"  rest_service_authority: {token_json.get('rest_service_authority')}")
    print(f"  soap_service_authority: {token_json.get('soap_service_authority')}")
    use = input("\nUse existing token? (y/n): ").strip().lower()
    if use == "y":
        access_token = token_json.get("access_token")
        rest_authority = token_json.get("rest_service_authority", BASE_URL)
        soap_authority = token_json.get("soap_service_authority", "")
        # Skip to API testing
        print("\nSkipping to API tests...")
    else:
        token_json = None
else:
    token_json = None

if not token_json or (token_json and input if use != "y" else False):
    # ============================================================
    # STEP 1: Open browser for authorization
    # ============================================================
    print("=" * 60)
    print("STEP 1: Open browser for OAuth authorization")
    print("=" * 60)

    auth_url = (
        f"{BASE_URL}/oauth2authorize/{ACCOUNT_CODE}?"
        f"response_type=code&"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
        f"scope=allowFullPermissions"
    )

    print(f"\nOpening browser...")
    print(f"After you Authorize, the page will show 'Callback Request Failed'")
    print(f"QUICKLY copy the 'code' value from the browser URL bar!")
    print(f"\nLook for: ...oauthCallback?code=XXXXX&state=...")
    print(f"Copy everything between 'code=' and '&state'\n")

    webbrowser.open(auth_url)

    # ============================================================
    # STEP 2: Get the code from user
    # ============================================================
    print("=" * 60)
    print("STEP 2: Paste the authorization code")
    print("=" * 60)

    code_input = input("\nPaste the full callback URL or just the code value: ").strip()

    # Extract code from full URL if pasted
    if "code=" in code_input:
        parsed = urllib.parse.urlparse(code_input)
        params = urllib.parse.parse_qs(parsed.query)
        auth_code = params.get("code", [code_input])[0]
    else:
        auth_code = code_input

    print(f"\nAuth code: {auth_code[:30]}...")

    # ============================================================
    # STEP 3: Exchange code for token
    # ============================================================
    print("\n" + "=" * 60)
    print("STEP 3: Exchange code for access token")
    print("=" * 60)

    # Try both grant_type values
    grant_types = ["authorization_code", "code"]
    token_json = None

    for gt in grant_types:
        print(f"\n  Trying grant_type={gt}...")
        token_data = {
            "grant_type": gt,
            "code": auth_code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
        }

        resp = requests.post(TOKEN_URL, data=token_data)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            token_json = resp.json()
            print(f"  SUCCESS with grant_type={gt}!")
            break
        else:
            print(f"  Response: {resp.text[:200]}")

    if not token_json:
        print("\nFAILED to get token with both grant types.")
        print("The auth code may have expired (they last ~60 seconds).")
        print("Try running the script again and paste the code faster.")
        exit(1)

    # Save token
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_json, f, indent=2)
    print(f"\nToken saved to {TOKEN_FILE}")

    access_token = token_json.get("access_token")
    rest_authority = token_json.get("rest_service_authority", BASE_URL)
    soap_authority = token_json.get("soap_service_authority", "")

# ============================================================
# Show token details
# ============================================================
print(f"\n{'=' * 60}")
print("TOKEN INFO")
print(f"{'=' * 60}")
print(f"  Access Token:  {str(access_token)[:30]}...")
print(f"  Token Type:    {token_json.get('token_type')}")
print(f"  Expires In:    {token_json.get('expires_in')} seconds")
print(f"  REST Authority:{rest_authority}")
print(f"  SOAP Authority:{soap_authority}")
print(f"  Scope:         {token_json.get('scope')}")
print(f"  All keys:      {list(token_json.keys())}")

# ============================================================
# STEP 4: Test REST endpoints
# ============================================================
print(f"\n{'=' * 60}")
print("STEP 4: Testing REST API")
print(f"{'=' * 60}")

headers = {
    "Authorization": f"Bearer {access_token}",
    "Accept": "application/json",
}

rest_endpoints = [
    "/api/v1/projects",
    "/api/v1/resources",
    "/api/v1/timesheets",
]

for ep in rest_endpoints:
    url = f"{rest_authority}{ep}"
    try:
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=False)
        if r.status_code == 200:
            print(f"\n  [OK] {ep}")
            try:
                data = r.json()
                if isinstance(data, list):
                    print(f"       Items: {len(data)}")
                    if len(data) > 0:
                        print(f"       First item keys: {list(data[0].keys())[:10]}")
                        print(f"       First item: {json.dumps(data[0], indent=2)[:300]}")
                elif isinstance(data, dict):
                    print(f"       Keys: {list(data.keys())[:10]}")
                    print(f"       Preview: {json.dumps(data, indent=2)[:300]}")
            except:
                print(f"       Response: {r.text[:200]}")
        elif r.status_code == 302:
            loc = r.headers.get("Location", "")
            print(f"  [->] {ep} => {loc[:80]}")
        elif r.status_code == 401:
            print(f"  [!!] {ep} => 401 UNAUTHORIZED")
        else:
            print(f"  [{r.status_code}] {ep} => {r.text[:100]}")
    except Exception as e:
        print(f"  [ERR] {ep} => {e}")

# ============================================================
# STEP 5: Test SOAP — PwsGetProjectList
# ============================================================
print(f"\n{'=' * 60}")
print("STEP 5: Testing SOAP API — PwsGetProjectList")
print(f"{'=' * 60}")

if soap_authority:
    soap_url = f"{soap_authority}/OpsProjectorWcfSvc/PwsProjectorServices.svc"
    ns = "http://projectorpsa.com/PwsProjectorServices/"
    action_base = "http://projectorpsa.com/PwsProjectorServices/IPwsProjectorServices/"

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

    print(f"  SOAP URL: {soap_url}")
    try:
        r = requests.post(soap_url, data=envelope.encode("utf-8"), headers=soap_headers, timeout=30)
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            if "ProjectName" in r.text or "ProjectIdentity" in r.text:
                count = r.text.count("ProjectIdentity")
                print(f"  SUCCESS! Projects found: ~{count}")
            print(f"  Response (first 800 chars):\n{r.text[:800]}")
        else:
            print(f"  Response: {r.text[:300]}")
    except Exception as e:
        print(f"  Error: {e}")
else:
    print("  No soap_service_authority. Skipping.")

print(f"\n{'=' * 60}")
print("DONE")
print(f"{'=' * 60}")
