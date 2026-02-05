import gradio as gr
from playwright.sync_api import Page, expect

from daggr import FnNode, Graph
from tests.ui.helpers import launch_daggr_server, wait_for_graph_load


def test_dropdown_options_render_outside_node(page: Page, temp_db: str):
    """Test that dropdown options render outside the node container, not clipped inside."""

    def process(choice):
        return f"Selected: {choice}"

    node = FnNode(
        process,
        name="selector",
        inputs={
            "choice": gr.Dropdown(
                label="Pick One",
                choices=["Option A", "Option B", "Option C", "Option D"],
                value="Option A",
            )
        },
        outputs={"result": gr.Textbox(label="Result")},
    )

    graph = Graph("Dropdown Test", nodes=[node], persist_key=False)
    server, url = launch_daggr_server(graph, temp_db)

    try:
        page.goto(url)
        wait_for_graph_load(page)

        input_node = page.locator(".node:has(.type-badge:text('INPUT'))")
        expect(input_node).to_be_visible()

        dropdown_input = input_node.locator(".dropdown-input")
        expect(dropdown_input).to_be_visible()
        dropdown_input.click()

        options_portal = page.locator(".options-portal")
        expect(options_portal).to_be_visible()

        node_box = input_node.bounding_box()
        options_box = options_portal.bounding_box()

        assert node_box is not None
        assert options_box is not None
        assert options_box["y"] + options_box["height"] > node_box["y"] + node_box["height"], (
            "Dropdown options should extend below the node boundary"
        )

        option_buttons = options_portal.locator(".option")
        expect(option_buttons).to_have_count(4)
        option_buttons.nth(1).click()

        page.wait_for_timeout(200)
        expect(dropdown_input).to_have_attribute("placeholder", "Option B")
    finally:
        server.close()

