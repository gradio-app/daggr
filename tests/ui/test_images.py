import tempfile
from pathlib import Path

import gradio as gr
from PIL import Image
from playwright.sync_api import Page, expect

from daggr import FnNode, Graph
from tests.ui.helpers import launch_daggr_server, wait_for_graph_load


def test_image_output_displays(page: Page, temp_db: str):
    def generate_image(prompt):
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        temp_dir = Path(tempfile.gettempdir()) / "daggr_test_images"
        temp_dir.mkdir(exist_ok=True)
        img_path = temp_dir / "test_image.png"
        img.save(img_path)
        return str(img_path)

    node = FnNode(
        generate_image,
        name="image_generator",
        inputs={"prompt": gr.Textbox(label="Prompt", value="red square")},
        outputs={"image": gr.Image(label="Generated Image")},
    )

    graph = Graph("Image Test", nodes=[node], persist_key=False)
    server, url = launch_daggr_server(graph, temp_db)

    try:
        page.goto(url)
        wait_for_graph_load(page)

        run_btn = page.locator(".run-btn").first
        expect(run_btn).to_be_visible()
        run_btn.click()

        page.wait_for_function(
            """() => {
                const imgs = document.querySelectorAll('.embedded-components img');
                for (const img of imgs) {
                    if (img.src && (img.src.includes('/file/') || img.src.startsWith('data:'))) {
                        return true;
                    }
                }
                return false;
            }""",
            timeout=15000,
        )
    finally:
        server.close()


def test_image_input_and_output(page: Page, temp_db: str):
    def process_image(image):
        return image

    node = FnNode(
        process_image,
        name="image_passthrough",
        inputs={"image": gr.Image(label="Input Image")},
        outputs={"output": gr.Image(label="Output Image")},
    )

    graph = Graph("Image IO Test", nodes=[node], persist_key=False)
    server, url = launch_daggr_server(graph, temp_db)

    try:
        page.goto(url)
        wait_for_graph_load(page)

        nodes = page.locator(".node")
        expect(nodes).to_have_count(2)

        input_node = page.locator(".node:has(.type-badge:text('INPUT'))")
        expect(input_node).to_be_visible()
    finally:
        server.close()


def test_multiple_outputs_with_image(page: Page, temp_db: str):
    def generate_with_info(prompt):
        img = Image.new("RGB", (50, 50), color=(0, 255, 0))
        temp_dir = Path(tempfile.gettempdir()) / "daggr_test_images"
        temp_dir.mkdir(exist_ok=True)
        img_path = temp_dir / "green_image.png"
        img.save(img_path)
        return str(img_path), f"Generated from: {prompt}"

    node = FnNode(
        generate_with_info,
        name="multi_output",
        inputs={"prompt": gr.Textbox(label="Prompt", value="green square")},
        outputs={
            "image": gr.Image(label="Generated"),
            "info": gr.Textbox(label="Info"),
        },
    )

    graph = Graph("Multi Output Test", nodes=[node], persist_key=False)
    server, url = launch_daggr_server(graph, temp_db)

    try:
        page.goto(url)
        wait_for_graph_load(page)

        run_btn = page.locator(".run-btn").first
        run_btn.click()

        page.wait_for_function(
            """() => {
                const imgs = document.querySelectorAll('.embedded-components img');
                const inputs = document.querySelectorAll('.embedded-components input[type="text"]');
                let hasImage = false;
                let hasText = false;
                for (const img of imgs) {
                    if (img.src && (img.src.includes('/file/') || img.src.startsWith('data:'))) {
                        hasImage = true;
                    }
                }
                for (const inp of inputs) {
                    if (inp.value && inp.value.includes('Generated from:')) {
                        hasText = true;
                    }
                }
                return hasImage && hasText;
            }""",
            timeout=15000,
        )
    finally:
        server.close()
