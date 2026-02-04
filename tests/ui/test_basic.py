import gradio as gr
from playwright.sync_api import Page, expect

from daggr import FnNode, Graph
from tests.ui.helpers import launch_daggr_server, wait_for_graph_load


def test_nodes_and_edges_render(page: Page, temp_db: str):
    def double(x):
        return x * 2

    def add_ten(y):
        return y + 10

    node_a = FnNode(
        double,
        name="doubler",
        inputs={"x": gr.Number(label="Input Number", value=5)},
        outputs={"result": gr.Number(label="Doubled")},
    )
    node_b = FnNode(
        add_ten,
        name="adder",
        inputs={"y": node_a.result},
        outputs={"result": gr.Number(label="Final Result")},
    )

    graph = Graph("Basic Test", nodes=[node_b], persist_key=False)
    server, url = launch_daggr_server(graph, temp_db)

    try:
        page.goto(url)
        wait_for_graph_load(page)

        nodes = page.locator(".node")
        expect(nodes).to_have_count(3)

        node_names = page.locator(".node-name")
        names = [node_names.nth(i).text_content() for i in range(node_names.count())]
        assert "doubler" in names
        assert "adder" in names

        edges = page.locator(".edge-path")
        expect(edges).to_have_count(2)
    finally:
        server.close()


def test_run_workflow_produces_output(page: Page, temp_db: str):
    def greet(name):
        return f"Hello, {name}!"

    node = FnNode(
        greet,
        name="greeter",
        inputs={"name": gr.Textbox(label="Name", value="World")},
        outputs={"greeting": gr.Textbox(label="Greeting")},
    )

    graph = Graph("Greeting Test", nodes=[node], persist_key=False)
    server, url = launch_daggr_server(graph, temp_db)

    try:
        page.goto(url)
        wait_for_graph_load(page)

        run_btn = page.locator(".run-btn").first
        expect(run_btn).to_be_visible()
        run_btn.click()

        page.wait_for_function(
            """() => {
                const inputs = document.querySelectorAll('.embedded-components input[type="text"]');
                for (const inp of inputs) {
                    if (inp.value && inp.value.includes('Hello')) {
                        return true;
                    }
                }
                return false;
            }""",
            timeout=15000,
        )
    finally:
        server.close()


def test_input_node_accepts_value(page: Page, temp_db: str):
    def process(text):
        return text.upper()

    node = FnNode(
        process,
        name="uppercaser",
        inputs={"text": gr.Textbox(label="Input Text", value="test")},
        outputs={"result": gr.Textbox(label="Uppercase")},
    )

    graph = Graph("Input Test", nodes=[node], persist_key=False)
    server, url = launch_daggr_server(graph, temp_db)

    try:
        page.goto(url)
        wait_for_graph_load(page)

        input_node = page.locator(".node:has(.type-badge:text('INPUT'))")
        expect(input_node).to_be_visible()

        input_field = input_node.locator("input[type='text']").first
        expect(input_field).to_be_visible()

        input_field.fill("hello world")

        run_btn = page.locator(".run-btn").first
        run_btn.click()

        page.wait_for_function(
            """() => {
                const inputs = document.querySelectorAll('.embedded-components input[type="text"]');
                for (const inp of inputs) {
                    if (inp.value && inp.value.includes('HELLO WORLD')) {
                        return true;
                    }
                }
                return false;
            }""",
            timeout=15000,
        )
    finally:
        server.close()
