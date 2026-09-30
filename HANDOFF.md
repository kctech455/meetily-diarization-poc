# HANDOFF.md — Meetily Diarization Sidecar (POC) Project Resume File

> Read this file after a reboot to resume this project without reloading the full
> conversation. Everything needed to continue is in here.

Last updated: 2026-09-29 (POC scaffold + per-user HF token management + Windows plan)

---

## 1. ONE-LINE STATUS

Building the **missing "full speaker diarization" feature** for a **Meetily fork** — a
local (MIT, Tauri, Rust) Teams meeting recorder — so the user's real goal works: attend
lots of Microsoft Teams meetings, get them transcribed **with per-person speaker
labels**, made searchable, and get action items, without paying for a SaaS. This POC is
the **diarization sidecar** (WhisperX + pyannote) that replaces Meetily community's
absent real diarization. Pipeline proven at the transcription layer; **blocked only by
a HuggingFace gated-model token** for the pyannote step.

---

## 2. PROJECT LOCATIONS

```
/home/kc/myApps/meetily-diarization-poc/   # project root (== future GitHub repo root)
  HANDOFF.md          # THIS FILE
  README.md           # overview + HF token flow + usage
  DEPLOY-WINDOWS.md   # how to run on the Win11/RTX box
  requirements.txt    # whisperx, pyannote.audio
  src/
    __init__.py
    diarize.py        # transcribe + diarize + merge -> labeled segments (SRT/JSON)
    settings.py       # per-machine HF token manager (CLI + resolution order)
    watchdog.py       # folder-watcher service for the Meetily handoff
  tests/
    make_test_audio.py # generates a 2-speaker test WAV (Alice/Bob via espeak-ng)
  .gitignore          # ignores venvs, recordings, HF secrets, settings.json
```

Git: local-only `main` branch, **NO remote configured yet**. 7 commits, clean tree.
User wants this pushed to git eventually (`~/myApps` is the app staging area).

---

## 3. GOAL & WHY (context you need)

- **User's real goal:** own Teams meetings → transcribed with speaker labels →
  searchable → auto action items. No SaaS, self-hosted locally.
- **Why fork Meetily (not AnythingLLM):**
  - AnythingLLM's Meeting Assistant is **closed-source desktop code** (prebuilt
    `.exe`/`.dmg` only). The open anything-llm repo is the web/server app and does NOT
    contain Meeting Assistant. Can't fork/modify/audit it.
  - Official Meetily README states verbatim: *"Speaker diarization is also planned for
    PRO in mid-June."* → community Meetily has **NO real per-person diarization**, only
    mic-vs-system ("you vs Other"). This is the gap the fork fills.
  - Meetily is MIT, fully open, 31k stars, Tauri (Rust backend + Next.js frontend),
    native Windows `.exe` installer, local-first, Ollama summaries, editable transcript,
    join-notification tray UI.
- **User's choices already made:**
  - **Action items = text only** (cut/paste to email), NOT agentic execution. The
    "click Run → execute agent skill" idea is DROPPED — user explicitly doesn't want it.
  - Local-first summaries via their **existing Ollama** (`http://localhost:11434`), cloud
    fallback ok.
  - Windows 11 machine is a **separate physical box with its own GPU** (RTX) — NOT this
    N100 VM. Everything runs locally on that box.
  - Fork scope = add real per-person diarization + speaker-name editing (rename) +
    (optional) custom summary templates. NOT rebuilding capture/transcription/summary.
- **The Windows machine topology:** separate box w/ RTX. Transcription (stock Meetily
  installer) is Vulkan/AVX2, NOT CUDA; the diarization sidecar is where CUDA pays off.

---

## 4. TECH STACK & DECISIONS ALREADY MADE

- **Python 3.11 is REQUIRED** (~/.local/bin/python3.11 on this VM). Python 3.14 (the
  Hermes default) BREAKS whisperx: it pins `ctranslate2==4.4.0` which has no 3.14 wheel.
  - The original `.venv` (3.14) failed; rebuilt as `.venv311` (3.11) → works.
  - **Venv name `.venv311`, NOT `.venv`** (a destructive re-create of `.venv` was blocked
    by the safety layer; we used `.venv311` to avoid the delete).
- **Installed & verified** (into `.venv311`): whisperx 3.8.6, pyannote.audio 4.0.7,
  torch 2.8.0+cu128, faster-whisper 1.2.1, ctranslate2 4.8.2. All import clean.
- **No CUDA on this VM** (torch.cuda.is_available() == False) — it's the N100. GPU runs
  happen on the Win11 box. Local tests use `--device cpu`.
- **pyannote diarization model is GATED on HuggingFace**: `pyannote/speaker-diarization-3.1`
  needs (a) license acceptance at the model page, (b) a per-user HF token. No token
  available on this VM yet → the final pyannote step is UNTESTED. Transcription IS proven.
- **Per-machine HF token design (per the user's coworker-sharing question):**
  resolution order = `--token` → `HF_TOKEN` env → `settings.json` (gitignored) →
  interactive prompt on first use. Never commit tokens; never store raw in Hermes memory.

---

## 5. ARCHITECTURE (built)

```
src/diarize.py
  _load_pipeline()  : lazy-import whisperx + pyannote (keeps CLI fast, avoids import cost)
  diarize(audio, token, device, batch_size) -> dict
    1. whisperx.load_model("small") -> transcribe -> align (whisperx.align)
    2. pyannote Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token)  # GATED
    3. whisperx.assign_speaker_labels(segments, diarization)
    -> {language, speakers[], segments[{start,end,speaker,text}]}
  to_srt(segments)  : SRT with [SPEAKER] tags
  main()            : CLI --audio --token --device --batch-size --out

src/settings.py     : per-machine HF token manager
  resolve_token(cli, env_var, settings_path)  # first match wins
  ensure_token(...)  # full resolution incl. interactive prompt + persist; raises w/ guidance
  load_settings / save_token / prompt_for_token
  CLI: python -m src.settings {set-token [tok] | show | clear}
  settings.json is GITIGNORED; show() never prints the full secret (prefix+length only)

src/watchdog.py     : service that watches a folder, diarizes finished recordings,
  writes JSON next to it. Uses ensure_token too. --watch --token --device --out

tests/make_test_audio.py : espeak-ng → 2 alternating speaker WAV (Alice/Bob), 20.1s.
  Fallback: pure-tone placeholder if espeak-ng missing.
```

### Gotchas / decisions (DO NOT regress)
- `--token` default is `None` (not `os.getenv`), so resolution order works; env handled
  inside `ensure_token`.
- `cmd_set_token` helper was removed — its logic lives inline in `main()`; subcommand
  positional arg must be declared on the subparser (`set_p.add_argument`).
- `whisperx.__version__` does NOT exist (module has no `__version__` attr) — don't grep for it.
- Run via `python -m src.settings` / `python src/diarize.py`; `from .settings import` works
  in package context, `from settings import` as fallback in script context (watchdog).
- Test audio: sample.wav at `recordings/` (gitignored). Regenerate when needed.
- Settings file is plaintext JSON. Fine for this trusted LAN; if this ever goes public,
  swap to Windows `keyring` credential store (flagged as future, not yet done).

---

## 6. SECRETS — WHERE THEY LIVE (do NOT commit, do NOT put in memory)

| Secret | Location | Used for |
|---|---|---|
| HF token (per-user) | `settings.json` (gitignored) OR `HF_TOKEN` env OR `--token` | pyannote gated model |
| SSH key for Win11 test | `~/.ssh/win11_diar` (+ `.pub`) | (prepped; Win11 not configured yet) |

No HF token exists on this VM yet. Reference by path/var, never echo/stash raw values.

---

## 7. VERIFIED STATE (the proof so far)

- `requirements.txt` deps install clean on **Python 3.11** (`.venv311`):
  whisperx 3.8.6, pyannote.audio 4.0.7, torch 2.8.0+cu128, faster-whisper 1.2.1.
- **Transcription PROVEN end-to-end** on this VM (CPU, model `tiny`):
  `whisperx.load_model('tiny','cpu','int8')` → detected language `en` → transcribed the
  20.1s two-speaker sample (`[0.0->20.1] Hello, this is Alice speaking. ...`).
- **Full `diarize.py` run reaches the expected gate:** `GatedRepoError: 401` fetching
  `pyannote/speaker-diarization-3.1` — proven NOT a code bug; it's the token gate.
- **Token manager verified live**: `set-token hf_test12345` → `show` (prefix hf_ + length) →
  `resolve_token()` returns saved value → `clear` → gone. Settings confirmed gitignored.
- `python -m py_compile` passes on settings.py / diarize.py / watchdog.py.
- Git: `main` clean, 7 commits, no remote. Files: `.gitignore`, DEPLOY-WINDOWS.md,
  README.md, requirements.txt, src/{__init__,diarize,settings,watchdog}.py, tests/make_test_audio.py.

---

## 8. WHAT IS **NOT** DONE YET (next candidates, in priority order)

1. **Get an HF token + accept pyannote license** → run the FULL pipeline end-to-end on a
   real recording to prove the diarization merge & speaker labels. THIS IS THE BLOCKING
   PATH. Requires user action: sign in to huggingface.co, accept
   `pyannote/speaker-diarization-3.1` license, create a token, then either `set-token` on
   this VM (slow CPU proof) or on the Win11 box (`--device cuda`).
2. **Test on the Win11/RTX box** — exact steps in DEPLOY-WINDOWS.md. Distinguish
   transcription (Vulkan/AVX2, stock installer) vs diarization (CUDA sidecar).
3. **Remote-test access (user asked, prepped but not done):**
   - SSH keypair generated at `~/.ssh/win11_diar` (+ pub, host `hermes-remote-test@win11`).
   - Win11 needs: OpenSSH server enabled, pub key into `admin_authorized_keys` (or
     user authorized_keys), user shares host/IP. Then Heremes can ssh in and run
     `--device cuda` tests directly.
   - Terminal access (SSH) is the clean answer; NoMachine/RDP GUI isn't reliable for
     driving. No remote desktop set up for this yet.
4. **Push to git** — no remote yet. Either add remote + push, or set up for coworker
   sharing. Remote is a user decision (repo not created yet; PAT pattern exists in
   food-log-app if reusing `kctech455`).
5. **Fork integration (the actual product deliverable):** wire watchdog → Meetily's
   storage dir, write labels into Meetily SQLite speaker column (upstream migration
   exists), point Meetily summary at local Ollama. Plus: speaker-name rename UI
   (click-to-rename, trivial — DB column exists), optional custom summary templates.
6. **Optional hardening:** keyring backend for token (if going public), model download
   caching note, per-file concurrency on watchdog.

---

## 8B. WIN11 SETUP STATE (verified 2026-09-30 via SSH as oit@10.141.9.147)

- SSH to Win11 works: `ssh oit@10.141.9.147` from this VM (key auth, BatchMode=yes).
- **Reality check: the GPU is a Quadro P1000 (Pascal, 4GB), NOT an RTX.** Driver 397.93
  (CUDA 10.x-era) → modern torch CUDA (cu12x/cu128) CANNOT run on it without a
  driver+hardware upgrade. The sidecar works on CPU here (`--device cpu`). The handoff's
  "RTX/CUDA pays off" assumption does NOT hold on THIS box. If GPU diarization matters,
  either update drivers (P1000 still only gets old CUDA) or use a real RTX machine.
- **winget is BROKEN on this box** (crashes with 0xC0000005 access violation on install).
  Do NOT use winget for installs. Use direct downloads/inno/static binaries instead.
- **Python 3.11.9 installed** at `C:\Users\OIT\AppData\Local\Programs\Python\Python311\python.exe`
  (official installer, per-user). `py -3.11` works.
- **Git 2.46.2** installed as portable MinGit at `C:\Program Files\Git\cmd\git.exe`.
  HAD to delete a self-referential `include path = C:/Program Files/Git/etc/gitconfig`
  line inside `C:\Program Files\Git\etc\gitconfig` (circular include error). Fixed.
- **Microsoft Visual C++ Redistributable (x64, 2015-2022) was REQUIRED** — torch fails
  with WinError 126 (`c10.dll` not found) and ctranslate2 fails to load without it.
  Installed from `https://aka.ms/vs/17/release/vc_redist.x64.exe`.
- **ffmpeg required**: whisperx's `load_audio` shells out to `ffmpeg` on PATH → WinError 2.
  `pip install imageio-ffmpeg` bundles a static ffmpeg at
  `.venv311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe` — but
  whisperx looks for `ffmpeg.exe`, so a COPY named `ffmpeg.exe` must exist in that dir
  (created). Prepend that `binaries\` dir to PATH before running.
- **`torchcodec` missing / libtorchcodec load warning is NON-FATAL** — pyannote's audio
  IO warns it can't use built-in decoding, but whisperx uses its own ffmpeg path. Ignore.
- Project code deployed to `C:\Users\OIT\meetily-diarization-poc\` (venv `.venv311`,
  versions match this VM: torch 2.8.0+cpu, whisperx 3.8.6, pyannote.audio 4.0.7).

### VERIFIED WORKING ON WIN11 (all exit 0)
- token manager: `set-token hf_TEST12345` → `show` (masked) → `clear`  ✓
- full transcription: whisperx `tiny`, CPU, sample.wav → `[0.0->20.1]` full Alice/Bob
  transcript, language `en` ✓
- src package imports (diarize/settings/watchdog) ✓, py_compile ✓
- diarize.py CLI now runs through token resolution → raises the EXPECTED gated-model
  guidance (blocker is the user's HF token + pyannote license, exactly the handoff's §8.1)

### CODE FIX APPLIED (bug found during Win11 test)
`src/diarize.py` and `src/watchdog.py`: `from .settings import ensure_token` inside
`main()` breaks when run as a SCRIPT (`python src/diarize.py`) with "ImportError: attempted
relative import with no known parent package". Fixed with try/except fallback to
`from settings import ensure_token` (same pattern watchdog already uses for `from .diarize`).
DO NOT regress to bare `from .settings import`.

---

## 9. GOTCHAS / OPERATIONAL NOTES

- Hermes model for this session: DeepSeek-V4-Flash0731 via myollama (was gemma4). Self-ID
  adjusts accordingly.
- Safety layer BLOCKED deleting/rebuilding `.venv` (destructive op needs consent, /yolo
  does NOT count). Hence the `.venv311` name. Keep it; don't try to rename over `.venv`.
- This is the Proxmox N100 VM (Ubuntu 24.04, x86_64) via NoMachine; no GPU here.
- The security layer may mask `key`/`token`/`secret`-looking words in tool output — that's
  cosmetic redaction, not real corruption.
- `recordings/`, `settings.json`, venv dirs, `*.diarized.json`, `*.srt`, `*.wav`,
  `HF_TOKEN*` are gitignored.

---

## 10. WIN11 EXACT TEST STEPS (summary — full version in DEPLOY-WINDOWS.md)

A. Prereqs: Python **3.11** (NOT 3.12+/3.14), Ollama (only needed for summaries later),
   Git for Windows.
B. Get code onto Win11: no remote yet → either `git push` from a remote we set up, or
   copy the folder over the LAN.
C. `py -3.11 -m venv .venv`, activate, `pip install whisperx pyannote.audio` (~minutes, torch ~2GB).
D. Accept `pyannote/speaker-diarization-3.1` license + create an HF token.
E. `python -m src.settings set-token hf_YOURTOKEN`
F. `python tests\make_test_audio.py -o recordings\sample.wav`
   `python src\diarize.py --audio recordings\sample.wav --device cuda`  ← the GPU difference
G. (optional) `python src\watchdog.py --watch recordings --device cuda`

---

## 11. HOW TO RESUME

After reboot, user says: "read /home/kc/myApps/meetily-diarization-poc/HANDOFF.md" (or
"read the handoff"). Then the highest-value next step is §8.1: get an HF token and prove
the full diarization pipeline end-to-end. Ask the user for the token (or have them run
`python -m src.settings set-token`) and accept the pyannote license first — that's the
single blocker. After local proof, move to the Win11/RTX test (§8.2) with `--device cuda`.

Context you'll want up front: the user liked AnythingLLM's Speaker diarization, meeting
summary, and Agentic follow-up actions — but Agentic is now explicitly DROPPED (text
action items only). Forking Meetily is the chosen path (closed-source AnythingLLM can't
be forked). The project lives under `/home/kc/myApps/` and is destined for git.

---
# END OF HANDOFF.md
