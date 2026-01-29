# Showcases InferenceNode for speech-to-text and text-to-speech with an FnNode transformation in between.
import gradio as gr

from daggr import FnNode, Graph, InferenceNode

original = InferenceNode(
    model="openai/whisper-large-v3:replicate",
    inputs={
        "audio": gr.Audio(label="Audio"),
    },
    outputs={
        "text": gr.Textbox(label="Text"),
    },
)


def pig_latin_sentence(text: str) -> str:
    words = text.split()
    pig_latin_words = []
    for word in words:
        pig_latin_words.append(word[1:] + word[0] + "ay")
    return " ".join(pig_latin_words)


pig_latin = FnNode(
    fn=pig_latin_sentence,
    inputs={
        "text": original.text,
    },
    outputs={
        "text": gr.Textbox(label="Text"),
    },
)

output = InferenceNode(
    model="hexgrad/Kokoro-82M",
    inputs={
        "text": pig_latin.text,
    },
    outputs={
        "audio": gr.Audio(label="Audio"),
    },
)

graph = Graph(name="Pig Latin Voice App", nodes=[original, pig_latin, output])

graph.launch()
