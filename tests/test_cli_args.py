import pytest
from unittest.mock import Mock, patch

from transcribe import build_parser, main, transcribe_audio


def test_argparse_defaults():
    """デフォルトは base モデル・bar 表示・txt 出力・翻訳なしであること"""
    args = build_parser().parse_args(["audio.m4a"])
    assert args.model == "base"
    assert args.mode == "bar"
    assert args.format == "txt"
    assert args.t_mode is None
    assert args.models_dir is None
    assert args.skip_update is False


def test_argparse_custom_models_dir():
    """--models-dir オプションが正しく解析されること"""
    args = build_parser().parse_args(["audio.m4a", "--models-dir", "/opt/models"])
    assert args.models_dir == "/opt/models"


def test_argparse_progress_modes_are_exclusive():
    """--bar と --none は同時指定できないこと"""
    with pytest.raises(SystemExit):
        build_parser().parse_args(["audio.m4a", "--bar", "--none"])


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


@patch("transcribe.transcribe_audio")
@patch("transcribe.load_model", return_value=(Mock(), "tiny"))
def test_main_batch_continues_after_failure(mock_load, mock_transcribe, tmp_path, capsys):
    """フォルダ処理で1ファイル失敗しても残りを処理し、終了コード1を返すこと"""
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "b.mp3").write_bytes(b"x")
    mock_transcribe.side_effect = [Exception("broken file"), None]

    exit_code = main([str(tmp_path), "--none"])

    assert exit_code == 1
    assert mock_transcribe.call_count == 2
    output = capsys.readouterr().out
    assert "1 of 2 file(s) failed" in output


@patch("transcribe.transcribe_audio")
@patch("transcribe.load_model", return_value=(Mock(), "tiny"))
def test_main_batch_all_success_returns_zero(mock_load, mock_transcribe, tmp_path):
    """フォルダ処理で全ファイル成功なら終了コード0を返すこと"""
    (tmp_path / "a.mp3").write_bytes(b"x")

    assert main([str(tmp_path), "--none"]) == 0
    assert mock_transcribe.call_count == 1


def test_main_batch_empty_folder(tmp_path, capsys):
    """音声ファイルがないフォルダでは何もせず正常終了すること"""
    assert main([str(tmp_path), "--none"]) == 0
    assert "No audio files found" in capsys.readouterr().out
