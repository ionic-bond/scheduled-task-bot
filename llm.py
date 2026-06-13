import requests

_key_index = 0

def _get_next_key(api_keys_str):
    global _key_index
    keys = [k.strip() for k in api_keys_str.split(',')]
    keys = [k for k in keys if k]
    if not keys:
        return ""
    key = keys[_key_index % len(keys)]
    _key_index += 1
    return key

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
    api_key = _get_next_key(api_key)
    if api_key.startswith("AIza") and "openai" not in base_url.lower():
        gemini_base = base_url.rstrip('/')
        if not gemini_base.endswith("/v1beta"):
            gemini_base += "/v1beta"
        url = f"{gemini_base}/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        contents = []
        if history:
            contents.append({"role": "user", "parts": [{"text": instruction}]})
            for past_response in history:
                contents.append({"role": "model", "parts": [{"text": past_response}]})
                contents.append({"role": "user", "parts": [{"text": instruction + DEDUP_PROMPT}]})
        else:
            contents.append({"role": "user", "parts": [{"text": instruction}]})
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": contents,
            "tools": [{"google_search": {}}]
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

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
    api_key = _get_next_key(api_key)
    if api_key.startswith("AIza") and "openai" not in base_url.lower():
        gemini_base = base_url.rstrip('/')
        if not gemini_base.endswith("/v1beta"):
            gemini_base += "/v1beta"
        url = f"{gemini_base}/models?key={api_key}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return [m["name"].replace("models/", "") for m in resp.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]

    url = f"{base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return [m["id"] for m in resp.json()["data"]]
