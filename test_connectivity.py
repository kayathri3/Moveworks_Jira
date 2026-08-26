"""
Simple Projector API connectivity test.
Tests if we can reach the base URL and discovers any accessible paths.
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("PROJECTOR_BASE_URL")

print("=" * 60)
print(f"Testing connectivity to: {BASE_URL}")
print("=" * 60)

# Test 1: Can we reach the base URL at all?
print("\n[1] Base URL reachability...")
try:
    r = requests.get(BASE_URL, timeout=10, allow_redirects=False)
    print(f"    Status: {r.status_code}")
    print(f"    Headers: {dict(list(r.headers.items())[:5])}")
    if r.status_code in (301, 302):
        print(f"    Redirects to: {r.headers.get('Location')}")
    print("    => Server is REACHABLE")
except Exception as e:
    print(f"    ERROR: {e}")
    print("    => Server is NOT reachable. Check network/VPN.")
    exit(1)

# Test 2: OAuth2 token endpoint exists?
print("\n[2] OAuth2 token endpoint...")
token_url = os.getenv("PROJECTOR_TOKEN_URL")
try:
    r = requests.post(token_url, data={"grant_type": "test"}, timeout=10)
    print(f"    Status: {r.status_code}")
    print(f"    Response: {r.text[:200]}")
    if r.status_code == 400:
        print("    => Token endpoint EXISTS and responds (rejected bad grant type = working)")
    elif r.status_code == 200:
        print("    => Token endpoint works!")
except Exception as e:
    print(f"    ERROR: {e}")

# Test 3: OAuth2 authorize endpoint exists?
print("\n[3] OAuth2 authorize endpoint...")
acct = os.getenv("PROJECTOR_ACCOUNT_CODE")
auth_url = f"{BASE_URL}/oauth2authorize/{acct}"
try:
    r = requests.get(auth_url, timeout=10, allow_redirects=False)
    print(f"    Status: {r.status_code}")
    if r.status_code == 200:
        print(f"    Response preview: {r.text[:150]}")
        print("    => Authorize endpoint EXISTS")
    elif r.status_code in (301, 302):
        print(f"    Redirects to: {r.headers.get('Location', '')[:100]}")
except Exception as e:
    print(f"    ERROR: {e}")

# Test 4: SOAP Web Services endpoint
print("\n[4] SOAP Web Services endpoints...")
soap_endpoints = [
    "/OpsProjectorWebSvc/OpsProjectorSvc.asmx",
    "/OpsProjectorWebSvc/OpsProjectorSvc.asmx?wsdl",
    "/OpsProjectorWcfSvc/PwsProjectorServices.svc",
    "/OpsProjectorWcfSvc/PwsProjectorServices.svc?wsdl",
]
for ep in soap_endpoints:
    try:
        r = requests.get(f"{BASE_URL}{ep}", timeout=10, allow_redirects=False)
        status = r.status_code
        if status == 200:
            preview = r.text[:100].replace("\n", " ")
            print(f"    [OK]  {ep} => {preview}")
        elif status in (301, 302):
            loc = r.headers.get("Location", "")
            if "Error" not in loc:
                print(f"    [->]  {ep} => {loc[:80]}")
        elif status == 404:
            print(f"    [--]  {ep} => Not Found")
        else:
            print(f"    [{status}] {ep}")
    except Exception as e:
        print(f"    [ERR] {ep} => {e}")

# Test 5: Known Projector web pages (to confirm server is fully working)
print("\n[5] Projector web pages (no auth needed)...")
page_endpoints = [
    "/",
    "/timesheet",
    "/Login",
    "/login",
    "/Account/Login",
]
for ep in page_endpoints:
    try:
        r = requests.get(f"{BASE_URL}{ep}", timeout=10, allow_redirects=False)
        status = r.status_code
        content_type = r.headers.get("Content-Type", "")[:40]
        if status == 200:
            # Check if it's HTML (a real page)
            is_html = "html" in content_type.lower()
            has_projector = "projector" in r.text.lower() or "bigtime" in r.text.lower()
            print(f"    [OK]  {ep} | {content_type} | Projector page: {has_projector}")
        elif status in (301, 302):
            print(f"    [->]  {ep} => {r.headers.get('Location', '')[:80]}")
        else:
            print(f"    [{status}] {ep} | {content_type}")
    except Exception as e:
        print(f"    [ERR] {ep} => {e}")

# Test 6: Try to discover any API-like paths
print("\n[6] Scanning for API paths...")
scan_paths = [
    "/api",
    "/api/",
    "/api/v1",
    "/api/v2",
    "/v1",
    "/v2",
    "/rest",
    "/odata",
    "/graphql",
    "/swagger",
    "/swagger/ui",
    "/api-docs",
    "/openapi.json",
    "/.well-known/openid-configuration",
]
for ep in scan_paths:
    try:
        r = requests.get(f"{BASE_URL}{ep}", timeout=10, allow_redirects=False)
        status = r.status_code
        if status == 200:
            ct = r.headers.get("Content-Type", "")[:40]
            preview = r.text[:100].replace("\n", " ")
            print(f"    [OK]  {ep} | {ct} | {preview}")
        elif status in (301, 302):
            loc = r.headers.get("Location", "")
            if "Error" not in loc and "login" not in loc.lower():
                print(f"    [->]  {ep} => {loc[:80]}")
        elif status == 404:
            pass  # silently skip
        elif status in (401, 403):
            print(f"    [!!]  {ep} => {status} (exists but needs auth!)")
        elif status != 500:
            print(f"    [{status}] {ep}")
    except:
        pass

print("\n" + "=" * 60)
print("DONE - Check results above")
print("=" * 60)
