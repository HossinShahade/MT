from locust import HttpUser, task, between

class EcommerceUser(HttpUser):
    wait_time = between(0.5, 2)
    token = None

    def on_start(self):
        """Called once per simulated user — gets auth token"""
        response = self.client.post("/api_token_auth/", json={
            "username": "loadtest",
            "password": "loadtest123"
        })
        if response.status_code == 200:
            self.token = response.json().get("token")
            self.client.headers.update({
                "Authorization": f"Token {self.token}"
            })
        else:
            print(f"[ERROR] Auth failed: {response.text}")

    @task(4)
    def browse_products(self):
        """Simulates product browsing — hits the cached endpoint"""
        self.client.get("/api/products/")

    @task(1)
    def place_order(self):
        """Simulates placing an order — hits the DB with locking"""
        self.client.post("/api/order/", json={
            "product_id": 1,
            "quantity": 1
        })