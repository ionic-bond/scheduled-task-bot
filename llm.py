import requests

SYSTEM_PROMPT = """You are an information monitoring assistant. Your job is to check for specific information as instructed by the user.

Response rules:
- If you find valuable, new, or noteworthy information, provide a clear and concise report.
- If there is NOTHING valuable or new to report, start your response with EXACTLY: [NO_UPDATE]
  Then on a new line, briefly explain what you found (or didn't find) and why it's not noteworthy.
- Do not fabricate information. Only report what you genuinely know or can determine.
- Be concise but informative in your reports."""

NO_UPDATE_TOKEN = "[NO_UPDATE]"


DEDUP_PROMPT = "\n\n[IMPORTANT: The following are your previous reports for this task. Do NOT repeat any information already covered. Only report NEW information not mentioned before.]"


def query(base_url, api_key, model, instruction, history=None):
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.append({"role": "user", "content": instruction})
        for past_response in history:
            messages.append({"role": "assistant", "content": past_response})
            messages.append({"role": "user", "content": instruction + DEDUP_PROMPT})
    else:
        messages.append({"role": "user", "content": instruction})
    payload = {
        "model": model,
        "messages": messages
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
