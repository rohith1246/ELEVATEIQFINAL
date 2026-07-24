import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app import create_app

app = create_app()

def test_flask_login():
    with app.test_client() as client:
        payload = {
            "email": "admin@elevateiq.com",
            "password": "Password123!",
            "portal": "elevateiq"
        }
        res = client.post("/login", data=json.dumps(payload), content_type="application/json")
        print("Status Code:", res.status_code)
        print("Response Data:", res.get_data(as_text=True))

if __name__ == "__main__":
    test_flask_login()
