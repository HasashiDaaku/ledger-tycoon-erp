import urllib.request
import json

base_url = "http://localhost:8000"

def test_logs():
    # Start game
    req_start = urllib.request.Request(f"{base_url}/game/start", method="POST")
    urllib.request.urlopen(req_start)
    
    # Process turn
    print("Processing turn...")
    req_turn = urllib.request.Request(f"{base_url}/game/turn", method="POST")
    with urllib.request.urlopen(req_turn) as response:
        data = json.loads(response.read().decode())
    
    logs = data.get("logs", [])
    
    summary_found = False
    content_str = "\n".join(logs)
    
    if "📊 MONTHLY ANALYTICAL SUMMARY" in content_str:
        print("✅ Found summary block!")
        
        # Check for non-zero values
        # Example check: "Avg Price: $0.00" should NOT be present if market is active
        if "Avg Price: $0.00" not in content_str:
             print("🏆 SUCCESS: Non-zero values confirmed in analytical summary!")
             
             # Show the summary for manual inspection in the output
             idx = content_str.find("📊 MONTHLY ANALYTICAL SUMMARY")
             print("\n--- SUMMARY OUTPUT ---")
             print(content_str[idx:])
             print("----------------------")
        else:
            print("❌ FAILURE: Summary still contains zero values (Avg Price: $0.00)")
    else:
        print("❌ SUMMARY BLOCK NOT FOUND")

if __name__ == "__main__":
    test_logs()
