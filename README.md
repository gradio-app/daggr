<h3 align="center">
  <div style="display:flex;flex-direction:row;">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="daggr/assets/logo_dark.png">
      <source media="(prefers-color-scheme: light)" srcset="daggr/assets/logo_light.png">
      <img width="75%" alt="daggr Logo" src="daggr/assets/logo_light.png">
    </picture>
    <p>DAG-based Gradio workflows!</p>
  </div>
</h3>

`daggr` is a Python library for building AI workflows that connect [Gradio](https://github.com/gradio-app/gradio) apps, ML models (through [Hugging Face Inference Providers](https://huggingface.co/docs/inference-providers/en/index)), and custom Python functions. It automatically generates a visual canvas for your workflow allowing you to inspect intermediate outputs, rerun any step any number of times, and also preserves state for complex or long-running workflows.



https://github.com/user-attachments/assets/2cfe49c0-3118-4570-b2bd-f87c333836b5


## Installation

```bash
pip install daggr
```

(requires Python 3.10 or higher).

## Quick Start

After installing `daggr`, create a new Python file, say `app.py`, and paste this code:

```python
import random

import gradio as gr

from daggr import GradioNode, Graph

glm_image = GradioNode(
    "hf-applications/Z-Image-Turbo",
    api_name="/generate_image",
    inputs={
        "prompt": gr.Textbox(  # An input node is created for the prompt
            label="Prompt",
            value="A cheetah sprints across the grassy savanna.",
            lines=3,
        ),
        "height": 1024,  # Fixed value (does not appear in the canvas)
        "width": 1024,  # Fixed value (does not appear in the canvas)
        "seed": random.random,  # Functions are rerun every time the workflow is run (not shown in the canvas)
    },
    outputs={
        "image": gr.Image(
            label="Image"  # Display in an Image component
        ),
    },
)

background_remover = GradioNode(
    "hf-applications/background-removal",
    api_name="/image",
    inputs={
        "image": glm_image.image,  # Connect the output of the GLM Image node to the input of the background remover node
    },
    outputs={
        "original_image": None,  # Original image is returned but not displayed
        "final_image": gr.Image(
            label="Final Image"
        ),  # Transparent bg image is displayed
    },
)

graph = Graph(
    name="Transparent Background Image Generator", nodes=[glm_image, background_remover]
)

graph.launch()
```

Run `python app.py` to start the Python file and you should see a Daggr app like this that you can use to generate images with a transparent background!

<img width="1462" height="508" alt="Screenshot 2026-01-26 at 1 01 58 PM" src="https://github.com/user-attachments/assets/b751abd8-e143-4882-817b-036fb66a6d92" />


## When to (Not) Use Daggr

Use Daggr when:
* You want to define an AI workflow in Python involving Gradio Spaces, inference providers, or custom functions
* The workflow is complex enough that inspecting intermediate outputs or rerunning individual steps is useful
* You need a fixed pipeline that you or others can run with different inputs

**Why not... ComfyUI?** ComfyUI is a visual node editor where you build workflows by dragging and connecting nodes. Daggr takes a code-first approach: you define workflows in Python and the visual canvas is generated automatically. If you prefer writing code over visual editing, Daggr may be a better fit.

**Why not... Airflow/Prefect?** Daggr was inspired by Airflow/Prefect, but whereas the focus of these orchestration platforms is scheduling, monitoring, and managing pipelines at scale, Daggr is built for interactive AI/ML workflows with real-time visual feedback and immediate execution, making it ideal for prototyping, demos, and workflows where you want to inspect intermediate outputs and rerun individual steps on the fly.

**Why not... Gradio?** Gradio creates web UIs for individual ML models and demos. While complex workflows can be built in Gradio, they often fail in ways that are hard to debug when using the Gradio app. Daggr tries to provide a transparent, easily-inspectable way to chain multiple Gradio apps, custom Python functions, and inference providers through a visual canvas.

Don't use Daggr when:
* You need a simple UI for a single model or function - consider using Gradio directly
* You want a node-based editor for building workflows visually - consider using  ComfyUI instead

## How It Works

A Daggr workflow consists of **nodes** connected in a directed graph. Each node represents a computation: a Gradio Space API call, an inference call to a model, or a Python function.

Each node has **input ports** and **output ports**, which correspond to the node's parameters and return values. Ports are how data flows between nodes.

**Input ports** can be connected to:
- A previous node's output port → creates an edge, data flows automatically
- A Gradio component → creates a standalone input in the UI
- A fixed value → passed directly, doesn't appear in UI
- A callable → called each time the node runs (useful for random seeds)

**Output ports** can be connected to:
- A Gradio component → displays the output in the node's card
- `None` → output is hidden but can still connect to downstream nodes

### Node Types

- **`GradioNode`**: Calls a Gradio Space API endpoint
- **`FnNode`**: Runs a Python function
- **`InferenceNode`**: Calls a model via [Hugging Face Inference Providers](https://huggingface.co/docs/inference-providers/en/index)

### Input Types

Each node's `inputs` dict accepts four types of values:

| Type | Example | Result |
|------|---------|--------|
| **Gradio component** | `gr.Textbox(label="Topic")` | Creates UI input |
| **Port reference** | `other_node.output_name` | Connects nodes |
| **Fixed value** | `"Auto"` or `42` | Constant, no UI |
| **Callable** | `random.random` | Called each run, no UI |

### Output Types

Each node's `outputs` dict accepts two types of values:

| Type | Example | Result |
|------|---------|--------|
| **Gradio component** | `gr.Image(label="Result")` | Displays output in node card |
| **None** | `None` | Hidden, but can connect to downstream nodes |

### Scatter / Gather

When a node outputs a list and you want to process each item individually, use `.each` to scatter and `.all()` to gather:

```python
script = FnNode(fn=generate_script, inputs={...}, outputs={"lines": gr.JSON()})

tts = FnNode(
    fn=text_to_speech,
    inputs={
        "text": script.lines.each["text"],      # Scatter: run once per item
        "speaker": script.lines.each["speaker"],
    },
    outputs={"audio": gr.Audio()},
)

final = FnNode(
    fn=combine_audio,
    inputs={"audio_files": tts.audio.all()},    # Gather: collect all outputs
    outputs={"audio": gr.Audio()},
)
```

## Putting It Together: A Mock Podcast Generator

```python
import gradio as gr
from daggr import FnNode, GradioNode, Graph

# Generate voice profiles
host_voice = GradioNode(
    space_or_url="abidlabs/tts",
    api_name="/generate_voice_design",
    inputs={
        "voice_description": gr.Textbox(label="Host Voice", value="Deep British voice..."),
        "language": "Auto",
        "text": "Hi! I'm the host.",
    },
    outputs={"audio": gr.Audio(label="Host Voice")},
)

guest_voice = GradioNode(
    space_or_url="abidlabs/tts",
    api_name="/generate_voice_design",
    inputs={
        "voice_description": gr.Textbox(label="Guest Voice", value="Friendly American voice..."),
        "language": "Auto",
        "text": "Hi! I'm the guest.",
    },
    outputs={"audio": gr.Audio(label="Guest Voice")},
)

# Generate dialogue (would be an LLM call in production)
def generate_dialogue(topic: str, host_voice: str, guest_voice: str):
    dialogue = [
        {"voice": host_voice, "text": "Hello, how are you?"},
        {"voice": guest_voice, "text": "I'm great, thanks!"},
    ]
    html = "<b>Host:</b> Hello!<br><b>Guest:</b> I'm great!"
    return dialogue, html

dialogue = FnNode(
    fn=generate_dialogue,
    inputs={
        "topic": gr.Textbox(label="Topic", value="AI"),
        "host_voice": host_voice.audio,
        "guest_voice": guest_voice.audio,
    },
    outputs={
        "json": gr.JSON(visible=False),
        "html": gr.HTML(label="Script"),
    },
)

# Generate audio for each line (scatter)
def text_to_speech(text: str, audio: str) -> str:
    return audio  # Would call TTS model in production

samples = FnNode(
    fn=text_to_speech,
    inputs={
        "text": dialogue.json.each["text"],
        "audio": dialogue.json.each["voice"],
    },
    outputs={"audio": gr.Audio(label="Sample")},
)

# Combine all audio (gather)
def combine_audio(audio_files: list[str]) -> str:
    from pydub import AudioSegment
    combined = AudioSegment.empty()
    for path in audio_files:
        combined += AudioSegment.from_file(path)
    combined.export("output.mp3", format="mp3")
    return "output.mp3"

final = FnNode(
    fn=combine_audio,
    inputs={"audio_files": samples.audio.all()},
    outputs={"audio": gr.Audio(label="Full Podcast")},
)

graph = Graph(name="Podcast Generator", nodes=[host_voice, guest_voice, dialogue, samples, final])
graph.launch()
```

## Sharing and Hosting

Create a public URL to share your workflow with others:

```python
graph.launch(share=True)
```

This generates a temporary public URL (expires in 1 week) using Gradio's tunneling infrastructure.

For permanent hosting, you can deploy Daggr apps on [Hugging Face Spaces](https://huggingface.co/spaces) using the Gradio SDK. Just create a new Space with the Gradio SDK, add your workflow code to `app.py`, and include `daggr` in your `requirements.txt`.

## Persistence and Sheets

Daggr automatically saves your workflow state—input values, node results, and canvas position—so you can pick up where you left off after a page reload.

### Sheets

**Sheets** are like separate workspaces within a single Daggr app. Each sheet has its own:
- Input values for all nodes
- Cached results from previous runs  
- Canvas zoom and pan position

Use sheets to work on multiple projects within the same workflow. For example, in a podcast generator app, each sheet could represent a different podcast episode you're working on.

The sheet selector appears in the title bar. Click to switch between sheets, create new ones, rename them (double-click), or delete them.

### How Persistence Works

| Environment | User Status | Persistence |
|-------------|-------------|-------------|
| **Local** | Not logged in | ✅ Saved as "local" user |
| **Local** | HF logged in | ✅ Saved under your HF username |

When running locally, your data is stored in a SQLite database (`.daggr_sessions.db`) in the current directory.

### The `persist_key` Parameter

By default, the `persist_key` is derived from your graph's `name`:

```python
Graph(name="My Podcast Generator")  # persist_key = "my_podcast_generator"
```

If you later rename your app but want to keep the existing saved data, set `persist_key` explicitly:

```python
Graph(name="Podcast Generator v2", persist_key="my_podcast_generator")
```

### Disabling Persistence

For scratch workflows or demos where you don't want data saved:

```python
Graph(name="Quick Demo", persist_key=False)
```

This disables all persistence—no sheets UI, no saved state.

## Hugging Face Authentication

Daggr automatically uses your local Hugging Face token for both `GradioNode` and `InferenceNode`. This enables:

- **ZeroGPU quota tracking**: Your HF token is sent to Gradio Spaces running on ZeroGPU, so your usage is tracked against your account's quota
- **Private Spaces access**: Connect to private Gradio Spaces you have access to
- **Gated models**: Use gated models on Hugging Face that require accepting terms of service

To log in with your Hugging Face account:

```bash
pip install huggingface_hub
hf auth login
```

You'll be prompted to enter your token, which you can find at https://huggingface.co/settings/tokens. 

Once logged in, the token is saved locally and daggr will automatically use it for all `GradioNode` and `InferenceNode` calls—no additional configuration needed.

Alternatively, you can set the `HF_TOKEN` environment variable directly:

```bash
export HF_TOKEN=hf_xxxxx
```

## LLM-Friendly Error Messages

Daggr is designed to be LLM-friendly, making it easy for AI coding assistants to generate and debug workflows. When you (or an LLM) make a mistake, Daggr provides detailed, actionable error messages with suggestions:

**Invalid API endpoint:**
```
ValueError: API endpoint '/infer' not found in 'hf-applications/background-removal'. 
Available endpoints: ['/image', '/text', '/png']. Did you mean '/image'?
```

**Typo in parameter name:**
```
ValueError: Invalid parameter(s) {'promt'} for endpoint '/generate_image' in 
'hf-applications/Z-Image-Turbo'. Did you mean: 'promt' -> 'prompt'? 
Valid parameters: {'width', 'height', 'seed', 'prompt'}
```

**Missing required parameter:**
```
ValueError: Missing required parameter(s) {'prompt'} for endpoint '/generate_image' 
in 'hf-applications/Z-Image-Turbo'. These parameters have no default values.
```

**Invalid output port reference:**
```
ValueError: Output port 'img' not found on node 'Z-Image-Turbo'. 
Available outputs: image. Did you mean 'image'?
```

**Invalid function parameter:**
```
ValueError: Invalid input(s) {'toppic'} for function 'generate_dialogue'. 
Did you mean: 'toppic' -> 'topic'? Valid parameters: {'topic', 'host_voice', 'guest_voice'}
```

**Invalid model name:**
```
ValueError: Model 'meta-llama/nonexistent-model' not found on Hugging Face Hub. 
Please check the model name is correct (format: 'username/model-name').
```

These errors make it easy for LLMs to understand what went wrong and fix the generated code automatically, enabling a smoother AI-assisted development experience.

## Development

```bash
pip install -e ".[dev]"
ruff check --fix --select I && ruff format
```

## License

MIT License
