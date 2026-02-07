"""LLM brain - connects to Ollama for local inference."""

import logging
import requests

logger = logging.getLogger(__name__)


class Brain:
    """Manages conversation with a local LLM via Ollama."""

    def __init__(self, config: dict):
        llm_cfg = config["llm"]
        self.model = llm_cfg["model"]
        self.host = llm_cfg["ollama_host"]
        self.system_prompt = llm_cfg["system_prompt"].strip()
        self.max_tokens = llm_cfg.get("max_tokens", 512)
        self.temperature = llm_cfg.get("temperature", 0.7)
        self.max_context = llm_cfg.get("context_window", 20)
        self.conversation: list[dict] = []

    def _build_messages(self) -> list[dict]:
        """Build the message list with system prompt and conversation history."""
        messages = [{"role": "system", "content": self.system_prompt}]
        # Keep only the last N exchanges to avoid context overflow
        trimmed = self.conversation[-(self.max_context * 2):]
        messages.extend(trimmed)
        return messages

    def think(self, user_text: str) -> str:
        """Send user text to the LLM and get a response."""
        self.conversation.append({"role": "user", "content": user_text})

        messages = self._build_messages()
        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": self.max_tokens,
                "temperature": self.temperature,
            },
        }

        try:
            logger.debug("Sending request to Ollama: %s", self.model)
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            reply = data["message"]["content"].strip()
        except requests.ConnectionError:
            reply = (
                "I can't reach Ollama. Make sure it's running with: ollama serve"
            )
            logger.error("Ollama connection failed at %s", self.host)
        except requests.Timeout:
            reply = "The model is taking too long to respond. Try a smaller model."
            logger.error("Ollama request timed out")
        except Exception as e:
            reply = "Something went wrong with the AI model."
            logger.error("Ollama error: %s", e)

        self.conversation.append({"role": "assistant", "content": reply})
        return reply

    def check_connection(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            # Check if our model (or base name) is available
            base_model = self.model.split(":")[0]
            available = any(base_model in m for m in models)
            if not available:
                logger.warning(
                    "Model '%s' not found. Available: %s. "
                    "Run: ollama pull %s",
                    self.model, models, self.model,
                )
                return False
            logger.info("Connected to Ollama. Model '%s' ready.", self.model)
            return True
        except Exception as e:
            logger.error("Cannot reach Ollama: %s", e)
            return False

    def reset_conversation(self):
        """Clear conversation history."""
        self.conversation.clear()
        logger.info("Conversation history cleared.")
