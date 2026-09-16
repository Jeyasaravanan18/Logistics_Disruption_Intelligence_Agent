import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

MODELS_TO_TRY = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.5-flash-lite"]

async def generate_gemini_json(prompt: str, system_instruction: str = "") -> dict | None:
    """
    Call Google Gemini API with native JSON output.
    Attempts gemini-1.5-flash then gemini-2.0-flash with structured JSON response.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip(' "\'')
    if not api_key or api_key == "your_gemini_api_key_here":
        return None

    full_prompt = f"System Instruction: {system_instruction}\n\n{prompt}" if system_instruction else prompt
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.2
        }
    }

    for model in MODELS_TO_TRY[:2]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(text)
                elif resp.status_code == 429:
                    print(f"[GeminiService] Quota exceeded (429) on {model}. Fast-falling back to expert rules.", flush=True)
                    break
                elif resp.status_code in (403, 404, 503):
                    print(f"[GeminiService] Model {model} returned {resp.status_code}. Fast-falling back.", flush=True)
                    continue
                else:
                    print(f"[GeminiService] API Error on {model} ({resp.status_code}).", flush=True)
                    break
        except Exception as e:
            print(f"[GeminiService] Call to {model} failed ({e}).", flush=True)
            break

    return None

