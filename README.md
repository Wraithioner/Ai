# AI Telegram Bot

A Telegram chatbot powered by a local LLM. Runs on **Railway** with no external API keys needed — the AI model runs directly in the process.

## Features

- **Telegram chat** — send messages, get AI responses
- **Per-user memory** — each user gets their own conversation history
- **Configurable personality** — change the system prompt to anything
- **Trainable** — fine-tune the model with your own data
- **Rate limiting** — prevents abuse
- **Railway-ready** — deploys with one click

## Deploy to Railway

### 1. Get a Telegram bot token

Message [@BotFather](https://t.me/BotFather) on Telegram and create a new bot. Copy the token.

### 2. Deploy on Railway

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) and create a new project from the repo
3. In **Settings > Variables**, add:
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   ```
4. Railway auto-detects Python and deploys

### 3. Optional environment variables

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | (required) | Bot token from @BotFather |
| `MODEL_NAME` | `Qwen/Qwen2.5-1.5B-Instruct` | HuggingFace model ID |
| `SYSTEM_PROMPT` | (see config) | Bot personality / instructions |
| `MAX_TOKENS` | `512` | Max response length |
| `TEMPERATURE` | `0.7` | Creativity (0.0-1.0) |
| `CONTEXT_WINDOW` | `10` | Exchanges to remember per user |
| `MAX_USERS` | `100` | Max concurrent users in memory |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Run Locally

```bash
# Install
pip install -r requirements.txt

# Set your bot token
export TELEGRAM_BOT_TOKEN="your_token_here"

# Start
python -m atlas.main
```

## Project Structure

```
Ai/
├── atlas/
│   ├── core/
│   │   ├── brain.py          # LLM engine (multi-user, memory managed)
│   │   └── config.py         # Config loader with env var overrides
│   ├── telegram/
│   │   └── bot.py            # Telegram bot handler
│   ├── training/
│   │   └── train.py          # Fine-tuning script
│   └── main.py               # Entry point
├── config/
│   └── settings.yaml         # Default configuration
├── data/
│   └── training/             # Training data (JSONL)
├── models/                   # Fine-tuned models
├── Procfile                  # Railway process definition
├── .dockerignore             # Lighter Railway builds
└── requirements.txt          # Python dependencies
```

## Choosing a Model

| Model | RAM | Speed | Quality |
|---|---|---|---|
| `TinyLlama/TinyLlama-1.1B-Chat-v1.0` | ~2GB | Fast | Basic |
| `Qwen/Qwen2.5-1.5B-Instruct` | ~3GB | Fast | Good (default) |
| `Qwen/Qwen2.5-7B-Instruct` | ~14GB | Slow | Great |

Set via `MODEL_NAME` env var or in `config/settings.yaml`.

## Train the Bot

Fine-tune with your own data to give the bot a custom personality:

```bash
# Add training data to data/training/*.jsonl
# Format: {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}

python -m atlas.training.train
```

The bot auto-detects fine-tuned models from `models/atlas-brain/`.

## Bot Commands

| Command | Action |
|---|---|
| `/start` | Welcome message |
| `/reset` | Clear conversation memory |
| `/help` | Show commands |
