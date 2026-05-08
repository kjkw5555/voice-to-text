import pytest
import socket
from unittest.mock import patch
from transcribe import is_internet_available

def test_is_internet_available_success():
    """正常にインターネットに接続できる場合、Trueを返すこと"""
    with patch("socket.create_connection") as mock_conn:
        mock_conn.return_value = None
        assert is_internet_available() is True

def test_is_internet_available_failure():
    """接続に失敗（タイムアウトやエラー）した場合、Falseを返すこと"""
    with patch("socket.create_connection") as mock_conn:
        mock_conn.side_effect = socket.error
        assert is_internet_available() is False
