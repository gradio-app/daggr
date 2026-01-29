from pathlib import Path
from unittest.mock import patch

import pytest

from daggr import Graph
from daggr.server import DaggrServer


@pytest.fixture
def server():
    graph = Graph(name="test")
    return DaggrServer(graph)


def test_file_to_url_converts_windows_paths(server):
    """Would fail on Windows before fix: _file_to_url only checked startswith('/')."""
    windows_path = "C:\\Users\\Test\\.cache\\image.png"

    with patch.object(Path, "is_absolute", return_value=True):
        with patch.object(Path, "exists", return_value=True):
            result = server._file_to_url(windows_path)

    assert result == "/file/C:/Users/Test/.cache/image.png"


def test_file_to_url_converts_real_file_paths(server, tmp_path):
    """Verifies real filesystem paths are converted to /file/ URLs."""
    test_file = tmp_path / "test.png"
    test_file.write_bytes(b"test")

    result = server._file_to_url(str(test_file))

    assert result.startswith("/file/")
    assert "\\" not in result
