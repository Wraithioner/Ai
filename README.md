# Atlas - Local AI Voice Agent

A personal AI assistant that runs **100% on your PC**. No API keys, no cloud, no subscriptions, no Ollama.

Say **"Atlas"** to get its attention, then talk naturally. It listens, thinks, and speaks back.

## What It Does

- **Listens** to your voice using your microphone (Whisper speech-to-text)
- **Thinks** using a local LLM running directly in Python (trainable)
- **Speaks** responses out loud (Piper TTS)
- **Remembers** conversation context within a session
- **Trainable** - fine-tune Atlas's brain with your own data
- **Self-contained** - no external servers, no third-party dependencies at runtime

## Quick Start

### Windows

```cmd
:: 1. Clone and install
git clone <this-repo> && cd Ai
scripts\install.bat

:: 2. Start Atlas (text mode)
python -m atlas.main --text-mode

:: 3. Train Atlas's brain (optional)
python -m atlas.main --train
```

### Linux

```bash
# 1. Clone and install
git clone <this-repo> && cd Ai
bash scripts/install.sh

# 2. Start Atlas (text mode)
python -m atlas.main --text-mode

# 3. Train Atlas's brain (optional)
python -m atlas.main --train
```

Or install manually: `pip install transformers accelerate huggingface-hub torch numpy pyyaml`

## Project Structure

```
Ai/
├── atlas/                      # Source code
│   ├── core/                   # Core components
│   │   ├── brain.py            #   LLM engine (runs model directly)
│   │   ├── ears.py             #   Speech-to-text (Whisper + VAD)
│   │   ├── voice.py            #   Text-to-speech (Piper)
│   │   └── config.py           #   Configuration & path management
│   ├── training/               # Fine-tuning tools
│   │   └── train.py            #   Training script
│   └── main.py                 # Entry point
├── config/
│   └── settings.yaml           # All settings in one place
├── data/
│   └── training/               # Your training data (JSONL files)
│       └── atlas_personality.jsonl
├── models/                     # Fine-tuned models saved here
├── logs/                       # Log files
├── scripts/
│   ├── install.bat             # Windows installer
│   ├── install.sh              # Linux installer
│   └── uninstall.sh            # Remove service (Linux)
└── requirements.txt
```

## Training Atlas's Brain

You can fine-tune Atlas to have a unique personality, custom knowledge, and specific behaviors.

### 1. Add training data

Edit `data/training/atlas_personality.jsonl` — each line is a conversation example:

```json
{"messages": [{"role": "system", "content": "Your name is Atlas."}, {"role": "user", "content": "What's your name?"}, {"role": "assistant", "content": "I'm Atlas, your personal AI."}]}
```

### 2. Run training

```
python -m atlas.main --train
```

### 3. Done

Atlas automatically detects and uses the fine-tuned model from `models/atlas-brain/`.

## Configuration

Edit `config/settings.yaml` to customize:

- **LLM model** - base model to use or fine-tune
- **Voice** - change the TTS voice
- **Whisper model size** - trade speed for accuracy
- **System prompt** - define Atlas's personality
- **Silence threshold** - how long to wait after you stop talking

## Voice Commands

| Say | Action |
|---|---|
| "Atlas, ..." | Atlas listens and responds |
| "Atlas" (alone) | Atlas acknowledges and waits |
| "goodbye" / "shut down" | Stops the agent |
| "reset" / "forget everything" | Clears conversation memory |

## Choosing a Base Model

| Model | RAM Needed | Speed | Quality |
|---|---|---|---|
| `TinyLlama/TinyLlama-1.1B-Chat-v1.0` | ~2GB | Fast | Basic chat |
| `Qwen/Qwen2.5-1.5B-Instruct` | ~3GB | Fast | Good quality (default) |
| `microsoft/Phi-3-mini-4k-instruct` | ~8GB | Medium | Great quality |

Switch models in `config/settings.yaml` — they auto-download on first run.
