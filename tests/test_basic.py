import pytest

import daggr
from daggr import FnNode, Graph


def test_basic():
    assert daggr.__version__


def test_edge_api_with_typed_ports():
    def step_a(text: str) -> dict:
        return {"output": text.upper()}

    def step_b(data: str) -> dict:
        return {"output": data + "!"}

    node_a = FnNode(fn=step_a)
    node_b = FnNode(fn=step_b)

    assert "text" in dir(node_a)
    assert "output" in dir(node_a)
    assert node_a._name == "step_a"
    assert node_a.text.name == "text"

    graph = Graph()
    graph.edge(node_a.output, node_b.data)

    assert len(graph._edges) == 1
    assert graph.get_connections() == [("step_a", "output", "step_b", "data")]


def test_port_validation():
    def process(text: str) -> dict:
        return {"output": text}

    def consume(data: str) -> dict:
        return {"output": data}

    node1 = FnNode(fn=process)
    node2 = FnNode(fn=consume)

    graph = Graph()
    graph.edge(node1.nonexistent_port, node2.data)
    graph.edge(node1.output, node2.missing_input)

    with pytest.raises(ValueError) as exc_info:
        graph._validate_edges()

    error_msg = str(exc_info.value)
    assert "nonexistent_port" in error_msg
    assert "missing_input" in error_msg
    assert "Available outputs: output" in error_msg
    assert "Available inputs: data" in error_msg
