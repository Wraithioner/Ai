"""LLM brain - runs a language model directly in Python. No external servers needed."""

import json
import logging
import re
from pathlib import Path

from atlas.core.config import MODEL_CACHE_DIR, MODELS_DIR

logger = logging.getLogger(__name__)

ACTION_PROMPT_TEMPLATE = """\
You are an AI controlling a computer. You can see the screen via OCR text.

CURRENT SCREEN TEXT:
{screen_text}

USER REQUEST: {user_request}

Respond with ONLY a JSON object (no other text) choosing one action:
{{"action": "click", "target": "exact text on screen to click", "reason": "why"}}
{{"action": "type", "value": "text to type", "reason": "why"}}
{{"action": "press", "value": "key name like enter/tab/escape", "reason": "why"}}
{{"action": "hotkey", "value": "ctrl+c or alt+tab etc", "reason": "why"}}
{{"action": "scroll", "value": "up or down", "reason": "why"}}
{{"action": "done", "reason": "task is complete because..."}}
{{"action": "fail", "reason": "cannot do this because..."}}

Rules:
- Pick the SINGLE best next action to make progress on the user's request.
- For "click", the target must be text you can see on screen.
- Only output the JSON object, nothing else."""


class Brain:
    """Loads and runs a local LLM directly using transformers. No Ollama needed.

    Supports loading a fine-tuned model from models/ if one exists,
    otherwise downloads the base model from HuggingFace.
    Auto-detects CUDA GPU and uses float16 acceleration when available.
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
        self.device = None

    def _find_local_model(self) -> Path | None:
        """Check if a fine-tuned model exists in the models/ directory."""
        finetuned_dir = MODELS_DIR / "atlas-brain"
        if finetuned_dir.exists() and (finetuned_dir / "config.json").exists():
            return finetuned_dir
        return None

    def initialize(self):
        """Download (if needed) and load the model into memory.

        Auto-detects CUDA and uses float16 on GPU for speed,
        falls back to float32 on CPU.
        """
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        # Auto-detect best device and dtype
        if torch.cuda.is_available():
            self.device = "cuda"
            dtype = torch.float16
            device_map = "auto"
            logger.info("CUDA GPU detected! Using float16 acceleration.")
        else:
            self.device = "cpu"
            dtype = torch.float32
            device_map = "cpu"
            logger.info("No GPU detected. Running on CPU with float32.")

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
            logger.info("This may download the model on first run.")

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_source,
                cache_dir=cache_dir,
                trust_remote_code=False,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                model_source,
                cache_dir=cache_dir,
                torch_dtype=dtype,
                device_map=device_map,
                trust_remote_code=False,
            )
            self.model.eval()

            if local_model:
                logger.info("Atlas brain loaded (fine-tuned) on %s.", self.device)
            else:
                logger.info(
                    "Model '%s' loaded on %s (%s).",
                    self.model_name, self.device, dtype,
                )
        except Exception as e:
            logger.error("Failed to load model: %s", e)
            raise

    def _build_messages(self) -> list[dict]:
        """Build the message list with system prompt and conversation history."""
        messages = [{"role": "system", "content": self.system_prompt}]
        trimmed = self.conversation[-(self.max_context * 2):]
        messages.extend(trimmed)
        return messages

    def _generate(self, messages: list[dict], max_new_tokens: int | None = None) -> str:
        """Run inference on a list of chat messages. Returns the raw reply text."""
        import torch

        max_new_tokens = max_new_tokens or self.max_tokens

        input_text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(input_text, return_tensors="pt")

        # Move inputs to the same device as the model
        if self.device == "cuda":
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

        input_len = inputs["input_ids"].shape[1]

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=self.temperature,
                do_sample=True,
                top_p=0.9,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        new_tokens = outputs[0][input_len:]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    def think(self, user_text: str) -> str:
        """Send user text to the LLM and get a conversational response."""
        self.conversation.append({"role": "user", "content": user_text})
        messages = self._build_messages()

        try:
            reply = self._generate(messages)
            if not reply:
                reply = "I'm not sure how to respond to that."
        except Exception as e:
            reply = "Something went wrong while thinking."
            logger.error("Model inference error: %s", e)

        self.conversation.append({"role": "assistant", "content": reply})
        return reply

    def plan_action(self, user_request: str, screen_text: str) -> dict:
        """Ask the LLM to decide the next computer action based on screen OCR.

        Returns a dict like:
            {"action": "click", "target": "File", "reason": "to open menu"}
            {"action": "type", "value": "hello", "reason": "user asked to type"}
            {"action": "done", "reason": "task complete"}
            {"action": "fail", "reason": "can't find the button"}
        """
        prompt = ACTION_PROMPT_TEMPLATE.format(
            screen_text=screen_text[:3000],  # Truncate to avoid token overflow
            user_request=user_request,
        )

        messages = [
            {"role": "system", "content": "You are a computer control assistant. Output only valid JSON."},
            {"role": "user", "content": prompt},
        ]

        try:
            raw = self._generate(messages, max_new_tokens=256)
            logger.debug("plan_action raw LLM output: %s", raw)

            # Extract JSON from the response (LLM might wrap it in markdown)
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                action = json.loads(json_match.group())
                # Validate required field
                if "action" not in action:
                    action = {"action": "fail", "reason": "LLM returned no action field"}
                return action
            else:
                logger.warning("No JSON found in LLM output: %s", raw[:200])
                return {"action": "fail", "reason": "Could not parse action from LLM response"}

        except json.JSONDecodeError as e:
            logger.error("JSON parse error in plan_action: %s", e)
            return {"action": "fail", "reason": f"Invalid JSON from LLM: {e}"}
        except Exception as e:
            logger.error("plan_action error: %s", e)
            return {"action": "fail", "reason": str(e)}

    def reset_conversation(self):
        """Clear conversation history."""
        self.conversation.clear()
        logger.info("Conversation history cleared.")
