import os
import time
import httpx
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# --- Generic LLM Wrapper with Retries, Timeouts, Metrics -----------------


async def call_llm(
    prompt: str,
    provider: str = "openai",
    api_key: Optional[str] = None,
    max_retries: int = 2,
    timeout: float = 20.0,
) -> Dict[str, Any]:
    """
    Call an LLM provider with timeout, retries and graceful failure.
    Always returns a dict, never raises on network failure.
    """
    start = time.time()
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            if provider == "openai":
                result = await call_openai(prompt, api_key, timeout=timeout)
            elif provider == "perplexity":
                result = await call_perplexity(prompt, api_key, timeout=timeout)
            elif provider == "gemini":
                result = await call_gemini(prompt, api_key, timeout=timeout)
            else:
                return {
                    "error": f"Unsupported provider: {provider}",
                    "latency": 0.0,
                    "tokens": 0,
                }

            latency = round(time.time() - start, 3)
            result["latency"] = latency
            return result

        except httpx.HTTPStatusError as e:
            last_error = str(e)
            # Retry only on 5xx server failures
            if e.response.status_code < 500 or e.response.status_code >= 600:
                break

        except Exception as e:
            last_error = str(e)

    return {
        "error": f"LLM request failed after retries: {last_error}",
        "latency": round(time.time() - start, 3),
        "tokens": 0,
    }


# --- Provider Level Calls ------------------------------------------------


async def call_openai(prompt: str, api_key: str | None, timeout: float):
    headers = {"Authorization": f"Bearer {api_key or os.getenv('OPENAI_API_KEY')}"}
    body = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]}

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions", headers=headers, json=body
        )
        r.raise_for_status()
        data = r.json()
        return {
            "message": data["choices"][0]["message"]["content"],
            "tokens": data.get("usage", {}).get("total_tokens", 0),
        }


async def call_perplexity(prompt: str, api_key: str | None, timeout: float):
    headers = {"Authorization": f"Bearer {api_key or os.getenv('PERPLEXITY_API_KEY')}"}
    body = {
        "model": "mistral-7b-instruct",
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            "https://api.perplexity.ai/chat/completions", headers=headers, json=body
        )
        r.raise_for_status()
        data = r.json()
        return {
            "message": data["choices"][0]["message"]["content"],
            "tokens": data.get("usage", {}).get("total_tokens", 0),
        }


async def call_gemini(prompt: str, api_key: str | None, timeout: float):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        f"?key={api_key or os.getenv('GEMINI_API_KEY')}"
    )
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=body)
        r.raise_for_status()
        data = r.json()
        return {
            "message": data["candidates"][0]["content"]["parts"][0]["text"],
            "tokens": data.get("usageMetadata", {}).get("totalTokenCount", 0),
        }
