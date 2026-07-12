import sys
from unittest.mock import MagicMock, Mock, patch

from transcribe import (
    MLX_MODEL_REPOS,
    MlxWhisperModel,
    load_model,
    resolve_backend,
    transcribe_audio,
)


def test_resolve_backend_explicit_values_pass_through():
    """明示指定はそのまま返ること"""
    assert resolve_backend("openai") == "openai"
    assert resolve_backend("mlx") == "mlx"


def test_resolve_backend_auto_falls_back_without_mlx():
    """mlx_whisper がインポートできない環境では auto は openai になること"""
    with patch.dict(sys.modules, {"mlx_whisper": None}):
        assert resolve_backend("auto") == "openai"


def test_load_model_mlx_returns_adapter_with_repo():
    """mlx バックエンドでは対応する HF リポジトリを持つアダプタを返すこと"""
    with patch.dict(sys.modules, {"mlx_whisper": MagicMock()}):
        model, safe_name = load_model(
            model_name="turbo",
            allow_unsafe_model=True,
            backend="mlx",
        )
    assert isinstance(model, MlxWhisperModel)
    assert safe_name == "turbo"
    assert model.repo == MLX_MODEL_REPOS["turbo"]


def test_mlx_adapter_drops_fp16_and_none_options():
    """アダプタは fp16 と None のオプションを mlx に渡さないこと"""
    fake_mlx = MagicMock()
    fake_mlx.transcribe.return_value = {"text": "hi", "segments": []}
    adapter = MlxWhisperModel("mlx-community/whisper-base-mlx")

    with patch.dict(sys.modules, {"mlx_whisper": fake_mlx}):
        adapter.transcribe(
            "/audio/a.m4a",
            fp16=False,
            verbose=None,
            task="transcribe",
            language=None,
        )

    fake_mlx.transcribe.assert_called_once_with(
        "/audio/a.m4a",
        path_or_hf_repo="mlx-community/whisper-base-mlx",
        task="transcribe",
    )


@patch("transcribe.get_writer")
@patch("transcribe.detect_audio_language")
@patch("os.path.exists", return_value=True)
def test_mlx_model_skips_predetect(
    mock_exists,
    mock_detect,
    mock_get_writer,
    capsys,
):
    """mlx モデルでは事前言語検出をせず、言語検出は mlx 側に任せること"""
    model = Mock()
    model.backend_name = "mlx"
    model.transcribe.return_value = {"text": "hello", "segments": [], "language": "en"}
    mock_get_writer.return_value = Mock()

    transcribe_audio(
        "/audio/interview.m4a",
        mode="bar",
        model=model,
        item_index=1,
        item_total=1,
    )

    mock_detect.assert_not_called()
    assert "[1/1] interview.m4a" in capsys.readouterr().out
    # 事前検出しないので language は渡さない（mlx が内部で検出・表示する）
    assert model.transcribe.call_args.kwargs["language"] is None
