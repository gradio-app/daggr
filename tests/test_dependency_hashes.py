import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from daggr.state import SessionState


@pytest.fixture
def state():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    s = SessionState(db_path=db_path)
    yield s
    os.unlink(db_path)


def test_save_and_load_dependency_hashes(state):
    state.save_dependency_hash(
        "my_graph", "tts_node", "space", "mrfakename/MeloTTS", "abc123"
    )
    state.save_dependency_hash(
        "my_graph", "llm_node", "model", "meta-llama/Llama-2-7b", "def456"
    )

    hashes = state.get_dependency_hashes("my_graph")

    assert len(hashes) == 2
    assert hashes["tts_node"]["dep_type"] == "space"
    assert hashes["tts_node"]["dep_id"] == "mrfakename/MeloTTS"
    assert hashes["tts_node"]["commit_hash"] == "abc123"
    assert hashes["llm_node"]["dep_type"] == "model"
    assert hashes["llm_node"]["commit_hash"] == "def456"


def test_dependency_hash_upsert(state):
    state.save_dependency_hash(
        "my_graph", "tts_node", "space", "mrfakename/MeloTTS", "abc123"
    )
    state.save_dependency_hash(
        "my_graph", "tts_node", "space", "mrfakename/MeloTTS", "xyz789"
    )

    hashes = state.get_dependency_hashes("my_graph")

    assert len(hashes) == 1
    assert hashes["tts_node"]["commit_hash"] == "xyz789"


def test_dependency_hashes_isolated_by_graph(state):
    state.save_dependency_hash(
        "graph_a", "node1", "space", "user/space1", "hash_a"
    )
    state.save_dependency_hash(
        "graph_b", "node1", "space", "user/space1", "hash_b"
    )

    hashes_a = state.get_dependency_hashes("graph_a")
    hashes_b = state.get_dependency_hashes("graph_b")

    assert hashes_a["node1"]["commit_hash"] == "hash_a"
    assert hashes_b["node1"]["commit_hash"] == "hash_b"


def test_check_dependency_hashes_detects_change():
    from daggr.node import GradioNode

    with patch.object(GradioNode, "_validate_space_format"), \
         patch.object(GradioNode, "_validate_gradio_api"):
        node = GradioNode.__new__(GradioNode)
        node._id = 0
        node._name = "tts"
        node._src = "user/my-space"
        node._api_name = "/predict"
        node._run_locally = False
        node._local_url = None
        node._local_failed = False
        node._preprocess = None
        node._postprocess = None
        node._input_ports = ["text"]
        node._output_ports = ["audio"]
        node._input_components = {}
        node._output_components = {}
        node._item_list_schemas = {}
        node._fixed_inputs = {}
        node._port_connections = {}

    from daggr.graph import Graph

    graph = Graph("Test", nodes=[node])

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        st = SessionState(db_path=db_path)
        st.save_dependency_hash(
            graph.persist_key, "tts", "space", "user/my-space", "old_hash_111"
        )

        from daggr.server import DaggrServer

        mock_space_info = MagicMock()
        mock_space_info.sha = "new_hash_222"

        with patch("daggr.server.DaggrServer._fetch_commit_hash", return_value="new_hash_222"), \
             patch.dict(os.environ, {"DAGGR_DB_PATH": db_path}), \
             patch("daggr.server._get_theme") as mock_theme:
            mock_theme_instance = MagicMock()
            mock_theme_instance._get_theme_css.return_value = ""
            mock_theme.return_value = mock_theme_instance

            server = DaggrServer(graph)
            assert len(server._dependency_warnings) == 1
            warning = server._dependency_warnings[0]
            assert warning["node_name"] == "tts"
            assert warning["dep_type"] == "space"
            assert warning["old_hash"] == "old_hash_111"
            assert warning["new_hash"] == "new_hash_222"
    finally:
        os.unlink(db_path)

