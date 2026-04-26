# voice-to-text

OpenAI Whisper を使った音声文字起こしツール。英語⇔日本語の翻訳にも対応しています。

[English README](README.md)

## 機能

- 音声ファイルの文字起こし（Whisper）
- 英語 → 日本語 翻訳（Google Translate）
- 日本語 → 英語 翻訳（Whisper の translate タスク）
- 出力フォーマット: `txt` / `srt` / `vtt` / `tsv` / `json`
- メモリ安全チェック（搭載メモリに応じてモデルを自動ダウングレード）
- 進捗表示モード: なし / プログレスバー / 詳細ログ

## 必要環境

- Python 3.9+
- [ffmpeg](https://ffmpeg.org/)（`ffprobe` が PATH に通っていること）

## インストール

```bash
pip install openai-whisper deep-translator tqdm psutil
```

## 使い方

```bash
python transcribe.py <音声ファイル> [オプション]
```

### 基本的な例

```bash
# デフォルト設定（base モデル、進捗なし、txt 出力）
python transcribe.py audio.m4a

# プログレスバーを表示
python transcribe.py audio.m4a --bar

# 詳細ログを表示
python transcribe.py audio.m4a --full

# large モデルで SRT 形式に出力
python transcribe.py audio.m4a --model large --format srt
```

### 翻訳を使う

```bash
# 英語音声 → 日本語テキスト
python transcribe.py audio.m4a --en2jp

# 日本語音声 → 英語テキスト
python transcribe.py audio.m4a --jp2en
```

出力ファイル名には翻訳モードのサフィックスが付きます（例: `audio_en2jp.txt`）。

## オプション一覧

| オプション | 説明 | デフォルト |
|---|---|---|
| `--model` | Whisper モデル (`tiny` / `base` / `small` / `medium` / `large` / `turbo`) | `base` |
| `--format` | 出力形式 (`txt` / `srt` / `vtt` / `tsv` / `json`) | `txt` |
| `--full` | 詳細ログを表示 | — |
| `--bar` | プログレスバーを表示 | — |
| `--none` | 出力を抑制 | ✓ |
| `--en2jp` | 英語 → 日本語 翻訳 | — |
| `--jp2en` | 日本語 → 英語 翻訳 | — |
| `--allow-unsafe-model` | メモリ安全チェックをスキップして指定モデルを強制使用 | — |

## モデルと必要メモリの目安

| モデル | 総メモリ | 空きメモリ | 備考 |
|---|---|---|---|
| tiny | 2 GiB | 1 GiB | 最軽量・高速 |
| base | 4 GiB | 2 GiB | デフォルト |
| small | 6 GiB | 3 GiB | |
| medium | 10 GiB | 6 GiB | |
| turbo | 12 GiB | 8 GiB | |
| large | 16 GiB | 10 GiB | 最高精度 |

メモリが不足している場合、自動的に小さいモデルへフォールバックします。  
強制的に指定モデルを使う場合は `--allow-unsafe-model` を付けてください。

## 出力ファイル

入力ファイルと同じディレクトリに保存されます。

| ケース | 出力ファイル名 |
|---|---|
| 通常の文字起こし | `<元ファイル名>.txt` |
| `--en2jp` 翻訳 | `<元ファイル名>_en2jp.txt` |
| `--jp2en` 翻訳 | `<元ファイル名>_jp2en.txt` |

## 依存ライブラリ

| ライブラリ | 用途 | 必須 |
|---|---|---|
| `openai-whisper` | 音声認識・文字起こし | ✅ |
| `deep-translator` | 英日翻訳（en2jp） | ✅ |
| `tqdm` | プログレスバー表示 | オプション |
| `psutil` | メモリ情報の取得 | オプション |
| `ffmpeg` | 音声ファイルの読み込み | ✅（外部ツール） |
