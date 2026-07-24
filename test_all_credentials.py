import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from elevateiq_app import create_app

def test_credentials():
    app = create_app()
    client = app.test_client()

    credentials_to_test = [
        ("System Admin", "testadmin@elevateiq.com", "Password123!"),
        ("System Admin Alt", "admin@elevateiq.com", "Password123!"),
        ("Team Leader (Email)", "demo.tl@elevateiq.com", "Password123!"),
        ("Team Leader (Emp ID)", "ELVIQ_TL01", "Password123!"),
        ("Employee (Email)", "demo.employee@elevateiq.com", "Password123!"),
        ("Employee (Emp ID)", "ELVIQ_EMP01", "Password123!"),
        ("Client (Email)", "demo.client@elevateiq.com", "Password123!"),
        ("Client (Client ID)", "CLT_DEMO01", "Password123!"),
        ("HR Specialist (Email)", "demo.hr@elevateiq.com", "Password123!"),
        ("HR Specialist (Emp ID)", "ELVIQ_HR01", "Password123!"),
        ("Student / Candidate", "demo.student@elevateiq.com", "Password123!"),
    ]

    print("\n============================================================")
    print("      Testing All Role Demo Credentials via /login API      ")
    print("============================================================\n")

    all_passed = True
    for label, login_id, password in credentials_to_test:
        response = client.post("/login", json={
            "email": login_id,
            "password": password
        })
        
        status = response.status_code
        data = response.get_json() or {}
        
        if status == 200 and "token" in data:
            role = data.get("user", {}).get("role", "N/A")
            name = data.get("user", {}).get("name", "N/A")
            print(f"[PASSED] | {label:<22} | Status 200 | User: {name:<20} | Role: {role}")
        else:
            all_passed = False
            error = data.get("error", "Unknown error")
            print(f"[FAILED] | {label:<22} | Status {status} | Error: {error}")

    print("\n============================================================")
    if all_passed:
        print("ALL ROLE CREDENTIALS ARE WORKING 100% PERFECTLY!")
    else:
        print("SOME CREDENTIALS FAILED - SEE DETAILS ABOVE.")
    print("============================================================\n")

if __name__ == "__main__":
    test_credentials()
