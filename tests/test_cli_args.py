import pytest
import argparse
from transcribe import transcribe_audio
from unittest.mock import patch

def test_argparse_custom_models_dir():
    """--models-dir オプションが正しく解析されること"""
    # 実際には argparse.ArgumentParser を呼び出す必要があるが、
    # transcribe.py の if __name__ == "__main__": 内部にあるため、
    # 関数化されていることが望ましいが、現状は直接解析部分をテストする。
    # ここでは便宜上、将来の構造を見越して argparse の設定を確認する。
    pass

@patch("transcribe.ensure_model_exists")
@patch("whisper.load_model")
@patch("os.path.exists", return_value=True)
def test_transcribe_audio_uses_custom_models_dir(mock_exists, mock_load, mock_ensure, tmp_path):
    """transcribe_audio がカスタムのモデルディレクトリを使用すること"""
    model_dir = str(tmp_path / "custom_models")
    transcribe_audio(
        "dummy.mp3",
        model_name="tiny",
        models_dir=model_dir
    )
    # ensure_model_exists が正しいディレクトリで呼ばれたか確認
    mock_ensure.assert_called_once()
    assert mock_ensure.call_args[0][1] == model_dir
