"""LLM brain - runs a language model directly in Python. No external servers needed."""

import logging
from pathlib import Path

from atlas.core.config import MODEL_CACHE_DIR, MODELS_DIR

logger = logging.getLogger(__name__)


class Brain:
    """Loads and runs a local LLM directly using transformers. No Ollama needed.

    Supports loading a fine-tuned model from models/ if one exists,
    otherwise downloads the base model from HuggingFace.
    """

    def __init__(self, config: dict):
        llm_cfg = config["llm"]
        self.model_name = llm_cfg["model"]
        self.system_prompt = llm_cfg["system_prompt"].strip()
        self.max_tokens = llm_cfg.get("max_tokens", 256)
        self.temperature = llm_cfg.get("temperature", 0.7)
        self.max_context = llm_cfg.get("context_window", 10)
        self.conversation: list[dict] = []
        self.model = None
        self.tokenizer = None

    def _find_local_model(self) -> Path | None:
        """Check if a fine-tuned model exists in the models/ directory."""
        finetuned_dir = MODELS_DIR / "atlas-brain"
        if finetuned_dir.exists() and (finetuned_dir / "config.json").exists():
            return finetuned_dir
        return None

    def initialize(self):
        """Download (if needed) and load the model into memory."""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        # Check for a local fine-tuned model first
        local_model = self._find_local_model()

        if local_model:
            model_source = str(local_model)
            cache_dir = None
            logger.info("Loading YOUR fine-tuned Atlas brain from %s", local_model)
        else:
            model_source = self.model_name
            cache_dir = str(MODEL_CACHE_DIR / self.model_name.replace("/", "--"))
            logger.info("Loading base model '%s'...", self.model_name)
            logger.info("This may download the model on first run (~1-3GB).")

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_source,
                cache_dir=cache_dir,
                trust_remote_code=False,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                model_source,
                cache_dir=cache_dir,
                torch_dtype=torch.float32,
                device_map="cpu",
                trust_remote_code=False,
            )
            self.model.eval()

            if local_model:
                logger.info("Atlas brain loaded (fine-tuned).")
            else:
                logger.info("Base model '%s' loaded and ready.", self.model_name)
        except Exception as e:
            logger.error("Failed to load model: %s", e)
            raise

    def _build_messages(self) -> list[dict]:
        """Build the message list with system prompt and conversation history."""
        messages = [{"role": "system", "content": self.system_prompt}]
        trimmed = self.conversation[-(self.max_context * 2):]
        messages.extend(trimmed)
        return messages

    def think(self, user_text: str) -> str:
        """Send user text to the LLM and get a response."""
        import torch

        self.conversation.append({"role": "user", "content": user_text})
        messages = self._build_messages()

        try:
            input_text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = self.tokenizer(input_text, return_tensors="pt")
            input_len = inputs["input_ids"].shape[1]

            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=self.max_tokens,
                    temperature=self.temperature,
                    do_sample=True,
                    top_p=0.9,
                    pad_token_id=self.tokenizer.eos_token_id,
                )

            new_tokens = outputs[0][input_len:]
            reply = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

            if not reply:
                reply = "I'm not sure how to respond to that."

        except Exception as e:
            reply = "Something went wrong while thinking."
            logger.error("Model inference error: %s", e)

        self.conversation.append({"role": "assistant", "content": reply})
        return reply

    def reset_conversation(self):
        """Clear conversation history."""
        self.conversation.clear()
        logger.info("Conversation history cleared.")
