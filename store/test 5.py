import requests
BASE = 'http://localhost/api/products/'
HEADERS = {'Authorization': 'Token 6c8cfb7a391a6a24ed9241ef5c481675a64ad3d5'}
for i in range(20):
    r = requests.get(BASE, headers=HEADERS)
    print(f"Request {i+1}: {r.status_code} served by port {r.headers.get('X-Server-Port')}")
    if r.status_code != 200:
        print(r.text[:300])