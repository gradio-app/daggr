import re

import gradio as gr
from playwright.sync_api import Page, expect

from daggr import FnNode, Graph
from tests.ui.helpers import launch_daggr_server, wait_for_graph_load


def test_run_mode_dropdown_and_single_step(page: Page, temp_db: str):
    def add_one(x):
        return x + 1

    def double(y):
        return y * 2

    node_a = FnNode(
        add_one,
        name="add_one",
        inputs={"x": gr.Number(label="Input", value=5)},
        outputs={"result": gr.Number(label="Plus One")},
    )
    node_b = FnNode(
        double,
        name="double",
        inputs={"y": node_a.result},
        outputs={"result": gr.Number(label="Doubled")},
    )

    graph = Graph("Run Mode Test", nodes=[node_b], persist_key=False)
    server, url = launch_daggr_server(graph, temp_db)

    try:
        page.goto(url)
        wait_for_graph_load(page)

        double_node = page.locator(".node:has(.node-name:text('double'))")
        expect(double_node).to_be_visible()

        run_controls = double_node.locator(".run-controls")
        expect(run_controls).to_be_visible()

        run_mode_toggle = run_controls.locator(".run-mode-toggle")
        expect(run_mode_toggle).to_be_visible()
        run_mode_toggle.click()

        run_mode_menu = page.locator(".run-mode-menu")
        expect(run_mode_menu).to_be_visible()

        step_option = run_mode_menu.locator(
            ".run-mode-option:has-text('Run this step')"
        )
        expect(step_option).to_be_visible()

        to_here_option = run_mode_menu.locator(
            ".run-mode-option:has-text('Run to here')"
        )
        expect(to_here_option).to_be_visible()

        # Default is "Run to here"
        expect(to_here_option).to_have_class(re.compile(r"active"))

        # Select "Run this step" and verify icon changes to single play
        step_option.click()
        expect(run_mode_menu).to_be_hidden()

        page.wait_for_function(
            """() => {
                const nodes = document.querySelectorAll('.node');
                for (const node of nodes) {
                    const name = node.querySelector('.node-name');
                    if (name && name.textContent === 'double') {
                        const icon = node.querySelector('.run-btn .run-icon-svg');
                        return icon && !icon.classList.contains('run-icon-double');
                    }
                }
                return false;
            }""",
            timeout=5000,
        )

        # Select "Run to here" and verify icon changes back to double play
        run_mode_toggle.click()
        expect(run_mode_menu).to_be_visible()

        to_here_option = page.locator(
            ".run-mode-menu .run-mode-option:has-text('Run to here')"
        )
        to_here_option.click()

        page.wait_for_function(
            """() => {
                const nodes = document.querySelectorAll('.node');
                for (const node of nodes) {
                    const name = node.querySelector('.node-name');
                    if (name && name.textContent === 'double') {
                        const icon = node.querySelector('.run-btn .run-icon-svg');
                        return icon && icon.classList.contains('run-icon-double');
                    }
                }
                return false;
            }""",
            timeout=5000,
        )

    finally:
        server.close()
