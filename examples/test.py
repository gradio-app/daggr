import daggr
import gradio as gr

tts = daggr.GradioNode(
    "mrfakename/MeloTTS",
    api_name="/synthesize",
    inputs={
        "text": gr.Textbox(label="Text"),
        "speaker": "EN-US",
        "speed": 1.0,
        "language": "EN",
    },
    outputs={"audio": gr.Audio()},
)

graph = daggr.Graph("Dependency Hash Tracking Demo", nodes=[tts])
graph.launch()
