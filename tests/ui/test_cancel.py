import time

import gradio as gr
from playwright.sync_api import Page, expect

from daggr import FnNode, Graph
from tests.ui.helpers import launch_daggr_server, wait_for_graph_load


def test_cancel_running_node(page: Page, temp_db: str):
    def slow_fn(x):
        time.sleep(30)
        return x * 2

    node = FnNode(
        slow_fn,
        name="slow_node",
        inputs={"x": gr.Number(label="Input", value=5)},
        outputs={"result": gr.Number(label="Result")},
    )

    graph = Graph("Cancel Test", nodes=[node], persist_key=False)
    server, url = launch_daggr_server(graph, temp_db)

    try:
        page.goto(url)
        wait_for_graph_load(page)

        slow_node = page.locator(".node:has(.node-name:text('slow_node'))")
        expect(slow_node).to_be_visible()

        run_btn = slow_node.locator(".run-btn")
        expect(run_btn).to_be_visible()
        run_btn.click()

        page.wait_for_function(
            """() => {
                const nodes = document.querySelectorAll('.node');
                for (const node of nodes) {
                    const name = node.querySelector('.node-name');
                    if (name && name.textContent === 'slow_node') {
                        const btn = node.querySelector('.run-btn.running');
                        return btn !== null;
                    }
                }
                return false;
            }""",
            timeout=10000,
        )

        stop_btn = slow_node.locator(".run-btn.running")
        expect(stop_btn).to_be_visible()
        stop_btn.click()

        page.wait_for_function(
            """() => {
                const nodes = document.querySelectorAll('.node');
                for (const node of nodes) {
                    const name = node.querySelector('.node-name');
                    if (name && name.textContent === 'slow_node') {
                        const btn = node.querySelector('.run-btn');
                        return btn && !btn.classList.contains('running');
                    }
                }
                return false;
            }""",
            timeout=5000,
        )

        run_btn_after = slow_node.locator(".run-btn:not(.running)")
        expect(run_btn_after).to_be_visible()
    finally:
        server.close()
