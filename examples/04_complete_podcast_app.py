import ssl
import tempfile
import time
import urllib.request

import gradio as gr
from pydub import AudioSegment

from daggr import FnNode, GradioNode, Graph

host_voice = GradioNode(
    space_or_url="Qwen/Qwen3-TTS",  # Currently mocked. But this would be a call to e.g. Qwen/Qwen3-TTS
    api_name="/generate_voice_design",
    inputs={
        "voice_description": gr.Textbox(
            label="Host Voice Description",
            value="Deep British voice that is very professional and authoritative...",
            lines=3,
        ),
        "language": "English",
        "text": "Hi! I'm the host of this podcast. It's going to be a great episode!",
    },
    outputs={
        "audio": gr.Audio(label="Host Voice"),
        "status": None,
    },
)


guest_voice = GradioNode(
    space_or_url="Qwen/Qwen3-TTS",  # Currently mocked. But this would be a call to e.g. Qwen/Qwen3-TTS
    api_name="/generate_voice_design",
    inputs={
        "voice_description": gr.Textbox(
            label="Guest Voice Description",
            value="Energetic, friendly young woman with American accent...",
            lines=3,
        ),
        "language": "English",
        "text": "Hi! I'm the guest on this podcast. Super excited to be here!",
    },
    outputs={
        "audio": gr.Audio(label="Guest Voice"),
        "status": None,
    },
)


def generate_dialogue(topic: str) -> dict:
    time.sleep(1)
    return {
        "items": [
            {"speaker": "Host", "text": "Hello, welcome to the show!"},
            {"speaker": "Guest", "text": "Thanks for having me!"},
            {"speaker": "Host", "text": "Today we're discussing " + topic},
            {"speaker": "Guest", "text": "Yes, it's a fascinating topic!"},
        ]
    }


dialogue = FnNode(
    fn=generate_dialogue,
    inputs={
        "topic": gr.Textbox(label="Topic", value="AI in healthcare..."),
    },
    outputs={"items": gr.Dialogue(speakers=["Host", "Guest"])},
)


def chatterbox(dialogue: list[dict], host_audio: str, guest_audio: str) -> str:
    voice_map = {"Host": host_audio, "Guest": guest_audio}
    return voice_map.get(speaker, host_audio)


samples = FnNode(
    fn=chatterbox,
    inputs={
        "dialogue": dialogue.items,
        "host_audio": host_voice.audio,
        "guest_audio": guest_voice.audio,
    },
    outputs={
        "audio": gr.Audio(label="Sample"),
    },
)


def combine_audio_files(audio_files: list[str]) -> str:
    if not audio_files:
        return None
    if len(audio_files) == 1:
        return audio_files[0]

    combined = AudioSegment.empty()
    for audio_path in audio_files:
        if audio_path:
            if audio_path.startswith(("http://", "https://")):
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(audio_path, context=ctx) as response:
                    tmp.write(response.read())
                tmp.close()
                segment = AudioSegment.from_file(tmp.name)
            else:
                segment = AudioSegment.from_file(audio_path)
            combined += segment

    output_path = tempfile.mktemp(suffix=".mp3")
    combined.export(output_path, format="mp3")
    return output_path


full_audio = FnNode(
    fn=combine_audio_files,
    inputs={
        "audio_files": samples.audio.all(),
    },
    outputs={
        "audio": gr.Audio(label="Full Audio"),
    },
)

graph = Graph(
    name="Complete Podcast Generator",
    nodes=[host_voice, guest_voice, dialogue, samples, full_audio],
)

graph.launch()
