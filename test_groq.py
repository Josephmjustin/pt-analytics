import requests

GROQ_API_KEY = "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"

response = requests.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "user", "content": "Say hello in one word"}
        ],
        "max_tokens": 10
    }
)

print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
