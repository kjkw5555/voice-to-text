# voice-to-text

Audio transcription tool powered by OpenAI Whisper, with English ↔ Japanese translation support.

[日本語版はこちら](README.ja.md)

## Features

- Audio transcription via Whisper
- Apple Silicon GPU backend via [mlx-whisper](https://pypi.org/project/mlx-whisper/), auto-selected when installed
- Batch processing of a whole folder (model is loaded only once)
- English → Japanese translation (Google Translate)
- Japanese → English translation (Whisper translate task)
- Multiple output formats: `txt` / `srt` / `vtt` / `tsv` / `json`
- Memory safety guard (auto-downgrades model when RAM is insufficient)
- Progress display modes: none / progress bar / verbose log

## Requirements

- Python 3.9+
- [ffmpeg](https://ffmpeg.org/) (`ffprobe` must be available in PATH)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python transcribe.py <audio_file_or_folder> [options]
```

### Basic examples

```bash
# Default (base model, progress bar, txt format)
python transcribe.py audio.m4a

# Explicitly show progress bar
python transcribe.py audio.m4a --bar

# Show verbose log
python transcribe.py audio.m4a --full

# Use large model and output as SRT
python transcribe.py audio.m4a --model large --format srt
```

### Batch processing a folder

Pass a folder to process all audio files inside it.

```bash
python transcribe.py ./recordings --model small
```

- The model is loaded once and reused for every file.
- If one file fails, the remaining files are still processed; failed
  files are listed at the end (exit code 1 if there were failures).

### Translation

```bash
# English audio → Japanese text
python transcribe.py audio.m4a --en2jp

# Japanese audio → English text
python transcribe.py audio.m4a --jp2en
```

The translation mode is appended to the output filename (e.g. `audio_en2jp.txt`).

`--en2jp` translation automatically retries transient network errors.
If translation still fails, the original transcription is saved without
the suffix (e.g. `audio.txt`) so the result is never lost.

## Options

| Option | Description | Default |
|---|---|---|
| `--backend` | Whisper backend (`auto` / `openai` / `mlx`). `auto` picks mlx (Apple Silicon GPU) when installed | `auto` |
| `--model` | Whisper model (`tiny` / `base` / `small` / `medium` / `large` / `turbo`) | `base` |
| `--format` | Output format (`txt` / `srt` / `vtt` / `tsv` / `json`) | `txt` |
| `--full` | Show verbose log | — |
| `--bar` | Show progress bar | ✓ |
| `--none` | Suppress all output | — |
| `--en2jp` | Translate English → Japanese | — |
| `--jp2en` | Translate Japanese → English | — |
| `--allow-unsafe-model` | Skip memory safety check and force the requested model | — |
| `--models-dir` | Directory to save Whisper models | `WHISPER_MODELS_DIR` env var, or `./models` |
| `--skip-update` | Skip checking for model updates if file exists | — |

## Model Memory Requirements

| Model | Total RAM | Available RAM | Notes |
|---|---|---|---|
| tiny | 2 GiB | 1 GiB | Fastest, lightest |
| base | 4 GiB | 2 GiB | Default |
| small | 6 GiB | 3 GiB | |
| medium | 10 GiB | 6 GiB | |
| turbo | 12 GiB | 8 GiB | |
| large | 16 GiB | 10 GiB | Highest accuracy |

When RAM is insufficient, the script automatically falls back to a smaller model.  
Use `--allow-unsafe-model` to force the requested model regardless of available memory.

## Output Files

Output is saved in the same directory as the input file.

| Case | Output filename |
|---|---|
| Transcription only | `<input_name>.txt` |
| `--en2jp` | `<input_name>_en2jp.txt` |
| `--jp2en` | `<input_name>_jp2en.txt` |
| `--en2jp` with failed translation | `<input_name>.txt` (original text) |

## Dependencies

| Library | Purpose | Required |
|---|---|---|
| `openai-whisper` | Speech recognition & transcription | ✅ |
| `deep-translator` | English → Japanese translation | ✅ |
| `tqdm` | Progress bar display | Optional |
| `psutil` | Memory usage detection | Optional |
| `mlx-whisper` | Apple Silicon GPU backend (best quality/speed on M-series Macs) | Optional |
| `ffmpeg` | Audio file decoding | ✅ (external) |

The memory requirement table above applies to the `openai` backend (CPU).
The `mlx` backend keeps fp16 weights in unified memory and needs far less RAM
(e.g. `turbo` runs in roughly 2 GiB of available memory).

## Development

```bash
pytest
```
