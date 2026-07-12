# HANDOFF

次のセッション/作業者への引き継ぎメモ。2026-07-12 時点。

## 現状サマリー

- テスト 19/19 通過。堅牢性・表示・効率の「守り」の改善は完了し、`main` は origin に push 済み（`a33e93b`）。
- 実機検証のレシピは `.claude/skills/verify/SKILL.md` にあり（`say` でテスト音声生成、死んだプロキシで翻訳失敗を再現、など）。

### 直近で完了した作業

1. 滞留していた未コミット作業の整理・コミット（フォルダ一括処理、デフォルト `--bar`、モデルキャッシュファイル名のバグ修正）
2. 堅牢性: 翻訳失敗時に文字起こし結果をサフィックスなしで保存（結果を失わない）、Google翻訳のリトライ、バッチで1ファイル失敗しても継続（失敗一覧+exit 1）
3. `--none` を本当に無音に（whisper の `verbose` は None/False/True で意味が違う）、偽プログレスバーを廃止し whisper 内蔵バーに一本化
4. モデルをファイルパスで `whisper.load_model()` に渡し、whisper 側の二重 SHA256 検証（large で約3GBのメモリ読み込み）を回避
5. `build_parser()` / `main(argv)` 抽出で CLI をテスト可能に

## 重要な前提（調査で判明した実態）

- **このツールの真のボトルネックは転写品質。** 実際の成果物（`名称未設定フォルダ/` の英語トーク転写）は冒頭から gibberish。
- マシンは Apple M4 / 16GB unified memory だが、空きRAMが常時2〜3GBのためメモリガードが base/tiny に落としており、品質が出ない状態が定常化している。
- 利用実態はパイプラインの一部: YouTube英語AIトーク（yt-dlp由来のファイル名）→ 転写 → 日本語翻訳 → transcript-council-summary スキルで要約。転写品質が下流すべてを律速する。

## ロードマップ（優先順）

### ① バックエンド換装【最優先】

openai-whisper の CPU/fp32 実行が品質の根本制約。`--backend` オプションで以下のいずれかを追加し、同じマシンで large-v3-turbo 級の品質を出す:

| 選択肢 | 特徴 |
|---|---|
| mlx-whisper | Apple MLX製。M4 で large-v3-turbo が実用速度。macOS専用 |
| faster-whisper | CTranslate2製。int8 でメモリ約1/4・4〜8倍速。クロスプラットフォーム、単語タイムスタンプ対応 |

- 既存 openai-whisper はフォールバックとして残す
- `MODEL_MEMORY_REQUIREMENTS_GB` はバックエンド別に実測で作り直す
- **着手はプロトタイプ比較から**: 手元の音声で base（現状） vs large-v3-turbo を品質・速度・メモリで実測

### ② yt-dlp 統合

URL を直接渡して DL→転写を1ステップに。ファイル名は動画タイトルから生成。

### ③ 翻訳の LLM 化

deep-translator は非公式Googleエンドポイント（脆い・技術用語に弱い・セグメント単位で文脈が切れる）。`--translator claude` を追加し Claude API (Haiku) で翻訳（1時間トークで数十円程度）。

### ④ --skip-existing

バッチで出力済みファイルをスキップ（resume）。実装コスト最小。①のモデル変更後の再処理でも有効。

### ⑤ 中期（必要になったら）

- 話者分離（pyannote / whisperX）— 対談が多いので価値は高いが依存が重い。①の後
- GitHub Actions CI（pytest を macos + ubuntu で）
- pyproject.toml 化・ファイル分割 — ①でバックエンド抽象化を入れて単一ファイルが限界になった時に同時に

### やらないこと

GUI化、PyPI公開などの過剰パッケージング、自前プログレスバーの復活。

## 既知の小さい課題（未対応）

- 翻訳失敗時のフォールバック保存は、既存の同名 `<input>.txt` を上書きする
- オンライン時は毎回モデルのフル SHA256 検証が走る（largeで数秒〜十数秒）。間引き（1日1回等）またはサイズ比較の先行で軽減可能
- 言語検出は bar/full モードのみ実行して `language=` に渡す設計（none モードは whisper 内部検出に任せる）— 結果はほぼ同じだが検出の mel 計算が二重
- `dummy.txt` が何かのツールにより繰り返し生成される（gitignore 済み、正体不明）
