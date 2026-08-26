import requests, json, os, sys
from dotenv import load_dotenv
load_dotenv()

code = sys.argv[1] if len(sys.argv) > 1 else input("Paste code: ").strip()
if "code=" in code:
    code = code.split("code=")[1].split("&")[0]

print(f"Code: {code[:25]}...")
resp = requests.post(os.getenv("PROJECTOR_TOKEN_URL"), data={
    "grant_type": "code",
    "code": code,
    "client_id": os.getenv("PROJECTOR_CLIENT_ID"),
    "client_secret": os.getenv("PROJECTOR_CLIENT_SECRET"),
    "redirect_uri": "https://cprime.moveworks.com/auth/oauthCallback",
})
print(f"Status: {resp.status_code}")
print(resp.text[:500])
if resp.status_code == 200:
    t = resp.json()
    with open("token.json","w") as f: json.dump(t, f, indent=2)
    print("\nSUCCESS!")
    for k,v in t.items(): print(f"  {k}: {str(v)[:60]}")
