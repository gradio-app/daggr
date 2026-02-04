import gradio as gr
from playwright.sync_api import Page, expect

from daggr import FnNode, Graph
from tests.ui.helpers import launch_daggr_server, wait_for_graph_load


def test_sheets_ui_elements_present(page: Page, temp_db: str):
    def process(text):
        return text.upper()

    node = FnNode(
        process,
        name="processor",
        inputs={"text": gr.Textbox(label="Input", value="test")},
        outputs={"result": gr.Textbox(label="Result")},
    )

    graph = Graph("Sheets Test", nodes=[node], persist_key="sheets_test")
    server, url = launch_daggr_server(graph, temp_db)

    try:
        page.goto(url)
        wait_for_graph_load(page)

        sheet_selector = page.locator(".sheet-current")
        expect(sheet_selector).to_be_visible(timeout=5000)

        sheet_name = page.locator(".sheet-name")
        expect(sheet_name).to_be_visible()
        expect(sheet_name).to_contain_text("Sheet")
    finally:
        server.close()


def test_create_new_sheet(page: Page, temp_db: str):
    def echo(text):
        return text

    node = FnNode(
        echo,
        name="echo",
        inputs={"text": gr.Textbox(label="Text", value="hello")},
        outputs={"result": gr.Textbox(label="Echo")},
    )

    graph = Graph("New Sheet Test", nodes=[node], persist_key="new_sheet_test")
    server, url = launch_daggr_server(graph, temp_db)

    try:
        page.goto(url)
        wait_for_graph_load(page)

        sheet_selector = page.locator(".sheet-current")
        expect(sheet_selector).to_be_visible(timeout=5000)
        sheet_selector.click()

        dropdown = page.locator(".sheet-dropdown")
        expect(dropdown).to_be_visible()

        new_sheet_btn = page.locator(".sheet-new")
        expect(new_sheet_btn).to_be_visible()
        new_sheet_btn.click()

        page.wait_for_timeout(1000)

        sheet_selector.click()
        sheet_options = page.locator(".sheet-option")
        expect(sheet_options).to_have_count(2, timeout=5000)
    finally:
        server.close()


def test_switch_between_sheets(page: Page, temp_db: str):
    def process(text):
        return f"Processed: {text}"

    node = FnNode(
        process,
        name="processor",
        inputs={"text": gr.Textbox(label="Input", value="default")},
        outputs={"result": gr.Textbox(label="Result")},
    )

    graph = Graph("Switch Sheets Test", nodes=[node], persist_key="switch_sheets_test")
    server, url = launch_daggr_server(graph, temp_db)

    try:
        page.goto(url)
        wait_for_graph_load(page)

        input_node = page.locator(".node:has(.type-badge:text('INPUT'))")
        input_field = input_node.locator("input[type='text']").first
        expect(input_field).to_be_visible()

        input_field.fill("Sheet 1 Value")

        run_btn = page.locator(".run-btn").first
        run_btn.click()

        page.wait_for_function(
            """() => {
                const inputs = document.querySelectorAll('.embedded-components input[type="text"]');
                for (const inp of inputs) {
                    if (inp.value && inp.value.includes('Processed:')) {
                        return true;
                    }
                }
                return false;
            }""",
            timeout=15000,
        )

        sheet_selector = page.locator(".sheet-current")
        sheet_selector.click()

        new_sheet_btn = page.locator(".sheet-new")
        new_sheet_btn.click()

        page.wait_for_timeout(1500)

        wait_for_graph_load(page)

        input_field = page.locator(
            ".node:has(.type-badge:text('INPUT')) input[type='text']"
        ).first
        expect(input_field).to_be_visible()
        current_value = input_field.input_value()
        assert current_value == "default" or current_value == ""

        sheet_selector = page.locator(".sheet-current")
        sheet_selector.click()

        first_sheet = page.locator(".sheet-option").first
        first_sheet.locator(".sheet-option-name").click()

        page.wait_for_timeout(1000)
        wait_for_graph_load(page)

        input_field = page.locator(
            ".node:has(.type-badge:text('INPUT')) input[type='text']"
        ).first
        restored_value = input_field.input_value()
        assert restored_value == "Sheet 1 Value"
    finally:
        server.close()


def test_result_persists_on_sheet(page: Page, temp_db: str):
    def double(x):
        return x * 2

    node = FnNode(
        double,
        name="doubler",
        inputs={"x": gr.Number(label="Number", value=5)},
        outputs={"result": gr.Number(label="Doubled")},
    )

    graph = Graph(
        "Persist Result Test", nodes=[node], persist_key="persist_result_test"
    )
    server, url = launch_daggr_server(graph, temp_db)

    try:
        page.goto(url)
        wait_for_graph_load(page)

        run_btn = page.locator(".run-btn").first
        run_btn.click()

        page.wait_for_function(
            """() => {
                const inputs = document.querySelectorAll('.embedded-components input[type="number"]');
                for (const inp of inputs) {
                    if (inp.value === '10') {
                        return true;
                    }
                }
                return false;
            }""",
            timeout=15000,
        )

        page.reload()
        wait_for_graph_load(page)

        page.wait_for_function(
            """() => {
                const inputs = document.querySelectorAll('.embedded-components input[type="number"]');
                for (const inp of inputs) {
                    if (inp.value === '10') {
                        return true;
                    }
                }
                return false;
            }""",
            timeout=15000,
        )
    finally:
        server.close()
