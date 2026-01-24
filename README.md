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

`daggr` is a Python library for building AI workflows that connect Gradio Spaces, ML models, and custom functions. It automatically generates a visual canvas UI for your workflow.

## Installation

```bash
pip install daggr
```

## Quick Start

```python
import gradio as gr
from daggr import Graph, FnNode, GradioNode

# 1. Define nodes with inputs and outputs
voice = GradioNode(
    space_or_url="abidlabs/tts",
    api_name="/generate_voice_design",
    inputs={
        "voice_description": gr.Textbox(label="Voice", value="Professional voice..."),
        "language": "Auto",  # Fixed value (no UI)
        "text": "Hello world!",
    },
    outputs={
        "audio": gr.Audio(label="Generated Voice"),
    },
)

def process_audio(audio: str) -> str:
    return audio  # Your processing logic here

processor = FnNode(
    fn=process_audio,
    inputs={"audio": voice.audio},  # Connect to voice node's output
    outputs={"audio": gr.Audio(label="Processed Audio")},
)

# 2. Create graph and launch
graph = Graph(name="Audio Pipeline", nodes=[voice, processor])
graph.launch()
```

## How It Works

### Input Types

Each node's `inputs` dict accepts three types of values:

| Type | Example | Result |
|------|---------|--------|
| **Gradio component** | `gr.Textbox(label="Topic")` | Creates UI input |
| **Port reference** | `other_node.output_name` | Connects nodes |
| **Fixed value** | `"Auto"` or `42` | Constant, no UI |

### Node Types

- **`GradioNode`**: Calls a Gradio Space API endpoint
- **`FnNode`**: Runs a Python function

## Scatter / Gather (Map over lists)

When a node outputs a list and you want to process each item individually, use `.each` to scatter and `.all()` to gather:

```python
def generate_script(topic: str) -> list[dict]:
    # Returns a list of dialogue lines
    return [
        {"speaker": "host", "text": "Welcome!"},
        {"speaker": "guest", "text": "Thanks for having me!"},
    ]

script = FnNode(
    fn=generate_script,
    inputs={"topic": gr.Textbox(label="Topic")},
    outputs={"lines": gr.JSON()},
)

def text_to_speech(text: str, speaker: str) -> str:
    # Process single item
    return f"audio_for_{speaker}.mp3"

# .each["key"] - scatter: run once per item, extracting "key" from each
tts = FnNode(
    fn=text_to_speech,
    inputs={
        "text": script.lines.each["text"],      # Each item's "text" field
        "speaker": script.lines.each["speaker"], # Each item's "speaker" field
    },
    outputs={"audio": gr.Audio()},
)

def combine_audio(audio_files: list[str]) -> str:
    # Combine all audio files
    return "combined.mp3"

# .all() - gather: collect all outputs back into a list
final = FnNode(
    fn=combine_audio,
    inputs={"audio_files": tts.audio.all()},  # Gathers all audio outputs
    outputs={"audio": gr.Audio(label="Final Audio")},
)

graph = Graph(nodes=[script, tts, final])
```

**Visual indicator**: Scatter edges show as forked lines (→⟨) and gather edges show as converging lines (⟩→) in the canvas UI.

## Full Example: Podcast Generator

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

## Development

```bash
pip install -e ".[dev]"
ruff check --fix --select I && ruff format
```

## License

MIT License
