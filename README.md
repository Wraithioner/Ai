# Local AI Voice Agent

A personal AI assistant that runs **100% on your PC**. No API keys, no cloud, no subscriptions.

Talk to it with your voice. It listens, thinks, and speaks back.

## What It Does

- **Listens** to your voice using your microphone (Whisper speech-to-text)
- **Thinks** using a local LLM running on your hardware (Ollama + Llama 3.1)
- **Speaks** responses out loud (Piper TTS)
- **Starts automatically** when your PC boots (systemd service)
- **Stops** when your PC shuts down
- **Remembers** conversation context within a session

## Requirements

- **OS:** Linux (Ubuntu/Debian, Fedora, or Arch)
- **RAM:** 8GB minimum, 16GB recommended
- **Storage:** ~10GB for models
- **Microphone:** Any USB or built-in mic
- **Speakers:** Any audio output
- **GPU:** Optional but recommended (NVIDIA with CUDA for faster inference)

## Quick Start

```bash
# 1. Clone and run the installer
git clone <this-repo> && cd Ai
bash scripts/install.sh

# 2. Start the agent
source .venv/bin/activate
python -m agent.main

# 3. Or test in text mode first (no mic needed)
python -m agent.main --text-mode
```

The installer handles everything: system packages, Ollama, AI model download, Python environment, and optional auto-start service.

## Architecture

```
You speak
    |
    v
[Microphone] --> [Silero VAD] --> [Whisper STT] --> text
                                                      |
                                                      v
                                              [Ollama + LLama 3.1]
                                                      |
                                                      v
                                                   response
                                                      |
                                                      v
                                              [Piper TTS] --> [Speakers]
                                                                  |
                                                                  v
                                                            You hear the reply
```

## Project Structure

```
Ai/
├── agent/
│   ├── main.py      # Main loop: listen -> think -> speak
│   ├── brain.py     # LLM interface (Ollama)
│   ├── ears.py      # Speech-to-text (Whisper + VAD)
│   ├── voice.py     # Text-to-speech (Piper)
│   └── config.py    # Configuration loader
├── config/
│   └── settings.yaml  # All settings in one place
├── scripts/
│   ├── install.sh     # One-click installer
│   └── uninstall.sh   # Remove the service
└── requirements.txt
```

## Configuration

Edit `config/settings.yaml` to customize:

- **LLM model** - switch between llama3.1, mistral, phi3, etc.
- **Voice** - change the TTS voice
- **Whisper model size** - trade speed for accuracy
- **System prompt** - define your AI's personality
- **Silence threshold** - how long to wait after you stop talking

## Voice Commands

| Say | Action |
|---|---|
| *anything* | AI responds by voice |
| "goodbye" / "shut down" | Stops the agent |
| "reset" / "forget everything" | Clears conversation memory |

## Service Management

If you installed the auto-start service:

```bash
sudo systemctl start ai-agent     # Start now
sudo systemctl stop ai-agent      # Stop
sudo systemctl restart ai-agent   # Restart
sudo systemctl status ai-agent    # Check status
journalctl -u ai-agent -f         # Live logs
```

## Choosing a Model

| Model | RAM Needed | Speed | Quality |
|---|---|---|---|
| `phi3:mini` | ~3GB | Fast | Good for basic chat |
| `mistral:7b` | ~5GB | Fast | Great all-rounder |
| `llama3.1:8b` | ~6GB | Medium | Best at this size (default) |
| `gemma2:9b` | ~7GB | Medium | Good conversation |
| `llama3.1:70b` | ~40GB | Slow | Best quality, needs big GPU |

Switch models in `config/settings.yaml` or pull a new one:

```bash
ollama pull mistral:7b
```

## Troubleshooting

**"Cannot connect to Ollama"**
```bash
ollama serve  # Start the Ollama server
```

**"No microphone detected"**
```bash
arecord -l  # List audio devices
# Update input_device in config/settings.yaml
```

**"Model not found"**
```bash
ollama list          # See installed models
ollama pull llama3.1:8b  # Download the model
```

**Slow responses?**
- Use a smaller model (`phi3:mini` or `mistral:7b`)
- Use Whisper `tiny` instead of `base`
- If you have an NVIDIA GPU, set `device: "cuda"` in settings.yaml
