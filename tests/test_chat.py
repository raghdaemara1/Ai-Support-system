import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import urllib.request
import json

url = 'http://localhost:8001/chat/message'
payload = {
    'tenant_id': 'demo-tenant',
    'customer_id': 'test',
    'message': 'whats alaram code 2008'
}
req = urllib.request.Request(
    url, 
    data=json.dumps(payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    response = urllib.request.urlopen(req)
    print(response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print(f'HTTP Error {e.code}: {e.read().decode("utf-8")}')
