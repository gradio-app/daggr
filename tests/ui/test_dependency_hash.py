import os

import gradio as gr
from playwright.sync_api import Page, expect

from daggr import GradioNode, Graph, _client_cache
from tests.ui.helpers import launch_daggr_server, wait_for_graph_load


def test_dependency_hash_auto_update_on_stale_cache(page: Page, temp_db: str):
    tts = GradioNode(
        "mrfakename/MeloTTS",
        api_name="/synthesize",
        inputs={
            "text": gr.Textbox(label="Text"),
            "speaker": "EN-US",
            "speed": 1.0,
            "language": "EN",
        },
        outputs={"audio": gr.Audio()},
        validate=False,
    )

    graph = Graph("Hash Tracking Test", nodes=[tts], persist_key=False)

    stale_hash = "0" * 40
    _client_cache.set_dependency_hash("mrfakename/MeloTTS", stale_hash)
    assert _client_cache.get_dependency_hash("mrfakename/MeloTTS") == stale_hash

    os.environ["DAGGR_DEPENDENCY_CHECK"] = "update"
    try:
        graph._check_dependency_hashes()
    finally:
        os.environ.pop("DAGGR_DEPENDENCY_CHECK", None)

    updated_hash = _client_cache.get_dependency_hash("mrfakename/MeloTTS")
    assert updated_hash is not None
    assert updated_hash != stale_hash, (
        "Hash should have been updated from the stale value"
    )

    server, url = launch_daggr_server(graph, temp_db)
    try:
        page.goto(url)
        wait_for_graph_load(page)

        nodes = page.locator(".node")
        expect(nodes).to_have_count(2)

        node_names = page.locator(".node-name")
        names = [node_names.nth(i).text_content() for i in range(node_names.count())]
        assert "MeloTTS" in names
    finally:
        server.close()
