import requests
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("BODS_API_KEY")

url = f"https://data.bus-data.dft.gov.uk/api/v1/dataset/?api_key={api_key}&limit=5"

response = requests.get(url)

print(f"Status Code: {response.status_code}")
print(f"Content-Type: {response.headers.get('Content-Type')}")
print(response.json())