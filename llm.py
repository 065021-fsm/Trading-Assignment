import argparse
import json
import os
from typing import Dict, List, Optional
from urllib import error, request

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv() -> bool:
        return False


load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"), override=False)


def _get(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    return value if value not in (None, "") else default


def get_llm_config() -> Dict[str, str]:
    api_key = _get("OLLAMA_API_KEY", "") or ""
    provider = (_get("LLM_PROVIDER") or ("ollama_cloud" if api_key else "ollama_local")).lower()
    docker_local_url = "http://localhost:11435"
    return {
        "provider": provider,
        "local_url": _get("OLLAMA_LOCAL_URL", docker_local_url) or docker_local_url,
        "cloud_url": _get("OLLAMA_CLOUD_URL", "https://ollama.com") or "https://ollama.com",
        "api_key": api_key,
        "model_fast": _get("LLM_MODEL_FAST") or "llama3.1:8b",
        "model_strong": _get("LLM_MODEL_STRONG") or "llama3.1:70b",
    }


def _call_ollama(url: str, model: str, prompt: str, api_key: str = "") -> Dict[str, object]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.1},
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    http_req = request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with request.urlopen(http_req, timeout=20) as resp:
        body = resp.read().decode("utf-8")
        data = json.loads(body)
        message = data.get("message", {}).get("content") or data.get("content") or str(data)
        return {"ok": True, "model": model, "response": message}


def test_local_ollama() -> Dict[str, object]:
    cfg = get_llm_config()
    try:
        result = _call_ollama(f"{cfg['local_url']}/api/chat", cfg["model_fast"], "Reply with OK")
        return {"provider": "ollama_local", "status": "ok", **result}
    except Exception as exc:  # pragma: no cover
        return {"provider": "ollama_local", "status": "failed", "error": str(exc)}


def test_cloud_ollama() -> Dict[str, object]:
    cfg = get_llm_config()
    if not cfg["api_key"]:
        return {"provider": "ollama_cloud", "status": "skipped", "error": "OLLAMA_API_KEY is not set"}
    try:
        model_name = cfg["model_strong"] if cfg.get("model_strong") else cfg["model_fast"]
        result = _call_ollama(f"{cfg['cloud_url']}/api/chat", model_name, "Reply with OK", cfg["api_key"])
        return {"provider": "ollama_cloud", "status": "ok", **result}
    except Exception as exc:  # pragma: no cover
        return {"provider": "ollama_cloud", "status": "failed", "error": str(exc)}


def call_llm_with_fallback(prompt: str, preferred_provider: Optional[str] = None) -> Dict[str, object]:
    cfg = get_llm_config()
    providers = []
    preferred = (preferred_provider or cfg.get("provider") or "ollama_local").lower()
    if preferred == "ollama_cloud":
        providers = ["ollama_cloud", "ollama_local"]
    elif preferred == "ollama_local":
        providers = ["ollama_local", "ollama_cloud"]
    else:
        providers = [preferred, "ollama_local"]

    last_error = None
    for provider_name in providers:
        try:
            if provider_name == "ollama_cloud":
                if not cfg["api_key"]:
                    continue
                model_name = cfg["model_strong"] if cfg.get("model_strong") else cfg["model_fast"]
                return _call_ollama(f"{cfg['cloud_url']}/api/chat", model_name, prompt, cfg["api_key"])
            model_name = cfg["model_fast"] if cfg.get("model_fast") else "llama3.1:8b"
            return _call_ollama(f"{cfg['local_url']}/api/chat", model_name, prompt)
        except Exception as exc:  # pragma: no cover
            last_error = exc
    raise last_error if last_error is not None else RuntimeError("LLM call failed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal LLM startup checks")
    parser.add_argument("--test", action="store_true", help="Run local and cloud startup checks")
    args = parser.parse_args()

    if not args.test:
        cfg = get_llm_config()
        print(json.dumps({"llm": cfg}, indent=2))
        return 0

    local = test_local_ollama()
    cloud = test_cloud_ollama()
    print(json.dumps({"local": local, "cloud": cloud}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
