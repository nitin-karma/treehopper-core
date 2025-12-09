# treehopper_llm.py
import os
import time
import httpx
import random
import asyncio
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from treehopper.logging import get_logger

logger = get_logger()

load_dotenv()

# =============================================================================
# TEST / MOCK CONFIG
# =============================================================================
IS_TEST = os.getenv("TH_TEST_MODE", "0") == "1"
LLM_PROVIDER_ENV = os.getenv("TH_LLM_PROVIDER", "openai").lower()

# =============================================================================
# GLOBAL RETRY SETTINGS (can be tuned via env in CI)
# =============================================================================
if IS_TEST:
    # fast retry mode for local/CI testing to avoid long exponential waits
    DEFAULT_MAX_RETRIES = int(os.getenv("TH_LLM_RETRIES", "1"))
    DEFAULT_TIMEOUT = float(os.getenv("TH_LLM_TIMEOUT", "10.0"))
    BACKOFF_BASE = float(os.getenv("TH_BACKOFF_BASE", "1.2"))
    BACKOFF_JITTER = float(os.getenv("TH_BACKOFF_JITTER", "0.1"))
else:
    DEFAULT_MAX_RETRIES = int(os.getenv("TH_LLM_RETRIES", "5"))
    DEFAULT_TIMEOUT = float(os.getenv("TH_LLM_TIMEOUT", "25.0"))
    BACKOFF_BASE = float(os.getenv("TH_BACKOFF_BASE", "2.0"))
    BACKOFF_JITTER = float(os.getenv("TH_BACKOFF_JITTER", "0.35"))

if IS_TEST:
    print("⚡ Treehopper LLM FAST RETRY MODE ENABLED (TH_TEST_MODE=1)")
if LLM_PROVIDER_ENV == "mock":
    print("⚡ Treehopper LLM MOCK PROVIDER ENABLED (TH_LLM_PROVIDER=mock)")

# =============================================================================
# MAIN ENTRY: call_llm (WRAPPER WITH RETRIES)
# =============================================================================


async def call_llm(
    prompt: str,
    provider: str | None = None,
    api_key: Optional[str] = None,
    max_retries: int | None = None,
    timeout: float | None = None,
) -> Dict[str, Any]:
    """
    Unified LLM wrapper with:
      - Timeout
      - Exponential backoff retry (configurable)
      - Jitter (random noise)
      - Clean response structure
      - Never raises exceptions (returns {"error": ...})

    Returns:
      { "message": "...", "tokens": N, "latency": secs }
      or
      { "error": msg, "latency": secs, "tokens": 0 }
    """
    provider = (provider or LLM_PROVIDER_ENV or "openai").lower()
    max_retries = max_retries if max_retries is not None else DEFAULT_MAX_RETRIES
    timeout = timeout if timeout is not None else DEFAULT_TIMEOUT

    start = time.time()
    last_error = None

    # Mock provider shortcut (instant return for tests / CI)
    if provider == "mock":
        await asyncio.sleep(0.05)
        return {
            "message": "[MOCK] quick response",
            "tokens": 0,
            "latency": round(time.time() - start, 3),
        }

    for attempt in range(1, max_retries + 2):
        try:
            # --------------------------------------------------------
            # SELECT PROVIDER
            # --------------------------------------------------------
            if provider == "openai":
                result = await call_openai(prompt, api_key, timeout)
            elif provider == "perplexity":
                result = await call_perplexity(prompt, api_key, timeout)
            elif provider == "gemini":
                result = await call_gemini(prompt, api_key, timeout)
            else:
                return {
                    "error": f"Unsupported provider: {provider}",
                    "latency": round(time.time() - start, 3),
                    "tokens": 0,
                }

            # --------------------------------------------------------
            # SUCCESS → RETURN
            # --------------------------------------------------------
            result["latency"] = round(time.time() - start, 3)
            return result

        except httpx.HTTPStatusError as e:
            status = e.response.status_code if e.response is not None else None
            # Retry on 429 or 5xx
            if status == 429 or (status is not None and 500 <= status <= 599):
                last_error = f"Status {status}: {str(e)}"
                wait = (BACKOFF_BASE**attempt) + random.uniform(0, BACKOFF_JITTER)
                # cap wait in test mode to keep fast
                if IS_TEST:
                    wait = min(wait, 3.0)
                print(
                    f"⚠️ LLM HTTP error ({status}). Retry {attempt}/{max_retries} after {wait:.2f}s"
                )
                await asyncio.sleep(wait)
                continue
            else:
                # Non-retryable
                last_error = f"Non-retryable HTTP error {status}: {str(e)}"
                break

        except httpx.TimeoutException as e:
            last_error = f"Timeout: {str(e)}"
            wait = (BACKOFF_BASE**attempt) + random.uniform(0, BACKOFF_JITTER)
            if IS_TEST:
                wait = min(wait, 3.0)
            print(f"⏳ LLM timeout. Retry {attempt}/{max_retries} after {wait:.2f}s")
            await asyncio.sleep(wait)
            continue

        except httpx.NetworkError as e:
            last_error = f"Network error: {str(e)}"
            wait = (BACKOFF_BASE**attempt) + random.uniform(0, BACKOFF_JITTER)
            if IS_TEST:
                wait = min(wait, 3.0)
            print(f"🌐 Network issue. Retry {attempt}/{max_retries} after {wait:.2f}s")
            await asyncio.sleep(wait)
            continue

        except Exception as e:
            # Unexpected / non-retryable
            last_error = str(e)
            break

    # All retries failed
    return {
        "error": f"LLM request failed after retries: {last_error}",
        "latency": round(time.time() - start, 3),
        "tokens": 0,
    }


# =============================================================================
# PROVIDER-SPECIFIC CALLS
# =============================================================================


async def call_openai(prompt: str, api_key: str | None, timeout: float):
    headers = {"Authorization": f"Bearer {api_key or os.getenv('OPENAI_API_KEY')}"}
    logger.info(headers)

    body = {
        "model": os.getenv("TH_OPENAI_MODEL", "gpt-4o-mini"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": float(os.getenv("TH_OPENAI_TEMPERATURE", "0.6")),
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "message": data["choices"][0]["message"]["content"],
            "tokens": data.get("usage", {}).get("total_tokens", 0),
        }


async def call_perplexity(prompt: str, api_key: str | None, timeout: float):
    headers = {"Authorization": f"Bearer {api_key or os.getenv('PERPLEXITY_API_KEY')}"}

    body = {
        "model": os.getenv("TH_PERPLEXITY_MODEL", "mistral-7b-instruct"),
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "message": data["choices"][0]["message"]["content"],
            "tokens": data.get("usage", {}).get("total_tokens", 0),
        }


async def call_gemini(prompt: str, api_key: str | None, timeout: float):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-pro:generateContent?key={api_key or os.getenv('GEMINI_API_KEY')}"
    )

    body = {"contents": [{"parts": [{"text": prompt}]}]}

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()

        return {
            "message": data["candidates"][0]["content"]["parts"][0]["text"],
            "tokens": data.get("usageMetadata", {}).get("totalTokenCount", 0),
        }
