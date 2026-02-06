import tempfile
from pathlib import Path

import gradio as gr
from PIL import Image
from playwright.sync_api import Page, expect

from daggr import FnNode, Graph
from tests.ui.helpers import launch_daggr_server, wait_for_graph_load

LOGO = str(
    Path(__file__).resolve().parent.parent.parent / "daggr" / "assets" / "logo_dark.png"
)


def test_image_initial_value_and_none_input(page: Page, temp_db: str):
    def flip_image(image):
        if image is None:
            return None
        img = Image.open(image)
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
        out = Path(tempfile.gettempdir()) / "daggr_flip_test.png"
        img.save(out)
        return str(out)

    node = FnNode(
        flip_image,
        name="flip",
        inputs={"image": gr.Image(label="Input Image", value=LOGO)},
        outputs={"flipped": gr.Image(label="Flipped Image")},
    )

    graph = Graph("Image Fix Test", nodes=[node], persist_key=False)
    server, url = launch_daggr_server(graph, temp_db)

    try:
        page.goto(url)
        wait_for_graph_load(page)

        page.wait_for_function(
            """() => {
                const imgs = document.querySelectorAll('.embedded-components img');
                for (const img of imgs) {
                    if (img.src && img.src.includes('/file/') && img.naturalWidth > 0) {
                        return true;
                    }
                }
                return false;
            }""",
            timeout=15000,
        )

        input_img = page.locator(".embedded-components img[src*='/file/']").first
        expect(input_img).to_be_visible()

        run_btn = page.locator(".run-btn").first
        expect(run_btn).to_be_visible()
        run_btn.click()

        page.wait_for_function(
            """() => {
                const imgs = document.querySelectorAll('.embedded-components img[src*="/file/"]');
                return imgs.length >= 2;
            }""",
            timeout=15000,
        )

        output_imgs = page.locator(".embedded-components img[src*='/file/']")
        expect(output_imgs).to_have_count(2)
    finally:
        server.close()
