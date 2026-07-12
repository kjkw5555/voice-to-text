# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

`transcribe.py` is a single-file CLI tool that transcribes audio via OpenAI Whisper, with optional
English↔Japanese translation. There is no package structure — everything lives in this one script plus
its test suite.

## Commands

Install dependencies:
```bash
pip install -r requirements.txt
```

Run the tool:
```bash
python transcribe.py <audio_file> [options]
```

Run all tests:
```bash
pytest
```

Run a single test file / test:
```bash
pytest tests/test_model_management.py
pytest tests/test_model_management.py::test_verify_model_hash_valid
```

There is no lint/format tooling configured in this repo.

## Architecture

Everything is in `transcribe.py`, organized into a few functional groups:

- **Memory safety guard** (`MODEL_MEMORY_REQUIREMENTS_GB`, `get_memory_info`, `model_fits_memory`,
  `choose_safe_model`): before loading a Whisper model, the script checks total/available RAM
  (via `psutil` if installed, else `sysctl`/`sysconf` fallbacks for macOS/Linux) and silently
  downgrades to the largest model in `MODEL_ORDER` that fits, unless `--allow-unsafe-model` is passed.
- **Local model persistence** (`ensure_model_exists`, `verify_model_hash`, `is_internet_available`):
  models are cached under `./models` (configurable via `--models-dir`) instead of Whisper's default
  cache dir. On each run, if internet is available, the local file's SHA256 is checked against the
  hash embedded in Whisper's `_MODELS` download URL, and it's re-downloaded if missing/corrupt/stale.
  If offline, the cached file is used as-is; `--skip-update` skips the hash check entirely when the
  file already exists. The verified file path is then passed to `whisper.load_model(path)` directly —
  loading by model *name* would make whisper re-read the whole file into memory for its own SHA256
  check, duplicating the one already done. See `plan/2026-05-08_local-model-persistence.md` for the
  original design.
- **Transcription/translation core** (`transcribe_audio`, `translate_text`, `translate_segments`,
  `detect_audio_language`): `--jp2en` uses Whisper's native `translate` task; `--en2jp` runs a normal
  `transcribe` pass and then translates each segment independently via `deep-translator`'s
  `GoogleTranslator` (segment-level, not whole-text, so timestamps in `srt`/`vtt`/`tsv` outputs stay
  aligned with the translated text). Output is written using Whisper's own `get_writer`, so all of
  Whisper's formats (`txt`/`srt`/`vtt`/`tsv`/`json`) work automatically for both raw and translated
  results. Output files are written next to the input, with `_en2jp`/`_jp2en` appended to the base
  name when translation is used.
- **Progress display** (`mode`: `none` / `bar` / `full`): maps directly onto whisper's `verbose`
  parameter — `None` (fully silent), `False` (whisper's built-in tqdm progress bar), `True` (verbose
  log). There is no custom progress bar. `detect_audio_language` runs an extra language-ID pass up
  front only when `mode` is `bar` or `full`, purely to print the detected language before
  transcription starts.
- **CLI entrypoint** (`build_parser()` / `main(argv)`): when the input path is a directory, all
  matching files in `AUDIO_EXTENSIONS` are found, the Whisper model is loaded once via `load_model`,
  and then reused across files (`transcribe_audio(..., model=shared_model, ...)`) rather than reloading
  per file. A failure in one file doesn't stop the batch; `main` returns 1 if any file failed.

## Testing conventions

Tests mock `whisper.load_model`, `os.path.exists`, and network calls (`transcribe.is_internet_available`,
`whisper._download`) rather than touching real models or the network — follow this pattern for new tests
so the suite stays fast and offline-safe.
