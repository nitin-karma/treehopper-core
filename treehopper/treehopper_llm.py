# treehopper/treehopper_llm.py
import os
import httpx
from dotenv import load_dotenv
from typing import Optional

load_dotenv()


async def call_llm(
    prompt: str, provider: str = "openai", api_key: Optional[str] = None
):
    provider = provider.lower()
    if provider == "openai":
        return await call_openai(prompt, api_key)
    if provider == "perplexity":
        return await call_perplexity(prompt, api_key)
    if provider == "gemini":
        return await call_gemini(prompt, api_key)
    return f"Unsupported provider: {provider}"


async def call_openai(prompt, api_key):
    headers = {"Authorization": f"Bearer {api_key or os.getenv('OPENAI_API_KEY')}"}
    json_data = {"model": "gpt-4", "messages": [{"role": "user", "content": prompt}]}
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=json_data,
        )
        return r.json()["choices"][0]["message"]["content"]


async def call_perplexity(prompt, api_key):
    headers = {"Authorization": f"Bearer {api_key or os.getenv('PERPLEXITY_API_KEY')}"}
    json_data = {
        "model": "mistral-7b-instruct",
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=json_data,
        )
        return r.json()["choices"][0]["message"]["content"]


async def call_gemini(prompt, api_key):
    headers = {"Content-Type": "application/json"}
    json_data = {"contents": [{"parts": [{"text": prompt}]}]}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/\
    gemini-pro:generateContent?key={api_key or os.getenv('GEMINI_API_KEY')}"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=headers, json=json_data)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
