# Showcases running a GradioNode locally with run_locally=True instead of calling a remote Space.
import gradio as gr

from daggr import GradioNode, Graph

translator = GradioNode(
    "abidlabs/en2fr",
    api_name="/predict",
    run_locally=True,
    inputs={
        "text": gr.Textbox(
            label="English Text",
            value="Hello, how are you today?",
            lines=3,
        ),
    },
    outputs={
        "translation": gr.Textbox(label="French Translation"),
    },
)

graph = Graph(name="English to French Translator (Local)", nodes=[translator])

graph.launch()
