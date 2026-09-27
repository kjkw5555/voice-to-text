from unittest.mock import Mock, patch

from transcribe import build_parser, expected_output_path, main


def test_argparse_skip_existing_default_off():
    """--skip-existing はデフォルトで無効であること"""
    assert build_parser().parse_args(["audio.m4a"]).skip_existing is False
    assert build_parser().parse_args(["audio.m4a", "--skip-existing"]).skip_existing is True


def test_expected_output_path_considers_format_and_translation():
    """出力予定パスに --format と翻訳サフィックスが反映されること"""
    assert expected_output_path("/a/talk.m4a") == "/a/talk.txt"
    assert expected_output_path("/a/talk.m4a", None, "srt") == "/a/talk.srt"
    assert expected_output_path("/a/talk.m4a", "en2jp", "txt") == "/a/talk_en2jp.txt"
    assert expected_output_path("/a/talk.m4a", "jp2en", "vtt") == "/a/talk_jp2en.vtt"


@patch("transcribe.transcribe_audio")
@patch("transcribe.load_model", return_value=(Mock(), "tiny"))
def test_batch_skips_files_with_existing_output(mock_load, mock_transcribe, tmp_path, capsys):
    """出力済みのファイルは転写せずスキップし、失敗扱いにしないこと"""
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "a.txt").write_text("done")
    (tmp_path / "b.mp3").write_bytes(b"x")

    exit_code = main([str(tmp_path), "--none", "--skip-existing"])

    assert exit_code == 0
    assert mock_transcribe.call_count == 1
    assert mock_transcribe.call_args[0][0] == str(tmp_path / "b.mp3")
    output = capsys.readouterr().out
    assert f"Skipping '{tmp_path / 'a.mp3'}'" in output
    assert "Skipped 1 file(s)" in output
    assert "failed" not in output


@patch("transcribe.transcribe_audio")
@patch("transcribe.load_model", return_value=(Mock(), "tiny"))
def test_batch_all_skipped_does_not_load_model(mock_load, mock_transcribe, tmp_path):
    """全件出力済みならモデルをロードせず正常終了すること"""
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "a.txt").write_text("done")

    assert main([str(tmp_path), "--none", "--skip-existing"]) == 0
    mock_load.assert_not_called()
    mock_transcribe.assert_not_called()


@patch("transcribe.transcribe_audio")
@patch("transcribe.load_model", return_value=(Mock(), "tiny"))
def test_batch_skip_respects_format(mock_load, mock_transcribe, tmp_path):
    """別フォーマットの出力しかない場合はスキップしないこと"""
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "a.txt").write_text("done")

    assert main([str(tmp_path), "--none", "--skip-existing", "--format", "srt"]) == 0
    assert mock_transcribe.call_count == 1


@patch("transcribe.transcribe_audio")
@patch("transcribe.load_model", return_value=(Mock(), "tiny"))
def test_batch_skip_en2jp_ignores_unsuffixed_fallback(mock_load, mock_transcribe, tmp_path):
    """--en2jp では翻訳失敗時のサフィックスなし出力だけではスキップしないこと"""
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "a.txt").write_text("fallback")
    (tmp_path / "b.mp3").write_bytes(b"x")
    (tmp_path / "b_en2jp.txt").write_text("done")

    assert main([str(tmp_path), "--none", "--skip-existing", "--en2jp"]) == 0
    assert mock_transcribe.call_count == 1
    assert mock_transcribe.call_args[0][0] == str(tmp_path / "a.mp3")


@patch("transcribe.transcribe_audio")
@patch("transcribe.load_model", return_value=(Mock(), "tiny"))
def test_batch_without_flag_processes_existing(mock_load, mock_transcribe, tmp_path):
    """--skip-existing なしでは従来どおり出力済みでも再処理すること"""
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "a.txt").write_text("done")

    assert main([str(tmp_path), "--none"]) == 0
    assert mock_transcribe.call_count == 1


@patch("transcribe.transcribe_audio")
def test_single_file_skipped_when_output_exists(mock_transcribe, tmp_path, capsys):
    """単一ファイル入力でも出力済みならスキップして終了コード0を返すこと"""
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    (tmp_path / "a_jp2en.json").write_text("{}")

    assert main([str(audio), "--none", "--skip-existing", "--jp2en", "--format", "json"]) == 0
    mock_transcribe.assert_not_called()
    assert "output already exists" in capsys.readouterr().out


@patch("transcribe.transcribe_audio")
@patch("transcribe.download_audio")
def test_url_input_skips_transcription_after_download(mock_download, mock_transcribe, tmp_path):
    """URL 入力ではダウンロード後の出力名で判定し、転写だけスキップすること"""
    audio = tmp_path / "Talk.m4a"
    audio.write_bytes(b"x")
    (tmp_path / "Talk.txt").write_text("done")
    mock_download.return_value = str(audio)

    assert main(["https://example.com/watch?v=1", "--none", "--skip-existing"]) == 0
    mock_download.assert_called_once()
    mock_transcribe.assert_not_called()
