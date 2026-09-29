"""Per-machine settings for the sidecar.

Holds non-source secrets (HuggingFace token) in a gitignored local file so a
coworker can enter/update their own token without touching code or env vars.

Resolution order (first match wins):
  1. CLI --token
  2. env HF_TOKEN
  3. saved settings.json
  4. interactive prompt (TTY only)
"""
import getpass
import json
import os
import sys
from pathlib import Path

DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.json"


def load_settings(path: Path | None = None) -> dict:
    p = path or DEFAULT_SETTINGS_PATH
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_token(token: str, path: Path | None = None) -> Path:
    """Persist token to settings file (gitignored). Overwrites existing key."""
    p = path or DEFAULT_SETTINGS_PATH
    data = load_settings(p)
    data["hf_token"] = token.strip()
    p.write_text(json.dumps(data, indent=2) + "\n")
    # keep the secret out of git even if .gitignore is ever regressed
    return p


def resolve_token(cli_value: str | None = None,
                  env_var: str = "HF_TOKEN",
                  settings_path: Path | None = None) -> str | None:
    """Return a token from any source, or None if none found."""
    # 1. CLI overrides everything
    if cli_value:
        return cli_value.strip()
    # 2. env
    if env_var and os.getenv(env_var):
        return os.getenv(env_var).strip()
    # 3. saved settings
    saved = load_settings(settings_path).get("hf_token")
    if saved:
        return saved.strip()
    return None


def prompt_for_token(message: str | None = None) -> str | None:
    """Interactive prompt. Returns None when there's no terminal (non-interactive)."""
    if not sys.stdin.isatty():
        return None
    print(message or "Enter your HuggingFace token (hf_...):", end=" ", flush=True)
    try:
        value = getpass.getpass("")
    except (EOFError, KeyboardInterrupt):
        return None
    return value.strip() or None


def ensure_token(cli_value: str | None = None,
                 env_var: str = "HF_TOKEN",
                 settings_path: Path | None = None,
                 prompt_message: str | None = None) -> str:
    """Full resolution incl. first-use prompt + persist. Raises if unavailable."""
    token = resolve_token(cli_value, env_var, settings_path)
    if token:
        return token

    prompted = prompt_for_token(prompt_message)
    if prompted:
        save_token(prompted, settings_path)
        return prompted

    raise SystemExit(
        "\nNo HF token found (pyannote models are gated). "
        "Set it via:\n"
        "  python -m src.settings set-token   (interactive, saved for next time)\n"
        "  export HF_TOKEN=hf_...              (per-session)\n"
        "or pass --token. First: accept the model license at "
        "https://huggingface.co/pyannote/speaker-diarization-3.1"
    )


def cmd_show_settings(args=None, settings_path: Path | None = None) -> int:
    data = load_settings(settings_path)
    token = data.get("hf_token")
    print(f"settings file: {settings_path or DEFAULT_SETTINGS_PATH}")
    print(f"token set:     {'yes' if token else 'no'}")
    if token:
        # never echo the full secret
        print(f"  (starts with {token[:3]}..., {len(token)} chars)")
    return 0


def cmd_clear_token(args=None, settings_path: Path | None = None) -> int:
    p = settings_path or DEFAULT_SETTINGS_PATH
    data = load_settings(p)
    if "hf_token" in data:
        data.pop("hf_token")
        p.write_text(json.dumps(data, indent=2) + "\n")
        print("Token cleared.")
    else:
        print("No token to clear.")
    return 0


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m src.settings",
                                 description="Manage local sidecar settings (HF token).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    set_p = sub.add_parser("set-token", help="set/update the HF token")
    set_p.add_argument("token", nargs="?", help="token; omit to prompt")

    sub.add_parser("show", help="show whether a token is set")
    sub.add_parser("clear", help="remove the saved token")
    args = ap.parse_args(argv)

    if args.cmd == "set-token":
        token = args.token or prompt_for_token("Enter your HuggingFace token: ")
        if not token:
            print("No token given."); return 1
        p = save_token(token)
        print(f"Saved token to {p} (gitignored).")
        return 0
    if args.cmd == "show":
        return cmd_show_settings()
    if args.cmd == "clear":
        return cmd_clear_token()
    ap.error(f"unknown command '{args.cmd}'")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
