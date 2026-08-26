import requests
import os
import getpass
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("PROJECTOR_BASE_URL")
CLIENT_ID = os.getenv("PROJECTOR_CLIENT_ID")
CLIENT_SECRET = os.getenv("PROJECTOR_CLIENT_SECRET")
ACCOUNT_CODE = os.getenv("PROJECTOR_ACCOUNT_CODE")
TOKEN_URL = os.getenv("PROJECTOR_TOKEN_URL")

# Get user credentials for password grant
USERNAME = os.getenv("PROJECTOR_USERNAME") or input("Enter Projector username (email): ")
PASSWORD = os.getenv("PROJECTOR_PASSWORD") or getpass.getpass("Enter Projector password: ")

access_token = None

# Step 1: Try different OAuth2 grant types
print("=" * 60)
print("STEP 1: Getting OAuth2 Access Token...")
print("=" * 60)

# Attempt 1: password grant
grant_attempts = [
    {
        "name": "password grant (with AccountCode)",
        "data": {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username": USERNAME,
            "password": PASSWORD,
            "AccountCode": ACCOUNT_CODE,
        }
    },
    {
        "name": "password grant (without AccountCode)",
        "data": {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username": USERNAME,
            "password": PASSWORD,
        }
    },
    {
        "name": "password grant (username with account)",
        "data": {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username": f"{ACCOUNT_CODE}\\{USERNAME}",
            "password": PASSWORD,
        }
    },
]

for attempt in grant_attempts:
    print(f"\nTrying: {attempt['name']}...")
    try:
        resp = requests.post(TOKEN_URL, data=attempt["data"])
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            token_json = resp.json()
            access_token = token_json.get("access_token") or token_json.get("AccessToken")
            print(f"  SUCCESS! Token: {str(access_token)[:20]}...")
            print(f"  Full response keys: {list(token_json.keys())}")
            break
        else:
            print(f"  Response: {resp.text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")

if not access_token:
    print("\n  All OAuth attempts failed. Will try Basic Auth for endpoints.")

# Step 2: Try various API endpoints
print("\n" + "=" * 60)
print("STEP 2: Testing API Endpoints...")
print("=" * 60)

# Prepare auth headers
if access_token:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    auth = None
else:
    headers = {"Accept": "application/json"}
    auth = (USERNAME, PASSWORD)
    print("Using Basic Auth (no token)")

endpoints = [
    "/v1/users/lookup",
    "/v1/projects",
    "/v1/engagements",
    "/v1/resources",
    "/v1/clients",
    "/v1/me",
    "/api/v1/projects",
    "/api/v1/me",
    "/api/v1/users/lookup",
    "/odata/Projects",
    "/odata/Engagements",
    "/odata/$metadata",
    "/rest/v1/projects",
    "/rest/v1/me",
]

# Also try with query-param auth (Projector Report Web Services style)
report_endpoints = [
    f"/report/code/test?format=json&AccountCode={ACCOUNT_CODE}&UserName={USERNAME}&Password={PASSWORD}",
]

working_endpoints = []

for endpoint in endpoints:
    url = f"{BASE_URL}{endpoint}"
    try:
        if access_token:
            resp = requests.get(url, headers=headers, timeout=10, allow_redirects=False)
        else:
            resp = requests.get(url, headers=headers, auth=auth, timeout=10, allow_redirects=False)
        status = resp.status_code

        if status == 200:
            marker = "SUCCESS"
            working_endpoints.append(endpoint)
            body_preview = resp.text[:300]
            print(f"\n  [OK]  {endpoint} | Status: {status}")
            print(f"        Response: {body_preview}")
        elif status == 302:
            print(f"  [->]  {endpoint} | REDIRECT -> {resp.headers.get('Location', '?')[:80]}")
        elif status == 404:
            print(f"  [--]  {endpoint} | NOT FOUND")
        elif status == 401:
            print(f"  [!!]  {endpoint} | UNAUTHORIZED")
        else:
            print(f"  [??]  {endpoint} | Status: {status} | {resp.text[:80]}")
    except Exception as e:
        print(f"  [ERR] {endpoint} | {str(e)[:80]}")

# Step 3: Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

if working_endpoints:
    print(f"\n✅ Working endpoints found ({len(working_endpoints)}):")
    for ep in working_endpoints:
        print(f"   - {ep}")
else:
    print("\n❌ No working endpoints found.")
    print("   Possible reasons:")
    print("   1. Token might be invalid (check token step above)")
    print("   2. API paths might be different - ask your team")
    print("   3. User permissions might be insufficient")
