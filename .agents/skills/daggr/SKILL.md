---
name: daggr
description: |
  Build DAG-based AI pipelines connecting Gradio Spaces, HuggingFace models, and Python functions into visual workflows. Use when asked to create a workflow, build a pipeline, connect AI models, chain Gradio Spaces, create a daggr app, build multi-step AI applications, or orchestrate ML models. Triggers on: "build a workflow", "create a pipeline", "connect models", "daggr", "chain Spaces", "AI pipeline".
license: MIT
metadata:
  author: gradio-app
  version: "1.1"
---

# daggr

Build visual DAG pipelines connecting Gradio Spaces, HF Inference Providers, and Python functions.

Full docs: https://raw.githubusercontent.com/gradio-app/daggr/refs/heads/main/README.md

## Quick Start

```bash
uv init && uv add daggr  # Set up project with daggr
```

```python
from daggr import GradioNode, FnNode, InferenceNode, Graph, ItemList
import gradio as gr

graph = Graph(name="My Workflow", nodes=[node1, node2, ...])
graph.launch()  # Starts web server with visual DAG UI
```

## Node Types

### GradioNode - Gradio Spaces

```python
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

# Example: image generation
img = GradioNode("Tongyi-MAI/Z-Image-Turbo", api_name="/generate",
    inputs={"prompt": gr.Textbox(), "resolution": "1024x1024 ( 1:1 )"},
    postprocess=lambda imgs, *_: imgs[0]["image"],
    outputs={"image": gr.Image()})
```

Find Spaces with semantic queries (describe what you need): `https://huggingface.co/api/spaces/semantic-search?q=generate+music+for+a+video&sdk=gradio&includeNonRunning=false`
Or by category: `https://huggingface.co/api/spaces/semantic-search?category=image-generation&sdk=gradio&includeNonRunning=false`
(categories: image-generation | video-generation | text-generation | speech-synthesis | music-generation | voice-cloning | image-editing | background-removal | image-upscaling | ocr | style-transfer | image-captioning)

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

Find models: `https://huggingface.co/api/models?inference_provider=all&pipeline_tag=text-to-image`
(swap pipeline_tag: text-to-image | image-to-image | image-to-text | image-to-video | text-to-video | text-to-speech | automatic-speech-recognition)

VLM/LLM models: https://router.huggingface.co/v1/models

```python
node = InferenceNode(
    model="org/model:provider",  # model:provider (fal-ai, replicate, together, etc.)
    inputs={"image": other_node.image, "prompt": gr.Textbox()},
    outputs={"image": gr.Image()},
)
```

**Auth:** InferenceNode and ZeroGPU Spaces require a HF token. If not in env, ask user to create one:
`https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained`
Out of quota? Pro gives 8x ZeroGPU + 10x inference: `https://huggingface.co/subscribe/pro`

## Port Connections

Pass ports via `inputs={...}`:
```python
inputs={"param": previous_node.output_port}       # Basic connection
inputs={"item": items_node.items.field_name}      # Scattered (per-item)
inputs={"all": scattered_node.output.all()}       # Gathered (collect list)
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
   ```bash
   curl -s "https://<space-subdomain>.hf.space/gradio_api/openapi.json"
   ```
   Replace `<space-subdomain>` with the Space's subdomain (e.g., `Tongyi-MAI/Z-Image-Turbo` → `tongyi-mai-z-image-turbo`).
   (Spaces also have "Use via API" link in footer with endpoints and code snippets)

2. **Handle files** (Gradio returns dicts):
   ```python
   path = file.get("path") if isinstance(file, dict) else file
   ```

3. **Use postprocess** for multi-return APIs:
   ```python
   postprocess=lambda imgs, seed, num: imgs[0]["image"]
   ```

4. **Debug with `.test()`** to validate a node in isolation:
   ```python
   node.test(param="value")
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

# ffmpeg composition (import tempfile, subprocess)
def combine(video: str|dict, audio: str|dict) -> str:
    v = video.get("path") if isinstance(video, dict) else video
    a = audio.get("path") if isinstance(audio, dict) else audio
    out = tempfile.mktemp(suffix=".mp4")
    subprocess.run(["ffmpeg","-y","-i",v,"-i",a,"-shortest",out])
    return out
```

## Run

```bash
uv run daggr workflow.py &  # Launch in background, hot reloads on file changes
```

## Authentication

**Local development:** Use `hf auth login` or set `HF_TOKEN` env var. This enables ZeroGPU quota tracking, private Spaces access, and gated models.

**Deployed Spaces:** Users can click "Login" in the UI and paste their HF token. This enables persistence (sheets) so they can save outputs and resume work later. The token is stored in browser localStorage.

**When deploying:** Pass secrets via `--secret HF_TOKEN=xxx` if your workflow needs server-side auth (e.g., for gated models in FnNode). Warning: this uses the deployer's token for all users.

## Deploy to Hugging Face Spaces

Only deploy if the user has explicitly asked to publish/deploy their workflow.

```bash
daggr deploy workflow.py
```

This extracts the Graph, creates a Space named after it, and uploads everything.

**Options:**
```bash
daggr deploy workflow.py --name my-space      # Custom Space name
daggr deploy workflow.py --org huggingface    # Deploy to an organization
daggr deploy workflow.py --private            # Private Space
daggr deploy workflow.py --hardware t4-small  # GPU (t4-small, t4-medium, a10g-small, etc.)
daggr deploy workflow.py --secret KEY=value   # Add secrets (repeatable)
daggr deploy workflow.py --dry-run            # Preview without deploying
```
