import requests, json, os
from dotenv import load_dotenv
load_dotenv()

TOKEN_URL = os.getenv("PROJECTOR_TOKEN_URL")
CLIENT_ID = os.getenv("PROJECTOR_CLIENT_ID")
CLIENT_SECRET = os.getenv("PROJECTOR_CLIENT_SECRET")
REDIRECT_URI = "https://cprime.moveworks.com/auth/oauthCallback"

print("Paste the FULL callback URL from browser (the one with ?code=...):")
print("Then press Enter immediately!")
url_input = input("> ").strip()

# Extract code from URL
if "code=" in url_input:
    AUTH_CODE = url_input.split("code=")[1].split("&")[0]
else:
    AUTH_CODE = url_input  # assume they pasted just the code

print(f"Code: {AUTH_CODE[:20]}...")
print("Exchanging NOW...")
resp = requests.post(TOKEN_URL, data={
    "grant_type": "code",
    "code": AUTH_CODE,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
})

print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:500]}")

if resp.status_code == 200:
    token = resp.json()
    with open("token.json", "w") as f:
        json.dump(token, f, indent=2)
    print("\nSUCCESS! Token saved to token.json")
    for k in token:
        v = str(token[k])[:50]
        print(f"  {k}: {v}")
