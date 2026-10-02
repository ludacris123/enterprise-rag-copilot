import json
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from .config import get_settings


class ProviderError(Exception):
    pass


def config(provider):
    cfg = get_settings()
    if provider == "groq":
        return "https://api.groq.com/openai/v1", cfg.groq_api_key, cfg.groq_model
    if provider == "openai":
        return "https://api.openai.com/v1", cfg.openai_api_key, cfg.openai_model
    if provider == "local" and cfg.enable_local_model:
        return cfg.local_model_url.rstrip("/"), "local", cfg.local_model_name
    raise ProviderError("Provider is not enabled")


def retryable(exc):
    return isinstance(exc, httpx.TransportError) or (isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 500, 502, 503, 504))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=4), retry=retry_if_exception(retryable), reraise=True)
def completion(provider, system, prompt, json_mode=False):
    base, key, model = config(provider)
    if not key:
        raise ProviderError(f"{provider.upper()}_API_KEY is not configured")
    payload = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
               "temperature": 0, "max_tokens": 1200}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    with httpx.Client(timeout=httpx.Timeout(45, connect=5)) as client:
        response = client.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=payload)
        response.raise_for_status()
        data = response.json()
    text = data["choices"][0]["message"]["content"]
    return {"text": text, "model": model, "input_tokens": data.get("usage", {}).get("prompt_tokens", 0),
            "output_tokens": data.get("usage", {}).get("completion_tokens", 0)}


def capabilities():
    cfg = get_settings()
    return [{"id": "offline", "label": "Offline · extractive", "enabled": True},
            {"id": "groq", "label": f"Groq · {cfg.groq_model}", "enabled": bool(cfg.groq_api_key)},
            {"id": "openai", "label": f"OpenAI · {cfg.openai_model}", "enabled": bool(cfg.openai_api_key)},
            {"id": "local", "label": f"Local · {cfg.local_model_name}", "enabled": cfg.enable_local_model}]
