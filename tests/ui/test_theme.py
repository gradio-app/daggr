import gradio as gr
from playwright.sync_api import Page

from daggr import FnNode, Graph
from tests.ui.helpers import launch_daggr_server, wait_for_graph_load


def test_theme_support(page: Page, temp_db: str):
    """Test that theme CSS is served and applied correctly."""

    def echo(text):
        return text

    node = FnNode(
        echo,
        name="echo",
        inputs={"text": gr.Textbox(label="Input")},
        outputs={"result": gr.Textbox(label="Output")},
    )

    graph = Graph("Theme Test", nodes=[node], persist_key=False)
    server, url = launch_daggr_server(graph, temp_db, theme=gr.themes.Soft())

    try:
        response = page.request.get(f"{url}/theme.css")
        assert response.ok
        css_content = response.text()
        assert "--body-background-fill" in css_content
        assert "--color-accent" in css_content

        page.goto(url)
        wait_for_graph_load(page)

        has_dark_class = page.evaluate("() => document.body.classList.contains('dark')")
        assert has_dark_class

        has_accent = page.evaluate("""
            () => {
                const value = getComputedStyle(document.documentElement).getPropertyValue('--color-accent');
                return value && value.trim().length > 0;
            }
        """)
        assert has_accent
    finally:
        server.close()
