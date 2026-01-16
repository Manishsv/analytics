import json
import httpx
from typing import Any, Dict, List, Optional


class OllamaClient:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def chat_json(self, system: str, user: str, timeout_s: int = 90) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            # Ollama supports JSON mode with many models; if the model ignores it,
            # we still parse content as JSON and fail fast.
            "format": "json",
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
            content = data["message"]["content"]
            return json.loads(content)
