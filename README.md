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

## Test with generated audio
```bash
python tests/make_test_audio.py -o recordings/sample.wav
python src/diarize.py --audio recordings/sample.wav --token $HF_TOKEN
```
