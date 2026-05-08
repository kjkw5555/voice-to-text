import pytest
import os
import hashlib
from unittest.mock import patch, MagicMock
from transcribe import verify_model_hash, ensure_model_exists

def test_verify_model_hash_valid(tmp_path):
    """ファイルの内容が期待されるハッシュと一致する場合、Trueを返すこと"""
    file_content = b"test content"
    expected_hash = hashlib.sha256(file_content).hexdigest()
    
    test_file = tmp_path / "test_model.pt"
    test_file.write_bytes(file_content)
    
    assert verify_model_hash(str(test_file), expected_hash) is True

def test_verify_model_hash_invalid(tmp_path):
    """ファイルの内容がハッシュと一致しない場合、Falseを返すこと"""
    test_file = tmp_path / "corrupt_model.pt"
    test_file.write_bytes(b"corrupt content")
    
    assert verify_model_hash(str(test_file), "wrong_hash") is False

@patch("transcribe.is_internet_available")
@patch("whisper._download")
def test_ensure_model_exists_downloads_if_missing(mock_download, mock_internet, tmp_path):
    """モデルが存在しない場合、ダウンロードが実行されること"""
    mock_internet.return_value = True
    model_dir = tmp_path / "models"
    model_name = "tiny"
    
    # 実際にはダウンロードしないようにモック
    with patch("os.path.exists", return_value=False):
        ensure_model_exists(model_name, str(model_dir))
        assert mock_download.called

@patch("transcribe.is_internet_available")
@patch("transcribe.verify_model_hash")
def test_ensure_model_exists_skips_if_valid(mock_verify, mock_internet, tmp_path):
    """モデルが存在しハッシュが正しい場合、ダウンロードをスキップすること"""
    mock_internet.return_value = True
    mock_verify.return_value = True
    
    model_dir = tmp_path / "models"
    model_file = model_dir / "tiny.pt"
    model_dir.mkdir()
    model_file.write_text("dummy")
    
    with patch("whisper._download") as mock_download:
        ensure_model_exists("tiny", str(model_dir))
        assert not mock_download.called
