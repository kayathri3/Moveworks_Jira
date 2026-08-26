import requests, json, os, webbrowser
from dotenv import load_dotenv
load_dotenv()

# Step 1: Open browser for fresh authorization
auth_url = (
    f"{os.getenv('PROJECTOR_BASE_URL')}/oauth2authorize/{os.getenv('PROJECTOR_ACCOUNT_CODE')}"
    f"?response_type=code"
    f"&client_id={os.getenv('PROJECTOR_CLIENT_ID')}"
    f"&redirect_uri=https%3A%2F%2Fcprime.moveworks.com%2Fauth%2FoauthCallback"
    f"&scope=allowFullPermissions"
)
print("Opening browser for authorization...")
webbrowser.open(auth_url)

# Step 2: Wait for user to paste the code
print("\n>>> AFTER you authorize and see 'Callback Failed':")
print(">>> Copy the code from the URL (after ?code= and before &state=)")
print(">>> Paste it below and press Enter IMMEDIATELY\n")
code = input("Paste code here: ").strip()

if "code=" in code:
    code = code.split("code=")[1].split("&")[0]

# Step 3: Exchange immediately
print(f"\nExchanging code: {code[:25]}...")
resp = requests.post(os.getenv("PROJECTOR_TOKEN_URL"), data={
    "grant_type": "code",
    "code": code,
    "client_id": os.getenv("PROJECTOR_CLIENT_ID"),
    "client_secret": os.getenv("PROJECTOR_CLIENT_SECRET"),
    "redirect_uri": "https://cprime.moveworks.com/auth/oauthCallback",
})

print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    t = resp.json()
    with open("token.json", "w") as f:
        json.dump(t, f, indent=2)
    print("\n=== SUCCESS! Token saved to token.json ===")
    for k, v in t.items():
        print(f"  {k}: {str(v)[:60]}")
    
    # Step 4: Test REST API immediately
    rest_base = t.get("rest_service_authority", os.getenv("PROJECTOR_BASE_URL"))
    token = t["access_token"]
    print(f"\n=== Testing REST API at {rest_base} ===")
    for ep in ["/api/v1/projects", "/api/v1/resources"]:
        try:
            r = requests.get(f"{rest_base}{ep}", 
                           headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                           timeout=15, allow_redirects=False)
            print(f"  {ep} => {r.status_code} | {r.text[:150]}")
        except Exception as e:
            print(f"  {ep} => ERROR: {e}")
else:
    print(f"FAILED: {resp.text[:300]}")
