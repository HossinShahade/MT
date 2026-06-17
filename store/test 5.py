import requests
BASE = 'http://localhost/api/products/'
HEADERS = {'Authorization': 'aa626615a97a33e9a52cc99a63b07e6b13206af1'}
for i in range(20):
    r = requests.get(BASE, headers=HEADERS)
    print(f"Request {i+1}: {r.status_code}")