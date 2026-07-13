---
name: verify
description: How to verify transcribe.py changes end-to-end without real recordings or manual setup.
---

# Verifying transcribe.py

CLI surface. No build step. Use the `tiny` model (~72MB, cached in `./models/` after first run).

## Generate test audio (macOS)

```bash
say -o /tmp/verify/valid.aiff "Hello, this is a test of the transcription system."
head -c 2048 /dev/urandom > /tmp/verify/corrupt.mp3   # invalid audio for error paths
```

## Drive it

```bash
# Single file
python3 transcribe.py /tmp/verify/valid.aiff --model tiny --skip-update --bar

# Batch (folder) — corrupt file should error, batch should continue, exit 1
python3 transcribe.py /tmp/verify --model tiny --skip-update --bar

# Translation failure path: point HTTPS at a dead proxy so only
# Google Translate fails (whisper model is local, is_internet_available
# uses a raw socket and ignores the proxy)
https_proxy=http://127.0.0.1:9 python3 transcribe.py /tmp/verify/valid.aiff \
    --model tiny --en2jp --skip-update --bar

# URL input (19-second video, downloads audio to CWD)
python3 transcribe.py "https://www.youtube.com/watch?v=jNQXAC9IVRw" --model tiny --bar
```

## Gotchas

- The tiny model often misdetects `say`-generated English audio as Japanese
  (transcribes to katakana). That's model quality, not a bug in the script.
- `--none` still prints whisper's own "Detected language:" line and progress
  bar because `verbose=False` (whisper is silent only with `verbose=None`).
- Output files land next to the input audio, not in the repo.
