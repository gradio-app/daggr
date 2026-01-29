---
name: daggr
description: |
  Build DAG-based AI pipelines connecting Gradio Spaces, HuggingFace models, and Python functions into visual workflows. Use when asked to create a workflow, build a pipeline, connect AI models, chain Gradio Spaces, create a daggr app, build multi-step AI applications, or orchestrate ML models. Triggers on: "build a workflow", "create a pipeline", "connect models", "daggr", "chain Spaces", "AI pipeline".
license: MIT
metadata:
  author: gradio-app
  version: "1.0"
---

# daggr

Build visual DAG pipelines connecting Gradio Spaces, HF Inference Providers, and Python functions.

## Quick Start

```python
from daggr import GradioNode, FnNode, InferenceNode, Graph, ItemList
import gradio as gr

graph = Graph(name="My Workflow", nodes=[node1, node2, ...])
graph.launch()  # Starts web server with visual DAG UI
```

## Node Types

### GradioNode - Gradio Spaces

```python
# Image generation example
img = GradioNode("Tongyi-MAI/Z-Image-Turbo", api_name="/generate",
    inputs={"prompt": gr.Textbox(), "resolution": "1024x1024 ( 1:1 )"},
    postprocess=lambda imgs, *_: imgs[0]["image"],
    outputs={"image": gr.Image()})
```

Find models: `https://huggingface.co/api/models?inference_provider=all&pipeline_tag=text-to-image` (swap pipeline_tag)

```python
# General pattern
node = GradioNode(
    space_or_url="owner/space-name",
    api_name="/endpoint",
    inputs={
        "param": gr.Textbox(label="Input"),   # UI input
        "other": other_node.output_port,       # Port connection
        "fixed": "constant_value",             # Fixed value
    },
    postprocess=lambda *returns: returns[0],   # Transform response
    outputs={"result": gr.Image(label="Output")},
)
```

### FnNode - Python Functions

```python
def process(input1: str, input2: int) -> str:
    return f"{input1}: {input2}"

node = FnNode(
    fn=process,
    inputs={"input1": gr.Textbox(), "input2": other_node.port},
    outputs={"result": gr.Textbox()},
)
```

### InferenceNode - [HF Inference Providers](https://huggingface.co/docs/inference-providers)

VLM/LLM models: https://router.huggingface.co/v1/models

```python
node = InferenceNode(
    model="org/model:provider",  # model:provider (fal-ai, replicate, together, etc.)
    inputs={"image": other_node.image, "prompt": gr.Textbox()},
    outputs={"image": gr.Image()},
)
```

## Port Connections

```python
next_node.input = previous_node.output_port      # Basic
items_node.items.field_name                       # Scattered (per-item)
scattered_node.output.all()                       # Gathered (collect list)
```

## ItemList - Dynamic Lists

```python
def gen_items(n: int) -> list:
    return [{"text": f"Item {i}"} for i in range(n)]

items = FnNode(fn=gen_items,
    outputs={"items": ItemList(text=gr.Textbox())})

# Runs once per item
process = FnNode(fn=process_item,
    inputs={"text": items.items.text},
    outputs={"result": gr.Textbox()})

# Collect all results
final = FnNode(fn=combine,
    inputs={"all": process.result.all()},
    outputs={"out": gr.Textbox()})
```

## Checklist

1. **Check API** before using a Space:
   ```python
   from gradio_client import Client
   Client("owner/space").view_api(return_format="dict")
   ```

2. **Handle files** (Gradio returns dicts):
   ```python
   path = file.get("path") if isinstance(file, dict) else file
   ```

3. **Use postprocess** for multi-return APIs:
   ```python
   postprocess=lambda imgs, seed, num: imgs[0]["image"]
   ```

## Common Patterns

```python
# Image Generation
GradioNode("Tongyi-MAI/Z-Image-Turbo", api_name="/generate",
    inputs={"prompt": gr.Textbox(), "resolution": "1024x1024 ( 1:1 )"},
    postprocess=lambda imgs, *_: imgs[0]["image"],
    outputs={"image": gr.Image()})

# Text-to-Speech
GradioNode("Qwen/Qwen3-TTS", api_name="/generate_voice_design",
    inputs={"text": gr.Textbox(), "language": "English", "voice_description": "..."},
    postprocess=lambda audio, status: audio,
    outputs={"audio": gr.Audio()})

# Image-to-Video
GradioNode("alexnasa/ltx-2-TURBO", api_name="/generate_video",
    inputs={"input_image": img.image, "prompt": gr.Textbox(), "duration": 5},
    postprocess=lambda video, seed: video,
    outputs={"video": gr.Video()})

# ffmpeg composition
def combine(video: str|dict, audio: str|dict) -> str:
    v = video.get("path") if isinstance(video, dict) else video
    a = audio.get("path") if isinstance(audio, dict) else audio
    out = tempfile.mktemp(suffix=".mp4")
    subprocess.run(["ffmpeg","-y","-i",v,"-i",a,"-shortest",out])
    return out
```

## Run

```bash
uv pip install daggr
python workflow.py  # Starts web server at http://127.0.0.1:7860
```

**Troubleshooting:** Clear cache if you encounter stale state issues:
```bash
rm -rf ~/.cache/huggingface/daggr/*.db
```

## Finding Spaces (optional)

Search for Gradio Spaces by task:
```bash
curl "https://huggingface.co/api/spaces/semantic-search?q=text+to+speech&sdk=gradio"
```
