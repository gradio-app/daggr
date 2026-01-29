# Showcases a multi-step image-to-3D pipeline: background removal → downscaling → FLUX enhancement → TRELLIS 3D.
import uuid
from typing import Any

import gradio as gr
from PIL import Image

from daggr import FnNode, GradioNode, Graph, InferenceNode
from daggr.state import get_daggr_files_dir


def downscale_image_to_file(image: Any, scale: float = 0.25) -> str | None:
    pil_img = Image.open(image)
    scale_f = max(0.05, min(1.0, float(scale)))
    w, h = pil_img.size
    new_w = max(1, int(w * scale_f))
    new_h = max(1, int(h * scale_f))
    resized = pil_img.resize((new_w, new_h), resample=Image.LANCZOS)
    out_path = get_daggr_files_dir() / f"{uuid.uuid4()}.png"
    resized.save(out_path)
    return str(out_path)


background_remover = GradioNode(
    "merve/background-removal",
    api_name="/image",
    run_locally=True,
    inputs={
        "image": gr.Image(),
    },
    outputs={
        "original_image": None,
        "final_image": gr.Image(label="Final Image"),
    },
)

downscaler = FnNode(
    downscale_image_to_file,
    name="Downscale image for Inference",
    inputs={
        "image": background_remover.final_image,
        "scale": gr.Slider(
            label="Downscale factor",
            minimum=0.25,
            maximum=0.75,
            step=0.05,
            value=0.25,
        ),
    },
    outputs={
        "image": gr.Image(label="Downscaled Image", type="filepath"),
    },
)

flux_enhancer = InferenceNode(
    model="black-forest-labs/FLUX.2-klein-4B:fal-ai",
    inputs={
        "image": downscaler.image,
        "prompt": gr.Textbox(
            label="prompt",
            value=("Transform this into a clean 3D asset render"),
            lines=3,
        ),
    },
    outputs={
        "image": gr.Image(label="3D-Ready Enhanced Image"),
    },
)


trellis_3d = GradioNode(
    "microsoft/TRELLIS.2",
    api_name="/image_to_3d",
    inputs={
        "image": flux_enhancer.image,
        "ss_guidance_strength": 7.5,
        "ss_sampling_steps": 12,
    },
    outputs={
        "glb": gr.HTML(label="3D Asset (GLB preview)"),
    },
)

graph = Graph(
    name="Image to 3D Asset Pipeline",
    nodes=[background_remover, downscaler, flux_enhancer, trellis_3d],
)


if __name__ == "__main__":
    graph.launch()
