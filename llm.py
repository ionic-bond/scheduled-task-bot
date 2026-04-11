import requests

SYSTEM_PROMPT = """You are an information monitoring assistant. Your job is to check for specific information as instructed by the user.

Response rules:
- If you find valuable, new, or noteworthy information, provide a clear and concise report.
- If there is NOTHING valuable or new to report, start your response with EXACTLY: [NO_UPDATE]
  Then on a new line, briefly explain what you found (or didn't find) and why it's not noteworthy.
- Do not fabricate information. Only report what you genuinely know or can determine.
- Be concise but informative in your reports."""

NO_UPDATE_TOKEN = "[NO_UPDATE]"


def query(base_url, api_key, model, instruction):
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": instruction}
        ]
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def list_models(base_url, api_key):
    url = f"{base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return [m["id"] for m in resp.json()["data"]]
