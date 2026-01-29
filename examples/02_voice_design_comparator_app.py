# Showcases parallel execution by comparing two TTS services (Qwen and Maya) with the same input.
import gradio as gr

from daggr import GradioNode, Graph

voice_description = gr.Textbox(
    label="Host Voice Description",
    value="Deep British voice that is very professional and authoritative...",
    lines=3,
)

text_to_speak = gr.Textbox(
    label="Text to Speak",
    value="Hi! I'm the host of a podcast. It's going to be a great episode!",
    lines=3,
)

qwen_voice = GradioNode(
    space_or_url="Qwen/Qwen3-TTS",
    api_name="/generate_voice_design",
    inputs={
        "voice_description": voice_description,
        "language": "Auto",
        "text": text_to_speak,
    },
    outputs={
        "audio": gr.Audio(label="Host Voice"),
        "status": None,
    },
)

maya_voice = GradioNode(
    space_or_url="maya-research/maya1",
    api_name="/generate_speech",
    inputs={
        "preset_name": "Male American",
        "description": voice_description,
        "text": text_to_speak,
        "temperature": 0.4,
        "max_tokens": 1500,
    },
    outputs={
        "audio": gr.Audio(label="Host Voice"),
        "status": None,
    },
)

graph = Graph(
    name="Voice Designing Comparator",
    nodes=[qwen_voice, maya_voice],
)

graph.launch()
