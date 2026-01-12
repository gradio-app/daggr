<div align="center">
<img src="https://github.com/user-attachments/assets/973811ad-e657-43b5-acd6-e7506ab2810e" alt="daggr" width="75%">
</div>

`daggr` is a Python package for building resilient DAG-based workflows that connect Gradio apps, ML models via inference providers, and custom functions.

## Installation

This package requires [Python 3.10 or higher](https://www.python.org/downloads/). Install with `pip`:

```bash
pip install daggr
```

or with `uv`:

```bash
uv pip install daggr
```

## Usage

daggr allows you to build complex pipelines using a clean, intuitive syntax inspired by Airflow.

### Basic Example

```python
from daggr import Graph, GradioNode, FnNode, ops

# Create nodes
text_generator = GradioNode(src="gradio/gpt2", name="Text Generator")
text_summarizer = GradioNode(src="gradio/distilbart-cnn-12-6", name="Summarizer")

# Build the graph using context manager and >> operator
with Graph(name="Text Pipeline") as graph:
    text_generator["output"] >> text_summarizer["text"]

# Launch the generated UI
graph.launch()
```


### Complete Example

```python
import gradio as gr

from daggr import FnNode, Graph, InputNode, MapNode


def mock_maya1_voice_gen(text_description: str) -> dict:
    return {"voice": f"generated_voice_{hash(text_description) % 1000}.wav"}


def mock_generate_dialogue(topic: str) -> dict:
    return {
        "dialogue": [
            {"speaker": "host", "text": f"Welcome! Today we discuss {topic}."},
            {"speaker": "guest", "text": "Thanks for having me."},
            {"speaker": "host", "text": "Let's dive in."},
            {"speaker": "guest", "text": "Absolutely, let's do it."},
        ]
    }


def mock_tts(segment: dict, host_voice: str, guest_voice: str) -> dict:
    voice = host_voice if segment["speaker"] == "host" else guest_voice
    return {"audio": f"tts_{segment['speaker']}_{voice[:20]}.wav"}


def combine_audio(segments: list, mode: str = "full") -> dict:
    count = 3 if mode == "test" else len(segments)
    return {"combined": f"podcast_{mode}_{count}_segments.wav"}


host_voice_input = InputNode(
    inputs=[gr.Textbox(label="Host Voice", placeholder="Warm, professional...")],
    name="Host Voice Description",
)

guest_voice_input = InputNode(
    inputs=[gr.Textbox(label="Guest Voice", placeholder="Energetic, friendly...")],
    name="Guest Voice Description",
)

topic_input = InputNode(
    inputs=[gr.Textbox(label="Topic", placeholder="AI in healthcare...")],
    name="Podcast Topic",
)

host_voice_gen = FnNode(
    fn=mock_maya1_voice_gen,
    outputs=[gr.Audio(label="Host Voice")],
    name="Generate Host Voice",
)

guest_voice_gen = FnNode(
    fn=mock_maya1_voice_gen,
    outputs=[gr.Audio(label="Guest Voice")],
    name="Generate Guest Voice",
)

dialogue_gen = FnNode(
    fn=mock_generate_dialogue,
    outputs=[gr.JSON(label="Dialogue")],
    name="Generate Dialogue",
)

tts_map = MapNode(
    fn=mock_tts,
    item_output=gr.Audio(),
    name="TTS Per Segment",
)

combine_test = FnNode(
    fn=lambda segments: combine_audio(segments, "test"),
    outputs=[gr.Audio(label="Test Preview")],
    name="Test Run",
)

combine_full = FnNode(
    fn=lambda segments: combine_audio(segments, "full"),
    outputs=[gr.Audio(label="Full Podcast")],
    name="Full Run",
)


with Graph(name="Podcast Generator") as graph:
    host_voice_input["Host Voice"] >> host_voice_gen["text_description"]
    guest_voice_input["Guest Voice"] >> guest_voice_gen["text_description"]
    topic_input["Topic"] >> dialogue_gen["topic"]

    dialogue_gen["dialogue"] >> tts_map["items"]
    host_voice_gen["voice"] >> tts_map["host_voice"]
    guest_voice_gen["voice"] >> tts_map["guest_voice"]

    tts_map["results"] >> combine_test["segments"]
    tts_map["results"] >> combine_full["segments"]


graph.launch()
```

### Test App

Run the included test app:

```bash
python test_app.py
```

## Development

To set up the package for development, clone this repository and run:

```bash
pip install -e ".[dev]"
```

## Testing

Run tests with:

```bash
pytest
```

## Code Formatting

Format code using Ruff:

```bash
ruff check --fix --select I && ruff format
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License
