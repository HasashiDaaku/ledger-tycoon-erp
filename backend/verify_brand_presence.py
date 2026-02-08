import requests
import time

API_URL = "http://localhost:8000"

def verify_brand_presence_logging():
    print("Restarting Game...")
    requests.post(f"{API_URL}/game/start")
    time.sleep(1)

    print("Setting Marketing Budget to 10%...")
    try:
        budget_res = requests.post(f"{API_URL}/game/player/marketing?budget_percent=0.10")
        if budget_res.status_code == 200:
            print("Budget set successfully.")
        else:
            print(f"Failed to set budget: {budget_res.status_code} - {budget_res.text}")
            return
    except Exception as e:
        print(f"Error setting budget: {e}")
        return

    print("Triggering a new turn...")
    try:
        response = requests.post(f"{API_URL}/game/turn")
        if response.status_code == 200:
            print("Turn processed successfully.")
            data = response.json()
            logs = data.get("logs", [])
            
            # Check for the Player Performance Report in the returned logs
            found_report = False
            found_brand_presence = False
            found_marketing_budget = False
            found_marketing_expense = False
            
            for line in logs:
                if "👤 PLAYER PERFORMANCE REPORT" in line:
                    found_report = True
                if "🌐 Brand Presence" in line and found_report:
                    found_brand_presence = True
                if "📢 PLAYER MARKETING CAMPAIGN:" in line:
                    found_marketing_budget = True
                    found_marketing_expense = True
                    print(f"Found Marketing Campaign Log: {line}")
            
            if found_report and found_brand_presence and found_marketing_budget and found_marketing_expense:
                print("SUCCESS: Player Performance Report, Brand Presence, Budget, and Expense found in logs.")
            else:
                print(f"FAILURE: Missing logs. Report:{found_report}, Brand:{found_brand_presence}, Budget:{found_marketing_budget}, Expense:{found_marketing_expense}")
                print("--- ALL LOGS ---")
                for line in logs:
                    print(line)
        else:
            print(f"Error processing turn: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    verify_brand_presence_logging()
