from unittest.mock import Mock, patch

from transcribe import transcribe_audio


@patch("transcribe.get_writer")
@patch("transcribe.detect_audio_language", return_value=("en", "English"))
@patch("os.path.exists", return_value=True)
def test_bar_mode_shows_language_then_indexed_filename(
    mock_exists,
    mock_detect_language,
    mock_get_writer,
    capsys,
):
    model = Mock()
    model.transcribe.return_value = {"text": "hello", "segments": []}
    mock_get_writer.return_value = Mock()

    transcribe_audio(
        "/audio/interview.m4a",
        mode="bar",
        model=model,
        item_index=2,
        item_total=10,
    )

    output_lines = capsys.readouterr().out.splitlines()
    assert output_lines[:2] == [
        "Detected language: English",
        "[2/10] interview.m4a",
    ]
    model.transcribe.assert_called_once_with(
        "/audio/interview.m4a",
        fp16=False,
        verbose=False,
        task="transcribe",
        language="en",
    )


@patch("transcribe.get_writer")
@patch("os.path.exists", return_value=True)
def test_none_mode_is_silent_and_passes_verbose_none(
    mock_exists,
    mock_get_writer,
    capsys,
):
    """--none では標準出力に何も出さず、whisper にも verbose=None を渡すこと"""
    model = Mock()
    model.transcribe.return_value = {"text": "hello", "segments": []}
    mock_get_writer.return_value = Mock()

    transcribe_audio(
        "/audio/interview.m4a",
        mode="none",
        model=model,
    )

    assert capsys.readouterr().out == ""
    assert model.transcribe.call_args.kwargs["verbose"] is None
