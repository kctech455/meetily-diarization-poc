# Meetily Diarization Sidecar (PoC)

Adds real per-person speaker diarization to Meetily (community build).

Pipeline:
1. Watch for finished recordings (or accept file path)
2. Run WhisperX transcription + alignment
3. Run pyannote diarization on the same audio
4. Merge -> speaker-labeled segments with word timestamps
5. Emit labeled transcript (JSON/SRT/plain) and later write to Meetily SQLite

## Usage (dev)
```bash
source .venv/bin/activate
python src/diarize.py --audio path/to/recording.m4a --token $HF_TOKEN
```

## Deploy target
Windows 11 box w/ RTX. Sidecar runs as a service; Meetily hands off finished recordings.
CUDA = `--device cuda`. AVX2 requirement applies to Meetily's stock transcription binary only,
not this sidecar.

## HuggingFace token (per-machine, per-user)
pyannote's diarization model is gated on HF — every user supplies their own token.
Resolution order (first match wins): `--token` → `HF_TOKEN` env → `settings.json` → interactive prompt on first use.

```bash
# set/update your token (saved to gitignored settings.json for next runs)
python -m src.settings set-token            # prompts
python -m src.settings set-token hf_...     # inline
python -m src.settings show                 # is a token set?
python -m src.settings clear                # remove your token
```

Before first use, accept the model license: https://huggingface.co/pyannote/speaker-diarization-3.1

## Test with generated audio
```bash
python tests/make_test_audio.py -o recordings/sample.wav
# token auto-resolves via env/settings/prompt
python src/diarize.py --audio recordings/sample.wav
```
