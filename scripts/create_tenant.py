import urllib.request
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

url = "http://localhost:8001/admin/tenants"
payload = {
    "name": "Obeikan Investment Group",
    "slug": "obeikan",
    "config": {
        "persona_name": "Aria",
        "persona_description": "A technical support specialist for Obeikan factory operations, expert in machine fault codes.",
        "channels": ["chat", "voice"]
    }
}

req = urllib.request.Request(
    url, 
    data=json.dumps(payload).encode('utf-8'),
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    response = urllib.request.urlopen(req)
    print(" Successfully created Obeikan tenant!")
    print(response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print(f" HTTP Error: {e.code} - {e.read().decode('utf-8')}")
except Exception as e:
    print(f" Error: {e}")
