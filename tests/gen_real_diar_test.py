"""Generate a realistic 2-speaker WAV with DISTINCT VOICES (female vs male) so pyannote
diarization has real acoustic separation to work with. Uses espeak-ng with two different
voice variants. Longer than the old 20s placeholder.

Usage: python tests/gen_real_diar_test.py -o recordings/meeting2.wav
"""
import argparse
import subprocess
import wave
from pathlib import Path


def espeak(text: str, out_wav: Path, voice: str, base_pitch: int = 50, speed: int = 160):
    subprocess.run(
        ["espeak-ng", "-w", str(out_wav),
         "-v", voice, "-p", str(base_pitch), "-s", str(speed), text],
        check=True, capture_output=True,
    )


def silence(duration_s: float, rate: int = 16000) -> bytes:
    n = int(duration_s * rate)
    return b"\x00\x00" * n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="recordings/meeting2.wav")
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # ALICE = higher pitch, standard en voice (bright/accent)
    # BOB   = lower pitch, RP voice (darker/different formants)
    # Distinct pitch + different formant -> real acoustic separation for pyannote.
    alice = ("en", 70)
    bob = ("en-gb-x-rp", 35)

    segs = [
        # (voice, pitch, text, gap_after_s)
        (alice, "Welcome everyone. Thank you for joining this project kickoff meeting today.", 0.6),
        (bob, "Thanks Alice. I think the timeline of four weeks is realistic if we start now.", 0.6),
        (alice, "Great. Let us confirm the main objectives and the deliverables for this quarter.", 0.6),
        (bob, "I will own the backend integration and the database schema changes.", 0.6),
        (alice, "Perfect. I will handle the front end and coordinate with the design team.", 0.6),
        (bob, "Sounds good. We should also set up the continuous integration pipeline early.", 0.8),
    ]

    parts = []
    tmp = out.parent / "_voice_tmp.wav"
    total = 0.0
    for (voice, pitch), text, gap in segs:
        espeak(text, tmp, voice, base_pitch=pitch)
        data = tmp.read_bytes()
        parts.append(data)
        total += len(data) / (2 * 16000)
        if gap:
            parts.append(silence(gap))
            total += gap
        tmp.unlink()

    data = b"".join(parts)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(data)

    print(f"Wrote {out}  ({total:.1f}s, 16kHz mono) — ALICE(female) / BOB(male), {len(segs)} turns")


if __name__ == "__main__":
    main()
