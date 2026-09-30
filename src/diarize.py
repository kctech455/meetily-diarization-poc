"""Core diarization pipeline: WhisperX transcription + pyannote diarization.

Run on any machine (CPU works, GPU fast). Used by the Windows service.
"""
import argparse
import json
import os
from pathlib import Path

def _load_pipeline():
    """Lazy import whisperx — only load when running (keeps CLI snappy)."""
    global whisperx
    import whisperx
    return whisperx


def diarize(audio_path: str, hf_token: str, device: str = "cpu", batch_size: int = 16,
            num_speakers: int | None = None,
            min_speakers: int | None = None,
            max_speakers: int | None = None) -> dict:
    """Transcribe + diarize an audio file; return labeled segments dict.

    num_speakers / min_speakers / max_speakers are optional hints passed to pyannote.
    pyannote's auto speaker-count under-segments very short clips (e.g. a 20s test wav);
    passing num_speakers helps on known-N-speaker inputs.
    """
    whisperx = _load_pipeline()

    # 1. Transcribe + align with WhisperX
    model = whisperx.load_model("small", device=device,
                                compute_type="int8" if device == "cpu" else "float16")
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio, batch_size=batch_size)
    model_a, metadata = whisperx.load_align_model(
        language_code=result["language"], device=device)
    result = whisperx.align(result["segments"], model_a, metadata,
                            audio, device, return_char_alignments=False)

    # 2. Diarize with pyannote via whisperx's DiarizationPipeline (whisperx 3.8.6 API).
    # It handles the waveform-dict formatting internally (no torchcodec dependency) and
    # returns a pandas DataFrame of {start, end, speaker} segments.
    from whisperx.diarize import DiarizationPipeline, assign_word_speakers
    diarize_pipeline = DiarizationPipeline(
        model_name="pyannote/speaker-diarization-3.1",
        token=hf_token, device=device)
    diarize_df = diarize_pipeline(
        audio, num_speakers=num_speakers,
        min_speakers=min_speakers, max_speakers=max_speakers)

    # 3. Merge — assign speaker labels to segment-level (and word-level) transcript
    result = assign_word_speakers(diarize_df, result)

    out = {
        "language": result.get("language", "en"),
        "speakers": sorted({seg["speaker"] for seg in result["segments"] if "speaker" in seg}),
        "segments": [
            {
                "start": round(seg["start"], 3),
                "end": round(seg["end"], 3),
                "speaker": seg.get("speaker", "UNK"),
                "text": seg.get("text", ""),
            }
            for seg in result["segments"]
        ],
    }
    return out


def to_srt(segments) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        start = _srt_time(seg["start"]); end = _srt_time(seg["end"])
        lines.append(f"{i}\n{start} --> {end}\n[{seg['speaker']}]\n{seg['text']}\n")
    return "\n".join(lines)


def _srt_time(sec: float) -> str:
    ms = int((sec - int(sec)) * 1000)
    h, rem = divmod(int(sec), 3600); m, s = divmod(rem, 60)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def main():
    ap = argparse.ArgumentParser(description="Diarize an audio file (WhisperX + pyannote)")
    ap.add_argument("--audio", required=True)
    ap.add_argument("--token", default=None, help="HF token (optional; falls back to env/settings/prompt)")
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda", "mps"])
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--num-speakers", type=int, default=None,
                    help="exact speaker count hint for pyannote (helps short clips)")
    ap.add_argument("--min-speakers", type=int, default=None)
    ap.add_argument("--max-speakers", type=int, default=None)
    ap.add_argument("--out")
    args = ap.parse_args()

    try:
        from .settings import ensure_token  # package run
    except ImportError:
        from settings import ensure_token  # script run
    token = ensure_token(cli_value=args.token,
                         prompt_message="Enter your HuggingFace token for pyannote models:")

    result = diarize(args.audio, token, args.device, args.batch_size,
                     num_speakers=args.num_speakers,
                     min_speakers=args.min_speakers,
                     max_speakers=args.max_speakers)
    out_path = args.out or str(Path(args.audio).with_suffix(".diarized.json"))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {out_path}")
    print(f"Speakers: {result['speakers']}")
    print("---")
    print(to_srt(result["segments"])[:2500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
