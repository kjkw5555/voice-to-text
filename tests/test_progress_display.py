from unittest.mock import Mock, patch

from transcribe import transcribe_audio


class FakeProgressBar:
    def __init__(self, *args, **kwargs):
        self.updates = []

    def update(self, value):
        self.updates.append(value)

    def close(self):
        pass


@patch("transcribe.get_writer")
@patch("transcribe.tqdm", FakeProgressBar)
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
