import whisper
import os
import time
import argparse
import subprocess
import platform
from whisper.utils import get_writer
from deep_translator import GoogleTranslator

# tqdmがインストールされているか確認し、なければダミーを作成
try:
    from tqdm import tqdm
except ImportError:
    class tqdm:
        def __init__(self, *args, **kwargs): pass
        def update(self, *args, **kwargs): pass
        def close(self, *args, **kwargs): pass

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


def model_fits_memory(model_name, memory_info):
    """モデルが現在のメモリ条件に対して安全かどうかを返します。"""
    requirement = MODEL_MEMORY_REQUIREMENTS_GB[model_name]
    total_gb = memory_info["total_gb"]
    available_gb = memory_info["available_gb"]

    if total_gb is not None and total_gb < requirement["total"]:
        return False

    if available_gb is not None and available_gb < requirement["available"]:
        return False

    return True


def choose_safe_model(requested_model, allow_unsafe_model=False):
    """
    現在のメモリ状況に応じて安全なモデルを選びます。
    """
    memory_info = get_memory_info()

    if allow_unsafe_model:
        return requested_model, memory_info, None

    if model_fits_memory(requested_model, memory_info):
        return requested_model, memory_info, None

    requested_index = MODEL_ORDER.index(requested_model)
    for candidate in reversed(MODEL_ORDER[:requested_index]):
        if model_fits_memory(candidate, memory_info):
            return candidate, memory_info, (
                f"Requested model '{requested_model}' may exceed safe memory limits. "
                f"Falling back to '{candidate}'."
            )

    return None, memory_info, (
        f"Requested model '{requested_model}' is not safe on this machine, "
        "and no smaller model meets the configured safety threshold."
    )

def get_audio_duration(file_path):
    """ffprobeを使用して音声の長さを取得します（秒単位）"""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return float(result.stdout.strip())
    except:
        return 0

def translate_text(text, target_lang="ja"):
    """テキストを翻訳します（長文対応のため分割して処理）"""
    translator = GoogleTranslator(source='auto', target=target_lang)
    # GoogleTranslator は一度に5000文字までなので、必要に応じて分割
    max_chars = 4500
    chunks = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
    translated_chunks = [translator.translate(chunk) for chunk in chunks]
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

def transcribe_audio(
    file_path,
    mode="none",
    model_name="base",
    translation_mode=None,
    output_format="txt",
    allow_unsafe_model=False,
):
    """
    音声ファイルを読み込み、文字起こしを実行して結果をファイルに保存します。
    """
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        return

    start_time = time.time()

    safe_model_name, memory_info, safety_message = choose_safe_model(
        model_name,
        allow_unsafe_model=allow_unsafe_model,
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
        return

    # 1. モデルのロード
    if mode != "none":
        print(f"Loading Whisper model '{safe_model_name}'...")
    model = whisper.load_model(safe_model_name)

    # 2. 文字起こし/翻訳の設定
    # jp2en は Whisper の translate タスクを使用
    task = "translate" if translation_mode == "jp2en" else "transcribe"
    
    if mode == "bar":
        print(f"Processing: {file_path} (Mode: {translation_mode or 'normal'})")
        pbar = tqdm(total=100, desc="Progress", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {percentage:3.0f}%")
        pbar.update(10)
        result = model.transcribe(file_path, fp16=False, verbose=False, task=task)
        pbar.update(70)
        
        # en2jp の場合は追加で翻訳処理
        if translation_mode == "en2jp":
            print("\nTranslating to Japanese...")
            result = translate_segments(result, target_lang="ja")
        
        pbar.update(20)
        pbar.close()
    else:
        verbose = (mode == "full")
        result = model.transcribe(file_path, fp16=False, verbose=verbose, task=task)
        
        if translation_mode == "en2jp":
            if mode != "none": print("Translating English to Japanese...")
            result = translate_segments(result, target_lang="ja")

    # 3. 結果の保存
    output_dir = os.path.dirname(file_path) or "."
    base_name = os.path.splitext(file_path)[0]
    
    # ファイル名に翻訳モードを付与
    suffix = f"_{translation_mode}" if translation_mode else ""
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Whisper Transcription with En-Ja/Ja-En Translation")
    parser.add_argument("file", help="Path to the audio file")
    
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
    parser.add_argument("--model", choices=["tiny", "base", "small", "medium", "large", "turbo"], default="base")
    parser.add_argument("--format", choices=["txt", "srt", "vtt", "tsv", "json"], default="txt")
    parser.add_argument(
        "--allow-unsafe-model",
        action="store_true",
        help="Skip memory safety downgrade and force the requested model",
    )
    
    parser.set_defaults(mode="none", t_mode=None)
    args = parser.parse_args()

    transcribe_audio(
        args.file,
        mode=args.mode,
        model_name=args.model,
        translation_mode=args.t_mode,
        output_format=args.format,
        allow_unsafe_model=args.allow_unsafe_model,
    )
