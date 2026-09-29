"""Generate a tiny two-speaker test WAV using espeak-ng (if available) or a tone.

Two alternating speech segments -> good enough to exercise the diarization merge.
"""
import argparse
import subprocess
import struct
import sys
import wave
from pathlib import Path


def _espeak_available() -> bool:
    try:
        subprocess.run(["espeak-ng", "--version"], capture_output=True)
        return True
    except FileNotFoundError:
        return False


def espeak_segment(text: str, out_wav: Path):
    """Render text to wav via espeak-ng."""
    subprocess.run(
        ["espeak-ng", "-w", str(out_wav), text], check=True, capture_output=True
    )


def silence(duration_s: float, rate: int = 16000) -> bytes:
    n = int(duration_s * rate)
    return b"\x00\x00" * n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="recordings/sample.wav")
    ap.add_argument("--lang1", default="en")
    ap.add_argument("--lang2", default="en")
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not _espeak_available():
        print("espeak-ng not found — falling back to a pure-tone placeholder.")
        _write_tone(out)
        print(f"Wrote tone placeholder -> {out}")
        return

    segs = [
        ("Hello, this is Alice speaking. I would like to confirm the project timeline.", Path(out.parent / "_a.wav")),
        (silence(0.4), None),
        ("Hi Alice, this is Bob. I think we can finish by next Friday if we start now.", Path(out.parent / "_b.wav")),
        (silence(0.4), None),
        ("Perfect Bob. Let us aim for next Friday and assign the tasks.", Path(out.parent / "_a2.wav")),
    ]

    parts = []
    for item, p in segs:
        if isinstance(item, bytes):
            parts.append(item)
        else:
            espeak_segment(item, p)
            parts.append(p.read_bytes())
            p.unlink()

    data = b"".join(parts)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(data)

    dur = len(data) / (2 * 16000)
    print(f"Wrote {out}  ({dur:.1f}s, 16kHz mono) — two speaker alternating.")


def _write_tone(out: Path, rate: int = 16000, duration_s: float = 6):
    import math
    frames = []
    for i in range(int(rate * duration_s)):
        # 440Hz, gentle; two phases separated by silence for "diarization" shape
        v = int(12000 * math.sin(2 * math.pi * 440 * i / rate))
        frames.append(struct.pack("<h", v))
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(frames))


if __name__ == "__main__":
    main()
