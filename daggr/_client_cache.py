from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from daggr.state import get_daggr_cache_dir

_client_cache: dict[str, Any] = {}
_api_memory_cache: dict[str, dict] = {}
_validated_set: set[str] = set()
_model_task_cache: dict[str, str] = {}
_dependency_hash_cache: dict[str, str] = {}
_dependency_hash_loaded: bool = False


def _is_hot_reload() -> bool:
    return os.environ.get("DAGGR_HOT_RELOAD") == "1"


def _get_cache_path(src: str) -> Path:
    src_hash = hashlib.md5(src.encode()).hexdigest()[:16]
    return get_daggr_cache_dir() / f"{src_hash}.json"


def _get_validated_file() -> Path:
    return get_daggr_cache_dir() / "_validated.json"


def _load_validated_set() -> None:
    global _validated_set
    if _validated_set:
        return
    if not _is_hot_reload():
        return
    validated_file = _get_validated_file()
    if validated_file.exists():
        try:
            _validated_set = set(json.loads(validated_file.read_text()))
        except (json.JSONDecodeError, OSError):
            _validated_set = set()


def _save_validated_set() -> None:
    if not _is_hot_reload():
        return
    try:
        get_daggr_cache_dir().mkdir(parents=True, exist_ok=True)
        _get_validated_file().write_text(json.dumps(list(_validated_set)))
    except OSError:
        pass


def is_validated(cache_key: tuple) -> bool:
    if not _is_hot_reload():
        return False
    _load_validated_set()
    return str(cache_key) in _validated_set


def mark_validated(cache_key: tuple) -> None:
    if not _is_hot_reload():
        return
    _load_validated_set()
    _validated_set.add(str(cache_key))
    _save_validated_set()


def get_api_info(src: str) -> dict | None:
    if src in _api_memory_cache:
        return _api_memory_cache[src]

    if not _is_hot_reload():
        return None

    cache_path = _get_cache_path(src)
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text())
            _api_memory_cache[src] = data
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return None


def set_api_info(src: str, info: dict) -> None:
    _api_memory_cache[src] = info
    if not _is_hot_reload():
        return
    try:
        get_daggr_cache_dir().mkdir(parents=True, exist_ok=True)
        cache_path = _get_cache_path(src)
        cache_path.write_text(json.dumps(info))
    except OSError:
        pass


def get_client(src: str):
    return _client_cache.get(src)


def set_client(src: str, client) -> None:
    _client_cache[src] = client


def _get_model_task_cache_path() -> Path:
    return get_daggr_cache_dir() / "_model_tasks.json"


def _load_model_task_cache() -> None:
    global _model_task_cache
    if _model_task_cache:
        return
    if not _is_hot_reload():
        return
    cache_path = _get_model_task_cache_path()
    if cache_path.exists():
        try:
            _model_task_cache = json.loads(cache_path.read_text())
        except (json.JSONDecodeError, OSError):
            _model_task_cache = {}


def _save_model_task_cache() -> None:
    if not _is_hot_reload():
        return
    try:
        get_daggr_cache_dir().mkdir(parents=True, exist_ok=True)
        _get_model_task_cache_path().write_text(json.dumps(_model_task_cache))
    except OSError:
        pass


def get_model_task(model: str) -> tuple[bool, str | None]:
    """Get cached task for a model.

    Returns:
        (found_in_cache, task) where:
        - found_in_cache is True if we have cached info for this model
        - task is the pipeline_tag (can be None if model has no task, or "__NOT_FOUND__" if model doesn't exist)
    """
    if model in _model_task_cache:
        return True, _model_task_cache[model]

    if not _is_hot_reload():
        return False, None

    _load_model_task_cache()
    if model in _model_task_cache:
        return True, _model_task_cache[model]
    return False, None


def set_model_task(model: str, task: str | None) -> None:
    _model_task_cache[model] = task
    _save_model_task_cache()


def set_model_not_found(model: str) -> None:
    _model_task_cache[model] = "__NOT_FOUND__"
    _save_model_task_cache()


def _get_dependency_hash_path() -> Path:
    return get_daggr_cache_dir() / "_dependency_hashes.json"


def _load_dependency_hash_cache() -> None:
    global _dependency_hash_cache, _dependency_hash_loaded
    if _dependency_hash_loaded:
        return
    cache_path = _get_dependency_hash_path()
    if cache_path.exists():
        try:
            _dependency_hash_cache = json.loads(cache_path.read_text())
        except (json.JSONDecodeError, OSError):
            _dependency_hash_cache = {}
    _dependency_hash_loaded = True


def _save_dependency_hash_cache() -> None:
    try:
        get_daggr_cache_dir().mkdir(parents=True, exist_ok=True)
        _get_dependency_hash_path().write_text(json.dumps(_dependency_hash_cache))
    except OSError:
        pass


def get_dependency_hash(src: str) -> str | None:
    _load_dependency_hash_cache()
    return _dependency_hash_cache.get(src)


def set_dependency_hash(src: str, sha: str) -> None:
    _load_dependency_hash_cache()
    _dependency_hash_cache[src] = sha
    _save_dependency_hash_cache()
