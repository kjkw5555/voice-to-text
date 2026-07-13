import pytest
from unittest.mock import Mock, patch

from transcribe import download_audio, is_url, main


def test_is_url():
    """http/https のみ URL と判定すること"""
    assert is_url("https://www.youtube.com/watch?v=xyz") is True
    assert is_url("http://example.com/audio.mp3") is True
    assert is_url("audio.m4a") is False
    assert is_url("./recordings") is False


@patch("transcribe.shutil.which", return_value=None)
def test_download_audio_requires_ytdlp(mock_which):
    """yt-dlp がない場合は導入方法つきのエラーになること"""
    with pytest.raises(RuntimeError, match="yt-dlp is required"):
        download_audio("https://example.com/v")


@patch("os.path.exists", return_value=True)
@patch("transcribe.subprocess.run")
@patch("transcribe.shutil.which", return_value="/usr/local/bin/yt-dlp")
def test_download_audio_returns_reported_path(mock_which, mock_run, mock_exists):
    """yt-dlp が出力した最終ファイルパスを返すこと"""
    mock_run.return_value = Mock(returncode=0, stdout="/tmp/My Talk.m4a\n")

    path = download_audio("https://example.com/v", mode="none")

    assert path == "/tmp/My Talk.m4a"
    cmd = mock_run.call_args[0][0]
    assert "--no-playlist" in cmd
    assert "bestaudio[ext=m4a]/bestaudio/best" in cmd
    assert "--progress" not in cmd  # none モードでは進捗を出さない


@patch("transcribe.subprocess.run")
@patch("transcribe.shutil.which", return_value="/usr/local/bin/yt-dlp")
def test_download_audio_raises_on_failure(mock_which, mock_run):
    """yt-dlp が失敗したら RuntimeError になること"""
    mock_run.return_value = Mock(returncode=1, stdout="")

    with pytest.raises(RuntimeError, match="exit code 1"):
        download_audio("https://example.com/v")


@patch("transcribe.transcribe_audio")
@patch("transcribe.download_audio", return_value="/tmp/talk.m4a")
def test_main_url_downloads_then_transcribes(mock_download, mock_transcribe):
    """URL を渡すとダウンロード後にそのファイルを転写すること"""
    exit_code = main(["https://www.youtube.com/watch?v=xyz", "--none"])

    assert exit_code == 0
    mock_download.assert_called_once()
    assert mock_transcribe.call_args[0][0] == "/tmp/talk.m4a"


@patch("transcribe.transcribe_audio")
@patch("transcribe.download_audio", side_effect=RuntimeError("network down"))
def test_main_url_download_failure_returns_one(mock_download, mock_transcribe):
    """ダウンロード失敗時は転写せず終了コード1を返すこと"""
    exit_code = main(["https://www.youtube.com/watch?v=xyz", "--none"])

    assert exit_code == 1
    mock_transcribe.assert_not_called()
