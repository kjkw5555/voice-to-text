# voice-to-text

OpenAI Whisper を使った音声文字起こしツール。英語⇔日本語の翻訳にも対応しています。

[English README](README.md)

## 機能

- 音声ファイルの文字起こし（Whisper）
- Apple Silicon GPU バックエンド（[mlx-whisper](https://pypi.org/project/mlx-whisper/)、インストール済みなら自動選択）
- フォルダ指定で複数ファイルを一括処理（モデルは1回だけロード）
- URL（YouTube等）を直接指定して転写（yt-dlp で音声トラックのみダウンロード）
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
pip install -r requirements.txt
```

## 使い方

```bash
python transcribe.py <音声ファイル | フォルダ | URL> [オプション]
```

### 基本的な例

```bash
# デフォルト設定（base モデル、プログレスバー表示、txt 出力）
python transcribe.py audio.m4a

# プログレスバーを明示的に指定
python transcribe.py audio.m4a --bar

# 詳細ログを表示
python transcribe.py audio.m4a --full

# large モデルで SRT 形式に出力
python transcribe.py audio.m4a --model large --format srt
```

### フォルダの一括処理

フォルダを指定すると、中の音声ファイルをまとめて処理します。

```bash
python transcribe.py ./recordings --model small
```

- モデルは最初に1回だけロードされ、全ファイルで使い回されます。
- 途中のファイルでエラーが発生しても処理は継続し、最後に失敗した
  ファイルの一覧を表示します（失敗があった場合の終了コードは 1）。

### URL から転写する

URL（YouTube等）を渡すと、ダウンロードと転写を一気に実行します。
[yt-dlp](https://github.com/yt-dlp/yt-dlp)（`brew install yt-dlp`）が必要です。

```bash
python transcribe.py "https://www.youtube.com/watch?v=..." --model turbo --en2jp
```

ダウンロードするのは音声トラックのみです（映像は取得しません）。音声ファイルは
動画タイトル名でカレントディレクトリに保存され、転写結果はその隣に出力されます。

### 翻訳を使う

```bash
# 英語音声 → 日本語テキスト
python transcribe.py audio.m4a --en2jp

# 日本語音声 → 英語テキスト
python transcribe.py audio.m4a --jp2en
```

出力ファイル名には翻訳モードのサフィックスが付きます（例: `audio_en2jp.txt`）。

`--en2jp` の翻訳は一時的な通信エラーに対して自動でリトライします。
それでも翻訳に失敗した場合は、文字起こし結果を失わないように
原文のままサフィックスなし（例: `audio.txt`）で保存されます。

## オプション一覧

| オプション | 説明 | デフォルト |
|---|---|---|
| `--backend` | バックエンド (`auto` / `openai` / `mlx`)。`auto` は mlx（Apple Silicon GPU）があれば mlx を選択 | `auto` |
| `--model` | Whisper モデル (`tiny` / `base` / `small` / `medium` / `large` / `turbo`) | `base` |
| `--format` | 出力形式 (`txt` / `srt` / `vtt` / `tsv` / `json`) | `txt` |
| `--full` | 詳細ログを表示 | — |
| `--bar` | プログレスバーを表示 | ✓ |
| `--none` | すべての出力を抑制 | — |
| `--en2jp` | 英語 → 日本語翻訳を実行 | — |
| `--jp2en` | 日本語 → 英語翻訳を実行 | — |
| `--allow-unsafe-model` | メモリ安全チェックをスキップし、指定モデルを強制使用 | — |
| `--models-dir` | モデルの保存先ディレクトリを指定 | 環境変数 `WHISPER_MODELS_DIR`、なければ `./models` |
| `--skip-update` | モデルファイルが存在する場合、更新チェックをスキップ | — |


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
| `--en2jp` で翻訳に失敗 | `<元ファイル名>.txt`（原文のまま保存） |

## 依存ライブラリ

| ライブラリ | 用途 | 必須 |
|---|---|---|
| `openai-whisper` | 音声認識・文字起こし | ✅ |
| `deep-translator` | 英日翻訳（en2jp） | ✅ |
| `tqdm` | プログレスバー表示 | オプション |
| `psutil` | メモリ情報の取得 | オプション |
| `mlx-whisper` | Apple Silicon GPU バックエンド（M系Macで最良の品質/速度） | オプション |
| `ffmpeg` | 音声ファイルの読み込み | ✅（外部ツール） |
| `yt-dlp` | URL入力（音声ダウンロード） | オプション（外部ツール） |

上記のメモリ要件表は `openai` バックエンド（CPU）向けです。`mlx` バックエンドは
fp16 の重みを unified memory に置くため必要メモリが大幅に少なく、`turbo` でも
空きメモリ 2 GiB 程度で動作します。

## 開発

```bash
pytest
```
