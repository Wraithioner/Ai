"""LLM brain - runs a language model directly in Python. No external servers needed."""

import gc
import json
import logging
import re
import time
from collections import OrderedDict
from pathlib import Path

import torch
from atlas.core.config import MODEL_CACHE_DIR, MODELS_DIR

logger = logging.getLogger(__name__)


class Brain:
    """Loads and runs a local LLM using transformers.

    Supports multi-user conversations (each Telegram user gets their own history).
    Uses an LRU cache to evict the oldest users when max_users is reached.
    Runs GC after inference to keep Railway memory stable.
    """

    def __init__(self, config: dict):
        llm_cfg = config["llm"]
        self.model_name = llm_cfg["model"]
        self.system_prompt = llm_cfg.get("system_prompt", "You are a helpful AI assistant.").strip()
        self.max_tokens = llm_cfg.get("max_tokens", 256)
        self.temperature = llm_cfg.get("temperature", 0.7)
        self.max_context = llm_cfg.get("context_window", 10)
        self.max_users = config.get("telegram", {}).get("max_users", 100)

        # Per-user conversation histories (LRU eviction)
        self._conversations: OrderedDict[int, list[dict]] = OrderedDict()

        self.model = None
        self.tokenizer = None
        self.device = None

    def _find_local_model(self) -> Path | None:
        """Check if a fine-tuned model exists in the models/ directory."""
        finetuned_dir = MODELS_DIR / "atlas-brain"
        if finetuned_dir.exists() and (finetuned_dir / "config.json").exists():
            return finetuned_dir
        return None

    def initialize(self):
        """Download (if needed) and load the model into memory."""
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if torch.cuda.is_available():
            self.device = "cuda"
            dtype = torch.float16
            device_map = "auto"
            logger.info("CUDA GPU detected — using float16.")
        else:
            self.device = "cpu"
            dtype = torch.float32
            device_map = "cpu"
            logger.info("No GPU — running on CPU with float32.")

        local_model = self._find_local_model()

        if local_model:
            model_source = str(local_model)
            cache_dir = None
            logger.info("Loading fine-tuned model from %s", local_model)
        else:
            model_source = self.model_name
            cache_dir = str(MODEL_CACHE_DIR / self.model_name.replace("/", "--"))
            logger.info("Loading model '%s'...", self.model_name)

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_source, cache_dir=cache_dir, trust_remote_code=False,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_source, cache_dir=cache_dir,
            torch_dtype=dtype, device_map=device_map,
            trust_remote_code=False,
        )
        self.model.eval()
        logger.info("Model loaded on %s.", self.device)

        # Free any leftover allocation from model loading
        gc.collect()
        if self.device == "cuda":
            torch.cuda.empty_cache()

    def _get_conversation(self, user_id: int) -> list[dict]:
        """Get or create conversation history for a user (LRU order)."""
        if user_id in self._conversations:
            self._conversations.move_to_end(user_id)
            return self._conversations[user_id]

        # Evict oldest user if at capacity
        if len(self._conversations) >= self.max_users:
            evicted_id, _ = self._conversations.popitem(last=False)
            logger.debug("Evicted conversation for user %d (at capacity %d)", evicted_id, self.max_users)

        self._conversations[user_id] = []
        return self._conversations[user_id]

    def _build_messages(self, user_id: int) -> list[dict]:
        """Build the message list with system prompt and trimmed history."""
        messages = [{"role": "system", "content": self.system_prompt}]
        conversation = self._get_conversation(user_id)
        trimmed = conversation[-(self.max_context * 2):]
        messages.extend(trimmed)
        return messages

    def _generate(self, messages: list[dict], max_new_tokens: int | None = None) -> str:
        """Run inference on a list of chat messages."""
        max_new_tokens = max_new_tokens or self.max_tokens

        inputs = self.tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        )

        if self.device == "cuda":
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

        input_len = inputs["input_ids"].shape[1]

        use_sampling = self.temperature > 0
        gen_kwargs = dict(
            **inputs,
            max_new_tokens=max_new_tokens,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        if use_sampling:
            gen_kwargs.update(temperature=self.temperature, do_sample=True, top_p=0.9)

        with torch.no_grad():
            outputs = self.model.generate(**gen_kwargs)

        new_tokens = outputs[0][input_len:]
        reply = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        # Free intermediate tensors
        del inputs, outputs
        gc.collect()

        return reply

    def think(self, user_text: str, user_id: int = 0) -> str:
        """Send user text to the LLM and get a response.

        Args:
            user_text: The user's message.
            user_id: Telegram user ID for per-user conversation tracking.
        """
        conversation = self._get_conversation(user_id)
        conversation.append({"role": "user", "content": user_text})

        # Trim history
        max_entries = self.max_context * 2
        if len(conversation) > max_entries:
            del conversation[:len(conversation) - max_entries]

        messages = self._build_messages(user_id)

        try:
            reply = self._generate(messages)
            if not reply:
                reply = "I'm not sure how to respond to that."
        except Exception as e:
            reply = "Something went wrong while thinking."
            logger.error("Inference error: %s", e)

        conversation.append({"role": "assistant", "content": reply})
        return reply

    def reset_conversation(self, user_id: int = 0):
        """Clear conversation history for a user."""
        self._conversations.pop(user_id, None)
        logger.info("Conversation cleared for user %d.", user_id)

    def active_users(self) -> int:
        """Return the number of users with active conversations."""
        return len(self._conversations)
