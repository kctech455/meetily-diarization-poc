# Windows (RTX box) Deploy

## Prerequisites
- Windows 11, NVIDIA GPU w/ CUDA drivers
- Python 3.11 (3.14 breaks `ctranslate2` — use 3.11)
- Ollama installed + running (`http://localhost:11434`)
- Meetily installed (`x64-setup.exe` from releases)
- HuggingFace token with access to `pyannote/speaker-diarization-3.1` (gated — accept license on HF first)

## Setup
```powershell
py -3.11 -m venv .venv311
.venv311\Scripts\activate
python -m pip install whisperx pyannote.audio
```

## Run (one-off test)
```powershell
$env:HF_TOKEN = "hf_..."
python src\diarize.py --audio meeting.m4a --device cuda --out out.json
```

## Run as service (watchdog)
Watches a folder; every finished recording gets diarized and a JSON written next to it.
```powershell
# once, then wire to Task Scheduler / NSSM at startup
python src\watchdog.py --watch C:\meetings --device cuda
```

## Meetily integration (fork)
1. Meetily saves recordings to its storage dir; point the watchdog at it (or have Meetily copy finished files to `--watch`).
2. After diarization, copy speaker labels into Meetily's SQLite `speaker` column (migration already exists upstream).
3. Point Meetily summary LLM at `http://localhost:11434` (Ollama).

## GPU note
Transcription (stock Meetily installer) = Vulkan/AVX2, not CUDA. This sidecar uses CUDA — that's where the RTX pays off.
