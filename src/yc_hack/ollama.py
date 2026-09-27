"""Minimal standard-library client for a local Ollama chat model."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class OllamaClient:
    def __init__(self, url: str | None = None, model: str | None = None):
        self.url = (url or os.environ.get("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.2")

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=2):
                return True
        except OSError:
            return False

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        request_body = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            request_body["format"] = "json"
        body = json.dumps({
            **request_body,
        }).encode()
        request = urllib.request.Request(
            f"{self.url}/api/chat", data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.loads(response.read())
        return str(result["message"]["content"])

    def with_model(self, model: str | None) -> "OllamaClient":
        return OllamaClient(self.url, model or self.model)

    def models(self) -> list[str]:
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=3) as response:
                payload = json.loads(response.read())
            return [str(item.get("name")) for item in payload.get("models", []) if item.get("name")]
        except (OSError, json.JSONDecodeError, AttributeError):
            return []
