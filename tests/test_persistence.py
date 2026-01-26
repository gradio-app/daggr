import os
import tempfile

import pytest

from daggr.state import SessionState


@pytest.fixture
def state():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    s = SessionState(db_path=db_path)
    yield s
    os.unlink(db_path)


def test_create_sheet(state):
    sheet_id = state.create_sheet("user1", "TestGraph", "My Sheet")
    sheet = state.get_sheet(sheet_id)

    assert sheet is not None
    assert sheet["sheet_id"] == sheet_id
    assert sheet["user_id"] == "user1"
    assert sheet["graph_name"] == "TestGraph"
    assert sheet["name"] == "My Sheet"


def test_list_sheets_by_user(state):
    state.create_sheet("user1", "Graph1", "Sheet A")
    state.create_sheet("user1", "Graph1", "Sheet B")
    state.create_sheet("user2", "Graph1", "Sheet C")

    user1_sheets = state.list_sheets("user1", "Graph1")
    user2_sheets = state.list_sheets("user2", "Graph1")

    assert len(user1_sheets) == 2
    assert len(user2_sheets) == 1
    assert all(s["name"] in ["Sheet A", "Sheet B"] for s in user1_sheets)
    assert user2_sheets[0]["name"] == "Sheet C"


def test_rename_sheet(state):
    sheet_id = state.create_sheet("user1", "Graph1", "Original Name")

    success = state.rename_sheet(sheet_id, "New Name")

    assert success is True
    sheet = state.get_sheet(sheet_id)
    assert sheet["name"] == "New Name"


def test_save_and_load_inputs(state):
    sheet_id = state.create_sheet("user1", "Graph1")

    state.save_input(sheet_id, "node1", "port_a", "hello")
    state.save_input(sheet_id, "node1", "port_b", 123)
    state.save_input(sheet_id, "node2", "input", {"key": "value"})

    inputs = state.get_inputs(sheet_id)

    assert inputs["node1"]["port_a"] == "hello"
    assert inputs["node1"]["port_b"] == 123
    assert inputs["node2"]["input"] == {"key": "value"}


def test_save_and_load_results(state):
    sheet_id = state.create_sheet("user1", "Graph1")

    state.save_result(sheet_id, "node1", {"output": "result1"})
    state.save_result(sheet_id, "node1", {"output": "result2"})

    latest = state.get_latest_result(sheet_id, "node1")
    assert latest == {"output": "result2"}

    first = state.get_result_by_index(sheet_id, "node1", 0)
    assert first == {"output": "result1"}

    all_results = state.get_all_results(sheet_id)
    assert len(all_results["node1"]) == 2


def test_user_isolation(state):
    sheet_a = state.create_sheet("alice", "Graph1", "Alice's Sheet")
    sheet_b = state.create_sheet("bob", "Graph1", "Bob's Sheet")

    state.save_input(sheet_a, "input_node", "value", "alice_data")
    state.save_input(sheet_b, "input_node", "value", "bob_data")

    alice_inputs = state.get_inputs(sheet_a)
    bob_inputs = state.get_inputs(sheet_b)

    assert alice_inputs["input_node"]["value"] == "alice_data"
    assert bob_inputs["input_node"]["value"] == "bob_data"

    alice_sheets = state.list_sheets("alice", "Graph1")
    bob_sheets = state.list_sheets("bob", "Graph1")
    assert len(alice_sheets) == 1
    assert len(bob_sheets) == 1
    assert alice_sheets[0]["sheet_id"] != bob_sheets[0]["sheet_id"]


def test_local_user_fallback(state, monkeypatch):
    monkeypatch.delenv("SPACE_ID", raising=False)

    user_id = state.get_effective_user_id(None)
    assert user_id == "local"

    user_id = state.get_effective_user_id({"username": "myuser"})
    assert user_id == "myuser"


def test_spaces_requires_login(state, monkeypatch):
    monkeypatch.setenv("SPACE_ID", "some-space-id")

    user_id = state.get_effective_user_id(None)
    assert user_id is None

    user_id = state.get_effective_user_id({"username": "hf_user"})
    assert user_id == "hf_user"


def test_delete_sheet(state):
    sheet_id = state.create_sheet("user1", "Graph1", "To Delete")
    state.save_input(sheet_id, "node1", "port", "data")
    state.save_result(sheet_id, "node1", {"output": "result"})

    deleted = state.delete_sheet(sheet_id)

    assert deleted is True
    assert state.get_sheet(sheet_id) is None
    assert state.get_inputs(sheet_id) == {}
    assert state.get_all_results(sheet_id) == {}
