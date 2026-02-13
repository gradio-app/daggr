# Showcases basic GradioNode chaining: generate an image then remove its background.
import random

import gradio as gr

from daggr import GradioNode, Graph

glm_image = GradioNode(
    "hf-applications/Z-Image-Turbo",
    api_name="/generate_image",
    inputs={
        "prompt": gr.Textbox(  # An input node is created for the prompt
            label="Prompt",
            value="A cheetah in the grassy savanna.",
            lines=3,
        ),
        "height": gr.Slider(
            label="Height", value=1024, minimum=1024, maximum=4096, step=128
        ),
        "width": gr.Slider(
            label="Width", value=1024, minimum=1024, maximum=4096, step=128
        ),
        "seed": random.random,  # Functions are rerun every time the workflow is run (not shown in the canvas)
    },
    embed_inputs=True,  # Display inputs inside node
    outputs={
        "image": gr.Image(
            label="Image"  # Display original image
        ),
    },
)

background_remover = GradioNode(
    "hf-applications/background-removal",
    api_name="/image",
    inputs={
        "image": glm_image.image,
    },
    postprocess=lambda _, final: final,
    outputs={
        "image": gr.Image(label="Final Image"),  # Display only final image
    },
)

graph = Graph(
    name="Transparent Background Image Generator", nodes=[glm_image, background_remover]
)

graph.launch()
