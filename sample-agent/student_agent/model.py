"""Local Ollama chat adapter."""


class OllamaModel:
    """Callable adapter for Ollama's local chat endpoint."""

    def __init__(self, model_name, endpoint="http://127.0.0.1:11434/api/chat"):
        self.model_name = model_name
        self.endpoint = endpoint

    def __call__(self, messages):
        """Return the model's message content as a JSON string."""
        import requests

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "format": "json",
            "temperature": 0,
            "num_predict": 2048,
        }
        response = requests.post(self.endpoint, json=payload, timeout=90)
        response.raise_for_status()
        data = response.json()

        if "message" in data and isinstance(data["message"], dict):
            return data["message"]["content"]
        if "content" in data:
            return data["content"]
        raise ValueError(f"Unexpected Ollama response shape: {data!r}")
