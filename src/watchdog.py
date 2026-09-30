"""Windows service watchdog: watches a folder for finished recordings,
runs diarization, writes labels back. Placeholder for the Meetily fork hook.

Deploy: run as a background process on the Windows box (Task Scheduler or NSSM).
Requires HF_TOKEN set (or --token). CUDA = --device cuda.
"""
import argparse
import os
import sys
import time
from pathlib import Path

try:
    from .diarize import diarize, _srt_time  # package run
except ImportError:
    from diarize import diarize, _srt_time  # script run


def run_forever(watch_dir: Path, token: str, device: str, poll_s: float = 5.0,
                out_dir: Path | None = None):
    watch_dir = watch_dir.resolve()
    out_dir = out_dir or watch_dir / "diarized"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[watchdog] watching {watch_dir} -> {out_dir} ({device})", flush=True)

    seen: set[str] = set()
    while True:
        for f in watch_dir.iterdir():
            if f.is_file() and f.suffix.lower() in {".wav", ".m4a", ".mp3", ".mp4", ".webm"}:
                key = f"{f.name}:{f.stat().st_size}:{f.stat().st_mtime:.0f}"
                if key in seen:
                    continue
                seen.add(key)
                # skip files still being written (size changed recently)
                if time.time() - f.stat().st_mtime < 2:
                    continue
                print(f"[watchdog] diarizing {f.name}", flush=True)
                try:
                    result = diarize(str(f), token, device)
                    out = out_dir / f"{f.stem}.json"
                    _write_json(out, result)
                    print(f"[watchdog] wrote {out}", flush=True)
                except Exception as e:  # noqa: BLE001
                    print(f"[watchdog] FAILED {f.name}: {e}", flush=True)
        time.sleep(poll_s)


def _write_json(path: Path, result: dict) -> None:
    import json
    with open(path, "w") as fh:
        json.dump(result, fh, indent=2)


def main():
    ap = argparse.ArgumentParser(description="Diarization watchdog service")
    ap.add_argument("--watch", required=True, help="folder to watch")
    ap.add_argument("--token", default=None, help="HF token (optional; falls back to env/settings/prompt)")
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda", "mps"])
    ap.add_argument("--out")
    args = ap.parse_args()

    try:
        from .settings import ensure_token  # package run
    except ImportError:
        from settings import ensure_token  # script run
    token = ensure_token(cli_value=args.token,
                         prompt_message="Enter your HuggingFace token for pyannote models:")

    run_forever(Path(args.watch), token, args.device,
                out_dir=Path(args.out) if args.out else None)


if __name__ == "__main__":
    raise SystemExit(main())
