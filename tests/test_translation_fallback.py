import pytest
from unittest.mock import Mock, patch

from transcribe import transcribe_audio, translate_text


@patch("transcribe.get_writer")
@patch("transcribe.translate_segments", side_effect=Exception("network down"))
@patch("os.path.exists", return_value=True)
def test_en2jp_failure_saves_original_without_suffix(
    mock_exists,
    mock_translate,
    mock_get_writer,
):
    """翻訳に失敗しても文字起こし結果がサフィックスなしで保存されること"""
    model = Mock()
    model.transcribe.return_value = {"text": "hello", "segments": []}
    writer = Mock()
    mock_get_writer.return_value = writer

    final_path = transcribe_audio(
        "/audio/interview.m4a",
        mode="none",
        model=model,
        translation_mode="en2jp",
    )

    assert final_path == "/audio/interview.txt"
    writer.assert_called_once()
    saved_result = writer.call_args[0][0]
    assert saved_result["text"] == "hello"


@patch("transcribe.get_writer")
@patch("transcribe.translate_segments")
@patch("os.path.exists", return_value=True)
def test_en2jp_success_keeps_suffix(mock_exists, mock_translate, mock_get_writer):
    """翻訳に成功した場合は従来どおり _en2jp サフィックスが付くこと"""
    model = Mock()
    model.transcribe.return_value = {"text": "hello", "segments": []}
    mock_translate.return_value = {"text": "こんにちは", "segments": []}
    mock_get_writer.return_value = Mock()

    final_path = transcribe_audio(
        "/audio/interview.m4a",
        mode="none",
        model=model,
        translation_mode="en2jp",
    )

    assert final_path == "/audio/interview_en2jp.txt"


@patch("transcribe.time.sleep")
@patch("transcribe.GoogleTranslator")
def test_translate_text_retries_transient_errors(mock_translator_cls, mock_sleep):
    """一時的なエラーはリトライして成功すること"""
    translator = Mock()
    translator.translate.side_effect = [Exception("boom"), "こんにちは"]
    mock_translator_cls.return_value = translator

    assert translate_text("hello") == "こんにちは"
    assert translator.translate.call_count == 2


@patch("transcribe.time.sleep")
@patch("transcribe.GoogleTranslator")
def test_translate_text_raises_after_max_retries(mock_translator_cls, mock_sleep):
    """リトライ上限を超えたら例外を送出すること"""
    translator = Mock()
    translator.translate.side_effect = Exception("boom")
    mock_translator_cls.return_value = translator

    with pytest.raises(Exception, match="boom"):
        translate_text("hello", max_retries=3)
    assert translator.translate.call_count == 3
