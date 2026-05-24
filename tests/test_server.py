import asyncio
from pathlib import Path
from unittest.mock import patch

import gradio as gr
import pytest
from fastapi.testclient import TestClient

from daggr import FnNode, Graph
from daggr.server import DaggrServer
from daggr.session import ExecutionSession


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


def _build_shared_input_graph() -> Graph:
    def detect(image: str) -> str:
        return f"detected:{image}"

    def keypoint(image: str, detection_json: str) -> str:
        return f"{image}|{detection_json}"

    shared_image: gr.Textbox = gr.Textbox(label="Input Image", value="default-image")
    detection_node: FnNode = FnNode(
        detect,
        name="detection",
        inputs={"image": shared_image},
        outputs={"detection_json": gr.Textbox()},
    )
    keypoint_node: FnNode = FnNode(
        keypoint,
        name="keypoint",
        inputs={
            "image": shared_image,
            "detection_json": detection_node.detection_json,
        },
        outputs={"keypoint_json": gr.Textbox()},
    )
    graph: Graph = Graph("shared-input", nodes=[detection_node, keypoint_node])
    return graph


def test_execute_to_node_reuses_shared_component_input():
    graph: Graph = _build_shared_input_graph()
    server: DaggrServer = DaggrServer(graph)
    session: ExecutionSession = ExecutionSession(graph)

    asyncio.run(
        server._execute_to_node(
            session=session,
            target_node="keypoint",
            session_id=None,
            input_values={"detection__image": {"value": "input-image"}},
            selected_results={},
        )
    )

    assert session.results["keypoint"]["keypoint_json"] == (
        "input-image|detected:input-image"
    )


def test_execute_to_node_streaming_reuses_shared_component_input():
    graph: Graph = _build_shared_input_graph()
    server: DaggrServer = DaggrServer(graph)
    session: ExecutionSession = ExecutionSession(graph)

    async def collect_events() -> list[dict]:
        events: list[dict] = []
        async for event in server._execute_to_node_streaming(
            session=session,
            target_node="keypoint",
            sheet_id=None,
            input_values={"detection__image": {"value": "input-image"}},
            item_list_values={},
            selected_results={},
            run_id="test-run",
        ):
            events.append(event)
        return events

    events: list[dict] = asyncio.run(collect_events())

    assert session.results["keypoint"]["keypoint_json"] == (
        "input-image|detected:input-image"
    )
    assert any(
        event.get("type") == "node_complete"
        and event.get("completed_node") == "keypoint"
        for event in events
    )


def test_workflow_api_reuses_shared_component_input():
    graph: Graph = _build_shared_input_graph()
    server: DaggrServer = DaggrServer(graph)
    client: TestClient = TestClient(server.app)

    response = client.post(
        "/api/call",
        json={"inputs": {"detection__image": "input-image"}},
    )

    assert response.status_code == 200
    outputs: dict = response.json()["outputs"]
    assert outputs["keypoint"]["keypoint_json"] == ("input-image|detected:input-image")
