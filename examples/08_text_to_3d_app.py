# Showcases a text-to-3D pipeline: FLUX image generation → background removal → TRELLIS mesh extraction.
import gradio as gr

from daggr import GradioNode, Graph

text_to_image = GradioNode(
    "hysts-mcp/FLUX.1-dev",
    api_name="/infer",
    inputs={
        "prompt": gr.Textbox(
            label="Prompt",
            value="A cute baby dragon breathing fire",
            lines=3,
        ),
        "height": 1024,
        "width": 1024,
        "seed": gr.Number(
            label="Seed (Image generation)", value=0, minimum=0, maximum=1000
        ),
    },
    outputs={
        "image": gr.Image(label="Image"),
    },
)

background_remover = GradioNode(
    "hysts-mcp/rembg",
    api_name="/remove_background",
    inputs={
        "image": text_to_image.image,
    },
    outputs={
        "output": gr.Image(label="Output"),
        "original_image": None,
    },
)

image_to_3d_step1 = GradioNode(
    "hysts-mcp/TRELLIS",
    api_name="/image_to_3d",
    inputs={
        "image": background_remover.output,
        "seed": gr.Number(
            label="Seed (Mesh generation)", value=0, minimum=0, maximum=1000
        ),
        "ss_guidance_strength": 7.5,
        "ss_sampling_steps": 12,
        "slat_guidance_strength": 3.0,
        "slat_sampling_steps": 12,
    },
    outputs={
        "state": gr.File(label="State file"),
        "video": gr.Video(label="Video visualization"),
    },
)

image_to_3d_step2 = GradioNode(
    "hysts-mcp/TRELLIS",
    api_name="/extract_glb",
    inputs={
        "state_path": image_to_3d_step1.state,
        "mesh_simplify": 0.95,
        "texture_size": 1024,
    },
    outputs={
        "Mesh": gr.Model3D(label="Mesh"),
    },
)

graph = Graph(
    name="text to image to 3d",
    nodes=[text_to_image, background_remover, image_to_3d_step1, image_to_3d_step2],
)

graph.launch()
