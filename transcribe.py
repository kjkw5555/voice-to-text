import whisper
import os
import time
import argparse
import subprocess
import platform
import socket
import hashlib
from whisper.utils import get_writer
from whisper.tokenizer import LANGUAGES
from deep_translator import GoogleTranslator

try:
    import psutil
except ImportError:
    psutil = None

MODEL_MEMORY_REQUIREMENTS_GB = {
    "tiny": {"total": 2, "available": 1},
    "base": {"total": 4, "available": 2},
    "small": {"total": 6, "available": 3},
    "medium": {"total": 10, "available": 6},
    "large": {"total": 16, "available": 10},
    "turbo": {"total": 12, "available": 8},
}

MODEL_ORDER = ["tiny", "base", "small", "medium", "turbo", "large"]

# mlx バックエンド用。fp16 重みが unified memory に載るため CPU 版より要件が緩い。
# 実測: turbo でピーク RSS 約0.7GB + GPU 割当（HANDOFF.md のベンチ参照）
MLX_MODEL_MEMORY_REQUIREMENTS_GB = {
    "tiny": {"total": 2, "available": 0.5},
    "base": {"total": 2, "available": 0.5},
    "small": {"total": 4, "available": 1},
    "medium": {"total": 6, "available": 2},
    "large": {"total": 8, "available": 4},
    "turbo": {"total": 8, "available": 2},
}

MLX_MODEL_REPOS = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large": "mlx-community/whisper-large-v3-mlx",
    "turbo": "mlx-community/whisper-large-v3-turbo",
}

AUDIO_EXTENSIONS = {".mp3", ".mp4", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".webm", ".aac", ".wma", ".aiff"}

# モデル保存先の優先順位: 環境変数 WHISPER_MODELS_DIR > 外付けSSD（マウント時）> ./models
# 内蔵ストレージの空きが少ないため、モデルは基本的に外付けSSDに置く。
EXTERNAL_MODELS_DIR = "/Volumes/SUNEAST_SE900SSD2T/Whispers"
MODELS_DIR = os.environ.get("WHISPER_MODELS_DIR") or (
    EXTERNAL_MODELS_DIR
    if os.path.isdir(EXTERNAL_MODELS_DIR)
    else os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
)

# HFキャッシュ（mlx等のモデル置き場）もモデルディレクトリ配下に。
# huggingface_hub は import 時に HF_HUB_CACHE を読むため、mlx_whisper を
# import する前（= モジュール読み込み時）に設定しておく必要がある。
os.environ.setdefault("HF_HUB_CACHE", os.path.join(MODELS_DIR, "huggingface", "hub"))


def is_internet_available(host="8.8.8.8", port=53, timeout=3):
    """
    インターネット接続を確認します。
    """
    try:
        socket.create_connection((host, port), timeout=timeout)
        return True
    except (socket.timeout, socket.error):
        return False


def verify_model_hash(file_path, expected_sha256):
    """
    ファイルのSHA256ハッシュを確認します。
    """
    if not os.path.exists(file_path):
        return False

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest() == expected_sha256


def ensure_model_exists(model_name, download_root, skip_update=False):
    """
    モデルがローカルに存在するか確認し、必要に応じてダウンロードまたは更新します。
    """
    os.makedirs(download_root, exist_ok=True)

    # whisperのモデルURLとハッシュを取得
    from whisper import _MODELS
    url = _MODELS.get(model_name)
    if not url:
        raise ValueError(f"Unknown model name: {model_name}")

    # URLからハッシュを抽出（例: https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c002f23d4706596350711913917d23d922c07621453b342416f06a1/tiny.pt）
    expected_sha256 = url.split("/")[-2] if "/" in url else None

    file_path = os.path.join(download_root, os.path.basename(url))

    exists = os.path.exists(file_path)

    if exists and skip_update:
        return file_path

    # インターネットがある場合は最新チェック
    if is_internet_available():
        # ハッシュチェック
        if not exists or (expected_sha256 and not verify_model_hash(file_path, expected_sha256)):
            print(f"Downloading/Updating Whisper model '{model_name}' to {download_root}...")
            from whisper import _download
            _download(url, download_root, in_memory=False)
    elif not exists:
        raise RuntimeError(f"Model '{model_name}' not found locally and no internet connection.")

    return file_path


def bytes_to_gb(value):
    """バイト数をGiB単位に変換します。"""
    if value is None:
        return None
    return value / (1024 ** 3)


def format_gb(value):
    """GiB表記の文字列を返します。"""
    if value is None:
        return "unknown"
    return f"{value:.1f} GiB"


def get_total_memory_bytes():
    """総メモリ容量を取得します。"""
    if psutil is not None:
        try:
            return psutil.virtual_memory().total
        except Exception:
            pass

    system = platform.system()

    if system == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            return int(result.stdout.strip())
        except Exception:
            return None

    if system == "Linux":
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            phys_pages = os.sysconf("SC_PHYS_PAGES")
            return page_size * phys_pages
        except (ValueError, OSError, AttributeError):
            return None

    return None


def get_available_memory_bytes():
    """現在利用可能なメモリ容量を取得します。"""
    if psutil is not None:
        try:
            return psutil.virtual_memory().available
        except Exception:
            return None
    return None


def get_memory_info():
    """総メモリ・空きメモリ情報を返します。"""
    total_bytes = get_total_memory_bytes()
    available_bytes = get_available_memory_bytes()
    return {
        "total_bytes": total_bytes,
        "available_bytes": available_bytes,
        "total_gb": bytes_to_gb(total_bytes),
        "available_gb": bytes_to_gb(available_bytes),
    }


def model_fits_memory(model_name, memory_info, requirements=MODEL_MEMORY_REQUIREMENTS_GB):
    """モデルが現在のメモリ条件に対して安全かどうかを返します。"""
    requirement = requirements[model_name]
    total_gb = memory_info["total_gb"]
    available_gb = memory_info["available_gb"]

    if total_gb is not None and total_gb < requirement["total"]:
        return False

    if available_gb is not None and available_gb < requirement["available"]:
        return False

    return True


def choose_safe_model(requested_model, allow_unsafe_model=False, requirements=MODEL_MEMORY_REQUIREMENTS_GB):
    """
    現在のメモリ状況に応じて安全なモデルを選びます。
    """
    memory_info = get_memory_info()

    if allow_unsafe_model:
        return requested_model, memory_info, None

    if model_fits_memory(requested_model, memory_info, requirements):
        return requested_model, memory_info, None

    requested_index = MODEL_ORDER.index(requested_model)
    for candidate in reversed(MODEL_ORDER[:requested_index]):
        if model_fits_memory(candidate, memory_info, requirements):
            return candidate, memory_info, (
                f"Requested model '{requested_model}' may exceed safe memory limits. "
                f"Falling back to '{candidate}'."
            )

    return None, memory_info, (
        f"Requested model '{requested_model}' is not safe on this machine, "
        "and no smaller model meets the configured safety threshold."
    )

def translate_text(text, target_lang="ja", max_retries=3, retry_wait_seconds=2):
    """テキストを翻訳します（長文対応のため分割して処理）"""
    translator = GoogleTranslator(source='auto', target=target_lang)
    # GoogleTranslator は一度に5000文字までなので、必要に応じて分割
    max_chars = 4500
    chunks = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
    translated_chunks = []
    for chunk in chunks:
        for attempt in range(max_retries):
            try:
                translated_chunks.append(translator.translate(chunk))
                break
            except Exception:
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_wait_seconds * (attempt + 1))
    return "".join(translated_chunks)


def translate_segments(result, target_lang="ja"):
    """セグメント単位で翻訳し、出力用の text / segments を揃えます。"""
    translated_segments = []

    for segment in result.get("segments", []):
        original_text = segment.get("text", "")
        translated_text = translate_text(original_text, target_lang=target_lang) if original_text.strip() else original_text
        updated_segment = dict(segment)
        updated_segment["text"] = translated_text
        translated_segments.append(updated_segment)

    if translated_segments:
        result["segments"] = translated_segments
        result["text"] = "".join(segment["text"] for segment in translated_segments).strip()
    else:
        result["text"] = translate_text(result.get("text", ""), target_lang=target_lang)

    return result


def detect_audio_language(model, file_path):
    """音声の冒頭から言語を検出し、言語コードと表示名を返します。"""
    audio = whisper.load_audio(file_path)
    audio = whisper.pad_or_trim(audio)
    mel = whisper.log_mel_spectrogram(
        audio,
        n_mels=model.dims.n_mels,
    ).to(model.device)
    _, probabilities = model.detect_language(mel)
    language_code = max(probabilities, key=probabilities.get)
    language_name = LANGUAGES.get(language_code, language_code).title()
    return language_code, language_name


def resolve_backend(backend="auto"):
    """バックエンド指定を解決します。auto は mlx が使える環境なら mlx を選びます。"""
    if backend != "auto":
        return backend
    try:
        import mlx_whisper  # noqa: F401
        return "mlx"
    except ImportError:
        return "openai"


class MlxWhisperModel:
    """mlx-whisper を openai-whisper のモデルと同じ形で使うためのアダプタ。"""

    backend_name = "mlx"

    def __init__(self, repo):
        self.repo = repo

    def transcribe(self, file_path, fp16=None, **kwargs):
        import mlx_whisper
        # fp16 は mlx では意味を持たないため無視。None のオプションは mlx 側の既定に任せる
        options = {k: v for k, v in kwargs.items() if v is not None}
        return mlx_whisper.transcribe(file_path, path_or_hf_repo=self.repo, **options)


def load_model(
    model_name="base",
    allow_unsafe_model=False,
    models_dir=None,
    skip_update=False,
    mode="none",
    backend="auto",
):
    """モデルをロードして返します。フォルダ処理時に使い回せます。"""
    actual_models_dir = models_dir or MODELS_DIR
    resolved_backend = resolve_backend(backend)

    requirements = (
        MLX_MODEL_MEMORY_REQUIREMENTS_GB
        if resolved_backend == "mlx"
        else MODEL_MEMORY_REQUIREMENTS_GB
    )
    safe_model_name, memory_info, safety_message = choose_safe_model(
        model_name,
        allow_unsafe_model=allow_unsafe_model,
        requirements=requirements,
    )

    if mode != "none":
        print(
            "Memory check:"
            f" total={format_gb(memory_info['total_gb'])},"
            f" available={format_gb(memory_info['available_gb'])}"
        )

    if safety_message:
        print(f"Safety guard: {safety_message}")

    if safe_model_name is None:
        print("Aborted before model load to avoid system instability.")
        print("Use a smaller --model or pass --allow-unsafe-model to override.")
        return None, None

    if resolved_backend == "mlx":
        try:
            import mlx_whisper  # noqa: F401
        except ImportError:
            print("Error: --backend mlx requires mlx-whisper (pip install mlx-whisper).")
            return None, None
        repo = MLX_MODEL_REPOS[safe_model_name]
        if mode != "none":
            print(f"Using mlx-whisper model '{repo}'...")
        return MlxWhisperModel(repo), safe_model_name

    try:
        model_path = ensure_model_exists(safe_model_name, actual_models_dir, skip_update=skip_update)
    except RuntimeError as e:
        print(f"Error: {e}")
        return None, None

    if mode != "none":
        print(f"Loading Whisper model '{safe_model_name}' from {actual_models_dir}...")
    # モデル名ではなくファイルパスで渡す。名前で渡すと whisper が毎回
    # ファイル全体をメモリに読み込んで SHA256 を再検証するため
    # （検証は ensure_model_exists 側で済んでいる）。
    model = whisper.load_model(model_path)
    return model, safe_model_name


def transcribe_audio(
    file_path,
    mode="none",
    model_name="base",
    translation_mode=None,
    output_format="txt",
    allow_unsafe_model=False,
    models_dir=None,
    skip_update=False,
    model=None,
    item_index=1,
    item_total=1,
    backend="auto",
):
    """
    音声ファイルを読み込み、文字起こしを実行して結果をファイルに保存します。
    model を渡すとモデルロードをスキップします（フォルダ処理時の使い回し用）。
    """
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        return

    start_time = time.time()

    actual_models_dir = models_dir or MODELS_DIR

    if model is None:
        model, safe_model_name = load_model(
            model_name=model_name,
            allow_unsafe_model=allow_unsafe_model,
            models_dir=actual_models_dir,
            skip_update=skip_update,
            mode=mode,
            backend=backend,
        )
        if model is None:
            return
    else:
        safe_model_name = model_name

    # 2. 文字起こし/翻訳の設定
    # jp2en は Whisper の translate タスクを使用
    task = "translate" if translation_mode == "jp2en" else "transcribe"

    is_mlx = getattr(model, "backend_name", "openai") == "mlx"

    language_code = None
    if mode in ("bar", "full"):
        # mlx は事前の言語検出APIを持たない。language=None のまま渡せば
        # mlx 側が検出し、verbose が None 以外なら自身で検出言語を表示する
        if not is_mlx:
            language_code, language_name = detect_audio_language(model, file_path)
            print(f"Detected language: {language_name}", flush=True)
        print(
            f"[{item_index}/{item_total}] {os.path.basename(file_path)}",
            flush=True,
        )

    # whisper の verbose は None=無音 / False=内蔵プログレスバー / True=詳細ログ
    verbose_by_mode = {"none": None, "bar": False, "full": True}
    result = model.transcribe(
        file_path,
        fp16=False,
        verbose=verbose_by_mode[mode],
        task=task,
        language=language_code,
    )

    # en2jp の場合は追加で翻訳処理。
    # 翻訳に失敗しても文字起こし結果は失わず、サフィックスなしで保存する。
    applied_translation_mode = translation_mode
    if translation_mode == "en2jp":
        if mode != "none":
            print("\nTranslating English to Japanese...", flush=True)
        try:
            result = translate_segments(result, target_lang="ja")
        except Exception as e:
            applied_translation_mode = None
            print(f"Warning: translation failed ({e}).")
            print("Saving the original transcription without the '_en2jp' suffix.")

    # 3. 結果の保存
    output_dir = os.path.dirname(file_path) or "."
    base_name = os.path.splitext(file_path)[0]

    # ファイル名に翻訳モードを付与
    suffix = f"_{applied_translation_mode}" if applied_translation_mode else ""
    output_file_base = f"{base_name}{suffix}"
    
    # Whisperの標準writerを使用
    writer = get_writer(output_format, output_dir)
    writer(result, output_file_base)
    
    final_path = f"{output_file_base}.{output_format}"

    if mode != "none":
        elapsed_time = time.time() - start_time
        print(f"\nDone! Saved to '{final_path}'.")
        print(f"Total time: {int(elapsed_time // 60)}m {int(elapsed_time % 60)}s")
    
    return final_path

def build_parser():
    parser = argparse.ArgumentParser(description="Whisper Transcription with En-Ja/Ja-En Translation")
    parser.add_argument("file", help="Path to the audio file or a folder of audio files")

    # 進捗表示
    group_p = parser.add_mutually_exclusive_group()
    group_p.add_argument("--full", action="store_const", dest="mode", const="full", help="Full details")
    group_p.add_argument("--bar", action="store_const", dest="mode", const="bar", help="Progress bar")
    group_p.add_argument("--none", action="store_const", dest="mode", const="none", help="No output")

    # 翻訳オプション
    group_t = parser.add_mutually_exclusive_group()
    group_t.add_argument("--en2jp", action="store_const", dest="t_mode", const="en2jp", help="English to Japanese")
    group_t.add_argument("--jp2en", action="store_const", dest="t_mode", const="jp2en", help="Japanese to English")

    # その他
    parser.add_argument(
        "--backend",
        choices=["auto", "openai", "mlx"],
        default="auto",
        help="Whisper backend. 'auto' uses mlx (Apple Silicon GPU) when available",
    )
    parser.add_argument("--model", choices=["tiny", "base", "small", "medium", "large", "turbo"], default="base")
    parser.add_argument("--format", choices=["txt", "srt", "vtt", "tsv", "json"], default="txt")
    parser.add_argument(
        "--allow-unsafe-model",
        action="store_true",
        help="Skip memory safety downgrade and force the requested model",
    )
    parser.add_argument("--models-dir", help=f"Directory to save Whisper models (default: {MODELS_DIR})")
    parser.add_argument("--skip-update", action="store_true", help="Skip checking for model updates if the file exists")

    parser.set_defaults(mode="bar", t_mode=None)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    common_kwargs = dict(
        mode=args.mode,
        model_name=args.model,
        translation_mode=args.t_mode,
        output_format=args.format,
        allow_unsafe_model=args.allow_unsafe_model,
        models_dir=args.models_dir,
        skip_update=args.skip_update,
        backend=args.backend,
    )

    if os.path.isdir(args.file):
        audio_files = sorted(
            p for p in (
                os.path.join(args.file, f) for f in os.listdir(args.file)
            )
            if os.path.isfile(p) and os.path.splitext(p)[1].lower() in AUDIO_EXTENSIONS
        )

        if not audio_files:
            print(f"No audio files found in '{args.file}'.")
            return 0

        print(f"Found {len(audio_files)} audio file(s) in '{args.file}'.")
        shared_model, _ = load_model(
            model_name=args.model,
            allow_unsafe_model=args.allow_unsafe_model,
            models_dir=args.models_dir,
            skip_update=args.skip_update,
            mode=args.mode,
            backend=args.backend,
        )
        if shared_model is None:
            return 1

        failed_files = []
        for i, audio_file in enumerate(audio_files, 1):
            try:
                transcribe_audio(
                    audio_file,
                    model=shared_model,
                    item_index=i,
                    item_total=len(audio_files),
                    **common_kwargs,
                )
            except Exception as e:
                print(f"Error: failed to process '{audio_file}': {e}")
                failed_files.append(audio_file)
        if failed_files:
            print(f"\n{len(failed_files)} of {len(audio_files)} file(s) failed:")
            for failed_file in failed_files:
                print(f"  - {failed_file}")
            return 1
        return 0

    transcribe_audio(args.file, item_index=1, item_total=1, **common_kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
