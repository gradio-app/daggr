"""Tests for cache directory resolution."""

import importlib
import os
import tempfile
from pathlib import Path
from unittest import mock

import huggingface_hub.constants

from daggr.local_space import _get_spaces_cache_dir
from daggr.state import get_daggr_cache_dir


def test_cache_directories_respect_hf_home_env_var():
    """Test that daggr and spaces cache directories respect HF_HOME env var."""
    with tempfile.TemporaryDirectory() as custom_hf_home:
        with mock.patch.dict(os.environ, {"HF_HOME": custom_hf_home}):
            importlib.reload(huggingface_hub.constants)

            daggr_cache = get_daggr_cache_dir()
            spaces_cache = _get_spaces_cache_dir()

            hf_home_path = Path(custom_hf_home)
            assert daggr_cache.is_relative_to(hf_home_path)
            assert spaces_cache.is_relative_to(hf_home_path)
