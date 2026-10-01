"""Apply speakers from a .diarized.json to readable transcript outputs.

Bridges the sidecar (WhisperX + pyannote) to humans and to Meetily's DB:

  python src/apply_speakers.py --json recordings/meeting.diarized.json

Outputs next to the JSON:
  <name>.labeled.srt         - SRT with [SPEAKER_x] tags
  <name>.labeled.txt         - plain text "SPEAKER_x: text" lines
  <name>.speakers.json       - speaker-id -> display-name mapping (GITIGNORED-ish, editable)

Optional Meetily DB write:
  python src/apply_speakers.py --json ... --db <meetily.sqlite> [--meeting-id <id>]
    Updates the transcripts table: every segment that overlaps a diarized segment
    gets its `speaker` column set to the label. Requires the migration that adds
    `speaker TEXT` to transcripts (present upstream as of 2025-11).

Run with the project venv: .venv311\\Scripts\\python.exe src\\apply_speakers.py ...
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

SRT_OK = True  # no third-party deps needed; stdlib only

def load_diarized(json_path: Path) -> dict:
    with open(json_path) as f:
        return json.load(f)


def write_srt(segments, out_srt: Path) -> None:
    def _t(sec: float) -> str:
        ms = int((sec - int(sec)) * 1000)
        h, rem = divmod(int(sec), 3600)
        m, s = divmod(rem, 60)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    lines = []
    for i, seg in enumerate(segments, 1):
        start, end = _t(seg["start"]), _t(seg["end"])
        lines.append(f"{i}\n{start} --> {end}\n[{seg.get('speaker','UNK')}]\n{seg['text'].strip()}\n")
    out_srt.write_text("\n".join(lines), encoding="utf-8")


def write_txt(segments, out_txt: Path) -> None:
    lines = []
    for seg in segments:
        spk = seg.get("speaker", "UNK")
        txt = seg["text"].strip()
        lines.append(f"[{spk}] {txt}")
    out_txt.write_text("\n".join(lines), encoding="utf-8")


def write_speakers_map(diarized: dict, out_map: Path) -> None:
    # default display name = the raw label; user edits this file to rename
    labels = diarized.get("speakers", []) or [s for s in {sg.get("speaker") for sg in diarized.get("segments", [])} if s]
    mapping = {lab: {"name": lab} for lab in labels}
    out_map.write_text(json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def apply_to_meetily_db(diarized: dict, db_path: Path, meeting_id: str | None) -> int:
    """Set `speaker` on transcripts rows that overlap diarized segments.

    Returns number of rows updated. Requires `speaker TEXT` column (upstream migration
    20251110000001_add_speaker_field.sql). Meeting scoped by optional --meeting-id.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        # verify column exists
        cols = [r[1] for r in conn.execute("PRAGMA table_info(transcripts)").fetchall()]
        if "speaker" not in cols:
            print("ERROR: transcripts table has no `speaker` column; run the migration "
                  "20251110000001_add_speaker_field.sql first.", file=sys.stderr)
            return -1
        updated = 0
        q = "UPDATE transcripts SET speaker=? WHERE speaker IS NULL AND audio_start_time IS NOT NULL "
        if meeting_id:
            q += "AND meeting_id=?"
        q += "AND audio_start_time BETWEEN ? AND ?"
        for seg in diarized.get("segments", []):
            # pad a little to catch segment-boundary overlap
            lo = max(0.0, seg["start"] - 0.05)
            hi = seg["end"] + 0.05
            params = [seg.get("speaker", "UNK")]
            if meeting_id:
                params.append(meeting_id)
            params += [lo, hi]
            cur = conn.execute(q, params)
            updated += cur.rowcount
        conn.commit()
        return updated
    finally:
        conn.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Apply speaker labels from .diarized.json to readable outputs")
    ap.add_argument("--json", required=True, help="path to *.diarized.json from the sidecar")
    ap.add_argument("--db", default=None, help="optional Meetily sqlite DB path to update")
    ap.add_argument("--meeting-id", default=None, help="scope DB update to one meeting")
    args = ap.parse_args(argv)

    json_path = Path(args.json)
    if not json_path.exists():
        print(f"ERROR: {json_path} not found", file=sys.stderr)
        return 1

    d = load_diarized(json_path)
    segments = d.get("segments", [])
    base = json_path.with_suffix("")  # strips .diarized.json -> .diarized

    srt = json_path.with_suffix(".labeled.srt")
    txt = json_path.with_suffix(".labeled.txt")
    mapf = json_path.with_suffix(".speakers.json")

    write_srt(segments, srt)
    write_txt(segments, txt)
    write_speakers_map(d, mapf)
    print(f"Wrote {srt}")
    print(f"Wrote {txt}")
    print(f"Wrote {mapf}  (edit this file to rename speakers)")

    if args.db:
        db = Path(args.db)
        if not db.exists():
            print(f"ERROR: db {db} not found", file=sys.stderr)
            return 2
        n = apply_to_meetily_db(d, db, args.meeting_id)
        print(f"DB update: {n} transcript row(s) labeled (db={db})")

    # quick preview
    print("--- preview ---")
    for seg in segments[:8]:
        print(f"[{seg.get('speaker','UNK')}] {seg['text'].strip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
