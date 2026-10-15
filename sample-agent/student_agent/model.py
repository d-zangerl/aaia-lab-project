"""Local Ollama chat adapter."""

import json
from urllib import request


class OllamaModel:
    """Callable adapter for Ollama's local chat endpoint."""

    def __init__(self, model_name, endpoint="http://127.0.0.1:11434/api/chat"):
        self.model_name = model_name
        self.endpoint = endpoint

    def __call__(self, messages):
        """Return the model's message content as a JSON string."""
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "format": "json",
            "temperature": 0,
            "num_predict": 2048,
        }

        req = request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=90) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - surfaced as model error
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        if "message" in data and isinstance(data["message"], dict):
            return data["message"]["content"]
        if "content" in data:
            return data["content"]
        if "error" in data:
            raise RuntimeError(f"Ollama reported an error: {data['error']}")
        raise ValueError(f"Unexpected Ollama response shape: {data!r}")
