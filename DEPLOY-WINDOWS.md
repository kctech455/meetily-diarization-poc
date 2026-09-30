# Windows (RTX box) Deploy — FULL RUNBOOK

> Self-serve, step-by-step guide to run the meetily diarization sidecar on a Windows 11
> machine with an NVIDIA RTX GPU (**RTX 2000 Ada, 8GB**).
>
> Verified end-to-end (CPU path) on a Quadro P1000 test box 2026-09-30. Every pitfall
> below was hit and fixed in real setup — follow this doc, not the terse README.
> You are doing this solo (no agent help), so each step is explicit with the exact
> command. **Do the steps in order.**

---

## 0. What this machine needs (checklist)

- [ ] Windows 11, admin account
- [ ] NVIDIA GPU with **CUDA-capable drivers** (RTX 2000 Ada = compute 8.9; see §1)
- [ ] Internet access
- [ ] Git for Windows (optional but recommended, §2)
- [ ] Python 3.11 (REQUIRED — 3.12+/3.13/3.14 BREAK `ctranslate2`, the faster-whisper core) — §3
- [ ] HuggingFace token with access to `pyannote/speaker-diarization-3.1` (gated) — §4
- [ ] ffmpeg on PATH — §5

Skip nothing. Each skipped step below turns into a confusing error later.

---

## 1. GPU DRIVERS (DO FIRST)

torch CUDA needs a **driver that supports CUDA 12.x**. For the RTX 2000 Ada the current
NVIDIA driver (≥ 535) is required.

1. Update your NVIDIA driver to the latest **RTX/Studio or Production Branch** driver.
   - Download: https://www.nvidia.com/Download/index.aspx
   - Select: RTX 2000 Ada Generation → Windows 11 → your OS.
2. Verify the GPU + driver from a PowerShell:
```powershell
nvidia-smi
```
You should see your GPU name, driver version, and a "CUDA Version" (the driver's max
supported toolkit). **On this machine you reported `596.71` / CUDA 13.2 — that's great:**
it comfortably runs torch's cu128 builds (they only need driver ≥535).
If `nvidia-smi` is not a recognized command, the driver isn't installed properly — fix
this before continuing.

> If you see a driver older than ~535 (e.g. the 397.93 on a test P1000), update it first —
> those can't run modern torch CUDA.

---

## 2. INSTALL GIT FOR WINDOWS (recommended)

Only needed if you plan to clone/pull this repo instead of copying the folder. Either way:
```powershell
winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements
```
If winget is broken on this machine (crashes), download the **portable MinGit** zip from
`https://github.com/git-for-windows/git/releases/latest` (`MinGit-<ver>-64-bit.zip`),
extract to `C:\Program Files\Git`, and add `C:\Program Files\Git\cmd` to your PATH.

---

## 3. INSTALL PYTHON 3.11 (REQUIRED — NOT 3.12/3.13/3.14)

`whisperx` pins `ctranslate2` (via faster-whisper) which has **no wheels for Python 3.12+**,
and 3.14 definitely breaks. Use **3.11** specifically.

### Option A — winget (preferred):
```powershell
winget install --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements --scope user
```

### Option B — official installer (fallback if winget is broken):
Download `python-3.11.9-amd64.exe` from `https://www.python.org/downloads/windows/`
(or direct: `https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe`), then run:
```powershell
.\python-3.11.9-amd64.exe /quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1 Include_test=0
```
> If you install per-user (InstallAllUsers=0), the python.exe lives at:
> `C:\Users\<you>\AppData\Local\Programs\Python\Python311\python.exe`

### Verify:
```powershell
py -3.11 --version     # should print "Python 3.11.9"
py -3.11 -c "import sys; print(sys.version)"
```
If `py -3.11` errors, the launcher or 3.11 isn't on PATH — reinstall with `Include_pip=1 PrependPath=1`.

---

## 4. INSTALL MICROSOFT VISUAL C++ REDISTRIBUTABLE (REQUIRED)

**Do not skip.** torch hard-fails with `WinError 126` (c10.dll not found) and ctranslate2
fails to load — both need the VC++ runtime.

Download and run (exact URL):
```
https://aka.ms/vs/17/release/vc_redist.x64.exe
```
Run the .exe with default options (install for all users).
Then **open a NEW PowerShell window** so the DLLs are picked up.

---

## 5. INSTALL FFMPEG (REQUIRED — whisperx shells out to it)

whisperx's `load_audio()` calls the `ffmpeg` executable on your PATH. Without it you get
`FileNotFoundError: [WinError 2] The system cannot find the file specified`.

### Recommended (bundled with the venv — no system install needed):
```powershell
py -3.11 -m pip install imageio-ffmpeg
```
Then find the bundled ffmpeg (it's a `.exe` named `ffmpeg-win-x86_64-v<ver>.exe` inside
the venv's `Lib\site-packages\imageio_ffmpeg\binaries\`). whisperx looks for literally
`ffmpeg`, so **create a copy named `ffmpeg.exe`** in that folder:
```powershell
$bin = (py -3.11 -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())").TrimEnd()
$dir = Split-Path $bin
$name = Split-Path $bin -Leaf
if ($name -ne "ffmpeg.exe") { Copy-Item $bin "$dir\ffmpeg.exe" -Force }
"ffmpeg is at: $dir\ffmpeg.exe"
```
**Add that `binaries\` folder to PATH permanently:**
```powershell
$dir = (py -3.11 -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())").TrimEnd() | Split-Path
[Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";$dir", [EnvironmentVariableTarget]::User)
```
Then open a NEW PowerShell and confirm:
```powershell
ffmpeg -version
```

### Alternative (if you prefer a system-wide install):
Install ffmpeg via `winget install Gyan.FFmpeg` or download the full build from
`https://www.gyan.dev/ffmpeg/builds/` and add its `bin\` to PATH.

---

## 6. GET THE CODE ONTO THE BOX

Either:
- **git clone** the repo once it's been pushed to a remote (there's **no remote configured
  yet** as of 2026-09-30; push it first from the machine that has the code), or
- **copy the folder** `meetily-diarization-poc` over the LAN onto the new box (this works
  right now — a plain `scp`/shared-folder copy of the four files below is enough). Do NOT
  copy the `.venv311` folder or `recordings/` over; recreate them locally.

The project folder must contain at least:
```
requirements.txt
src/diarize.py
src/settings.py
src/watchdog.py
```
(you don't need the venv or recordings to run; they get created locally.)

---

## 7. CREATE THE VENV + INSTALL DEPENDENCIES

From a PowerShell, in the project root (`C:\...\meetily-diarization-poc`):
```powershell
py -3.11 -m venv .venv311
.venv311\Scripts\activate
python -m pip install --upgrade pip
```

### Install CUDA torch FIRST (so pip doesn't pull the CPU build)
PyPI's default Windows torch is **CPU**. For the RTX you want the CUDA build.
> Your driver is **CUDA 13.2 / 596.71** — more than new enough. Prefer the **cu128** index
> (torch 2.8/2.10 stable builds exist as `cp311 win_amd64` wheels there). cu128 runs on any
> driver ≥535, including yours — don't chase cu13x/cu14x wheels unless you need them;
> torch's cu128 builds are battle-tested with whisperx/pyannote.
```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

### Then install the sidecar deps
```powershell
pip install whisperx pyannote.audio
```
> These pull `faster-whisper` + `ctranslate2` (CPU) and `pyannote.audio`. Both are fine —
> the heavy GPU lifting happens in torch, which you've already installed as CUDA.

> **KNOWN PIP TRAP — do the torch step ABOVE before these.** whisperx pins `torch~=2.8.0`
> and `pyannote.audio` wants `torch>=2.8.0`. PyPI's default `torch-2.8.0` Windows wheel is
> **CPU**. If you run `pip install whisperx pyannote.audio` *without* torch already installed,
> pip pulls PyPI's CPU torch to satisfy the pin. Installing the cu128 torch **first** makes
> pip treat torch as already-satisfied (your `2.8.0+cu128` meets the pin) and it won't touch it.
> If you hit a "CPU torch" result anyway, `pip install --reinstall --no-deps torch --index-url
> https://download.pytorch.org/whl/cu128` afterward.

### Verification (CRITICAL — do this before proceeding):
```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.version.cuda)"
```
You want output like `2.8.0+cu128 True 12.8` or `2.10.0+cu128 True 12.8` — the key is
**`True`** in the middle and a `+cu1xx` suffix on the version (NOT `+cpu`).
- `torch.cuda.is_available()` must be **True** — if it's False, you got the CPU wheel.
- If `c10.dll` or DLL errors appear, the VC++ redist (§4) isn't installed — redo it.
```powershell
python -c "import whisperx; print('whisperx ok')"
python -c "import pyannote.audio; print('pyannote ok')"
python -c "from src.diarize import diarize; from src.settings import resolve_token; print('src ok')"
```
> The `pyannote.audio` import may print a loud Warning about `torchcodec`/FFmpeg not being
> installed correctly for built-in audio decoding — **this is NON-FATAL**. whisperx uses its
> own ffmpeg path. Ignore it.

> **Note:** torchcodec is not installed (it pulls an extra ~200MB FFmpeg wheel). Not needed.
> If a later pyannote error complains about audio decoding, load audio in-memory or re-run
> with the bundled ffmpeg on PATH.

---

## 8. HUGGINGFACE TOKEN (THE GATED-MODEL BLOCKER)

The pyannote diarization model `pyannote/speaker-diarization-3.1` is **gated** — you must
accept the license for **THREE** repos (the third is a hidden requirement that the model
card does NOT mention; missing it gives a confusing 403):

1. Sign in to https://huggingface.co
2. On EACH of these pages, click **"Agree and access repository"** (accept the license):
   - `https://huggingface.co/pyannote/speaker-diarization-3.1`  (main pipeline)
   - `https://huggingface.co/pyannote/segmentation-3.0`          (segmentation)
   - `https://huggingface.co/pyannote/speaker-diarization-community-1`  (⚠️ REQUIRED but
     **NOT listed on the model card** — a known trap; the 403 error it causes gives no hint)
3. Create an **Access Token** (Read) at https://huggingface.co/settings/tokens
   — copy the `hf_...` string.

> If you get `GatedRepoError: 403 ... "you are not in the authorized list"` for
> `speaker-diarization-community-1` even after accepting the other two — that's the hidden
> third repo. Accept its license (step 2, third bullet) and retry. This is a known pyannote
> 3.1 requirement the docs omit.

### Store it (do NOT hardcode in code or commit):
```powershell
python -m src.settings set-token hf_XXXXX
```
Confirms saved (gitignored). Verify masked:
```powershell
python -m src.settings show
```
> The settings module resolves token by: CLI `--token` → env `HF_TOKEN` → saved settings.json.
> It NEVER prints the full secret (only `hf_...` + length).

---

## 9. GENERATE TEST AUDIO

The repo ships a generator. If your machine has espeak-ng it makes two-speaker TTS audio;
**without espeak-ng it writes a pure-tone placeholder** (that tone won't exercise real
diarization well — better to use a real meeting recording).
```powershell
python tests\make_test_audio.py -o recordings\sample.wav
```
For a real proof, copy an actual meeting recording (`meeting.mp3/m4a/wav`) into `recordings\`.

---

## 10. RUN THE ONE-OFF TEST (CUDA)

```powershell
python src\diarize.py --audio recordings\sample.wav --device cuda --out out.json
```

Expected on success:
- torch loads on CUDA, no "cpu" fallback in logs
- transcript segments with `[SPEAKER_00]` / `[SPEAKER_01]` labels
- prints `Speakers: ['SPEAKER_00', 'SPEAKER_01']`
- writes `out.diarized.json` (or next to audio if no `--out`)

Common failures (and fixes):
| Symptom | Cause | Fix |
|---|---|---|
| `torch.cuda.is_available()` False | CPU torch wheel | reinstall torch with cu128/cu124 index (§7) |
| `WinError 126` c10.dll | VC++ redist missing | install §4, new shell |
| `WinError 2` ffmpeg | ffmpeg not on PATH | do §5, new shell |
| `GatedRepoError: 401/403` fetching pyannote model | token missing OR a gated dep not accepted | do §8 fully (incl. the hidden `speaker-diarization-community-1` repo) |
| `ImportError: attempted relative import` | ran via wrong python/path | run from project root, use `.venv311\Scripts\python.exe` |
| Out of memory / CUDA OOM | 8GB over 20min clip | add `--batch-size 8` (whisperx batching) |

> `--device cuda` uses `compute_type="float16"` (diarize.py picks this automatically).
> `--device cpu` uses int8 and is much slower — RTX is the intended path.

> **Speaker-count hints** (all optional): pyannote's AUTOMATIC speaker-counting can be
> conservative on short clips (e.g. label everyone as one speaker on a <30s test wav). For
> meetings where you know the speaker count, pass a hint:
> ```powershell
> python src\diarize.py --audio meeting.mp3 --device cuda --num-speakers 2
> python src\diarize.py --audio meeting.mp3 --device cuda --min-speakers 2 --max-speakers 5
> ```
> On real human recordings (minutes long) auto-detection generally works; use hints only
> when you know the count or get an obvious under-segmentation.
> **Test-data caveat:** espeak-ng synthesized test audio (both speakers same TTS vocal tract)
> is a KNOWN hard case for diarization — even with 2 distinct-esque voices, both may collapse
> to one speaker. Don't judge the pipeline on espeak audio; judge it on a real recording.

---

## 11. RUN AS A WATCHDOG SERVICE (the production mode)

Watches a folder; every finished recording gets diarized and a JSON written next to it.

### Test it in the foreground first:
```powershell
python src\watchdog.py --watch C:\meetings --device cuda
```
Drop a recording into `C:\meetings` — you should see `[watchdog] diarizing <file>` then
`[watchdog] wrote <path>\<name>.json`.

### Install as a real service (survives reboots/login, runs headless):
Use **NSSM** (Non-Sucking Service Manager) — the standard for Python services on Windows:
```powershell
# download NSSM from https://nssm.cc/download
nssm install MeetilyDiarization "C:\Users\<you>\meetily-diarization-poc\.venv311\Scripts\python.exe" "C:\Users\<you>\meetily-diarization-poc\src\watchdog.py --watch C:\meetings --device cuda"
nssm set MeetilyDiarization AppDirectory "C:\Users\<you>\meetily-diarization-poc"
nssm set MeetilyDiarization AppEnvironmentExtra "HF_TOKEN=hf_XXXXX"   # or rely on settings.json
nssm start MeetilyDiarization
```
> Alternative: **Task Scheduler** at logon with the same command. NSSM is more robust for a
> headless background service.

> CRITICAL for production: the watchdog needs the **same ffmpeg on PATH** and **CUDA torch**
> from this doc. If you run it as a service under a different user, install the VC++ redist
> and ffmpeg for that user too, or set the service to run as your user.

---

## 12. MEETILY INTEGRATION (fork — the actual product)

This sidecar is the missing diarization layer for the Meetily fork. To wire it in:

1. **Point the watchdog at Meetily's recording storage dir.** Meetily saves recordings to
   its own storage folder; set `--watch` to that folder (or have Meetily copy finished
   files into the watched folder).
2. **Copy speaker labels into Meetily's SQLite `speaker` column.** Meetily already has an
   upstream migration for a `speaker` column — the watchdog's JSON output maps to it.
3. **Point Meetily's summary LLM at local Ollama** `http://localhost:11434` for
   local-first summaries (no cloud).

---

## 13. GPU NOTES (why this machine is the right one)

- **Transcription** in the stock Meetily installer uses **Vulkan/AVX2**, NOT CUDA — Meetily
  itself doesn't use the GPU for transcription.
- **This sidecar is where CUDA pays off**: pyannote + whisperx run on the RTX via CUDA.
- RTX 2000 Ada (8GB) is comfortably sufficient for whisperx `small` (or `medium` at
  ~8GB) + pyannote diarization on meeting-length audio. Use `--batch-size 16` default;
  drop to 8 if you hit OOM on long recordings.

---

## 14. TROUBLESHOOTING QUICK-REFERENCE

| Error | Meaning | Fix |
|---|---|---|
| `WinError 126` / c10.dll | VC++ redist missing | §4 |
| `[WinError 2] The system cannot find the file` | ffmpeg missing | §5 |
| `GatedRepoError: 401/403` | HF token missing OR a gated dep (`speaker-diarization-community-1`) not accepted | §8 |
| `ImportError: attempted relative import` | wrong python / not from root | use `.venv311\Scripts\python.exe` from project root |
| `torch.cuda.is_available()` False | CPU wheel | §7 CUDA torch reinstall |
| `FileNotFoundError: ffmpeg` at `imageio_ffmpeg` path | bundled exe named different | copy to `ffmpeg.exe` (§5) |

---

## FINAL CHECKLIST (tick these before calling it done)

- [ ] `nvidia-smi` shows RTX 2000 Ada + a recent CUDA version (≥ 12.x; yours is 13.2)
- [ ] `py -3.11 --version` → 3.11.x
- [ ] `ffmpeg -version` works in a new shell
- [ ] torch import shows `cuda True`
- [ ] whisperx, pyannote.audio, src imports all OK
- [ ] token saved via `python -m src.settings set-token hf_...`
- [ ] `python src\diarize.py --audio recordings\sample.wav --device cuda` → `SPEAKER_00/01`
- [ ] (production) watchdog service runs and diarizes a dropped file

---

## Why so many prerequisites? (context)

torch is heavy: the Windows CPU wheel is ~200MB, the CUDA wheel ~2.5GB, and it needs the
VC++ runtime. whisperx wraps faster-whisper (ctranslate2) for the transcription core and
shells out to ffmpeg for decoding. pyannote's diarization model is gated on HuggingFace and
won't work until you accept the license AND provide a token. Missing ANY of these produces
a confusing error — the step above that installs it is the fix.
