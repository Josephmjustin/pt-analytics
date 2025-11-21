import requests
import json
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

APP_KEY = os.getenv("TFL_APP_KEY")
BASE_URL = "https://api.tfl.gov.uk"

# Test 1: Get all bus lines
print("Testing TfL API access...")
url = f"{BASE_URL}/Line/Mode/bus"
response = requests.get(url, params={"app_key": APP_KEY})

print(f"Status Code: {response.status_code}")
print(f"Total bus lines: {len(response.json())}")
print("\nFirst 3 lines:")
for line in response.json()[:3]:
    print(f"  - {line['id']}: {line['name']}")

# Test 2: Get vehicle positions for a specific line
print("\n" + "="*50)
print("Testing vehicle position data...")

line_id = "12"  # Route 12
url = f"{BASE_URL}/Line/{line_id}/Arrivals"
response = requests.get(url, params={"app_key": APP_KEY})

print(f"Status Code: {response.status_code}")
print(f"Active vehicles on line {line_id}: {len(response.json())}")

# Save full response to inspect
with open("scripts/sample_arrivals.json", "w") as f:
    json.dump(response.json(), f, indent=2)

# Print first vehicle's data structure
if response.json():
    print("\nFirst vehicle data keys:")
    print(json.dumps(list(response.json()[0].keys()), indent=2))
    
print("\nSaved full response to: scripts/sample_arrivals.json")