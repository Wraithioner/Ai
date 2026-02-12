"""Fine-tune Atlas's brain with your own training data.

Usage:
    python -m atlas.main --train

This will:
1. Load the base model
2. Load your training data from data/training/
3. Fine-tune the model
4. Save the fine-tuned model to models/atlas-brain/

After training, Atlas will automatically use your fine-tuned brain.
"""

import json
import logging
from pathlib import Path

from atlas.core.config import (
    load_config,
    MODEL_CACHE_DIR,
    MODELS_DIR,
    TRAINING_DATA_DIR,
)

logger = logging.getLogger(__name__)


def load_training_data() -> list[dict]:
    """Load all .jsonl files from data/training/."""
    all_data = []

    if not TRAINING_DATA_DIR.exists():
        logger.error("Training data directory not found: %s", TRAINING_DATA_DIR)
        return all_data

    for jsonl_file in sorted(TRAINING_DATA_DIR.glob("*.jsonl")):
        count = 0
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    all_data.append(entry)
                    count += 1
                except json.JSONDecodeError as e:
                    logger.warning("Skipping bad line in %s: %s", jsonl_file.name, e)
        logger.info("Loaded %d examples from %s", count, jsonl_file.name)

    return all_data


def format_for_training(examples: list[dict], tokenizer) -> list[str]:
    """Convert message lists into formatted training strings."""
    formatted = []
    for example in examples:
        messages = example.get("messages", [])
        if not messages:
            continue
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )
        formatted.append(text)
    return formatted


def run_training(config_path: str | None = None):
    """Run the fine-tuning process."""
    import torch
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        TrainingArguments,
        Trainer,
        DataCollatorForLanguageModeling,
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_config(config_path)
    model_name = config["llm"]["model"]
    output_dir = MODELS_DIR / "atlas-brain"

    print("\n" + "=" * 50)
    print("  Atlas Brain Training")
    print("=" * 50)

    # Step 1: Load training data
    print("\n[1/4] Loading training data...")
    examples = load_training_data()
    if not examples:
        print("\nNo training data found!")
        print(f"Add .jsonl files to: {TRAINING_DATA_DIR}")
        print("See data/training/atlas_personality.jsonl for the format.")
        return

    print(f"  Found {len(examples)} training examples.")

    if len(examples) < 10:
        print(f"  Tip: More examples = better results. You have {len(examples)},")
        print("  consider adding more to data/training/.")

    # Step 2: Load base model
    print(f"\n[2/4] Loading base model '{model_name}'...")
    cache_dir = str(MODEL_CACHE_DIR / model_name.replace("/", "--"))

    tokenizer = AutoTokenizer.from_pretrained(
        model_name, cache_dir=cache_dir, trust_remote_code=False,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Use GPU with float16 if available for faster training
    if torch.cuda.is_available():
        dtype = torch.float16
        print("  Using CUDA GPU for training.")
    else:
        dtype = torch.float32
        print("  Using CPU for training (slower).")

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        cache_dir=cache_dir,
        torch_dtype=dtype,
        trust_remote_code=False,
    )
    print("  Model loaded.")

    # Step 3: Prepare dataset
    print("\n[3/4] Preparing training data...")
    formatted_texts = format_for_training(examples, tokenizer)

    # Tokenize each example individually (variable lengths are fine).
    # DataCollatorForLanguageModeling handles per-batch padding,
    # avoiding wasteful global padding to max_length.
    tokenized = []
    for text in formatted_texts:
        enc = tokenizer(text, truncation=True, max_length=512)
        tokenized.append(enc)

    class SimpleDataset(torch.utils.data.Dataset):
        def __init__(self, examples):
            self.examples = examples

        def __len__(self):
            return len(self.examples)

        def __getitem__(self, idx):
            item = self.examples[idx]
            input_ids = torch.tensor(item["input_ids"], dtype=torch.long)
            attention_mask = torch.tensor(item["attention_mask"], dtype=torch.long)
            return {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "labels": input_ids.clone(),
            }

    dataset = SimpleDataset(tokenized)
    print(f"  Prepared {len(dataset)} training samples.")

    # Step 4: Train
    print("\n[4/4] Training Atlas's brain...")
    if not torch.cuda.is_available():
        print("  This may take a while on CPU.")

    training_args = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=3,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=2e-5,
        warmup_steps=10,
        logging_steps=5,
        save_strategy="no",
        fp16=torch.cuda.is_available(),
        report_to="none",
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )

    trainer.train()

    # Save the fine-tuned model
    print("\nSaving Atlas's brain...")
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    print(f"\nAtlas's brain saved to: {output_dir}")
    print("\nDone! Atlas will now use your fine-tuned brain.")
    print("Start Atlas with: python -m atlas.main --text-mode")
