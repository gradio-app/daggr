import gradio as gr

from daggr import FnNode, InferenceNode, GradioNode


host_voice = GradioNode(
    space_or_url="qwen3tts/qwen3tts-v1-0",
    api_name="generate_voice_design", 
    inputs={
        "voice_description": gr.Textbox(label="Host Voice Description", value="Deep British voice that is very professional and authoritative...")
        "language": "auto",
        "text": "Hi! I'm the host of podcast. It's going to be a great episode!",
    }
    outputs={
        "audio": gr.Audio(label="Host Voice"),
        "status": gr.Text(visible=False),
    }
)


guest_voice = GradioNode(
    space_or_url="qwen3tts/qwen3tts-v1-0",
    api_name="generate_voice_design", 
    inputs={
        "voice_description": gr.Textbox(label="Guest Voice Description", value="Energetic, friendly young voice with American accent...")
        "language": "auto",
        "text": "Hi! I'm the guest of podcast. Super excited to be here!",
    }
    outputs={
        "audio": gr.Audio(label="Host Voice"),
        "status": gr.Text(visible=False),
    }
)

def generate_dialogue(topic: str, host_voice: str, guest_voice: str) -> list[dict]:
    import os
    from huggingface_hub import InferenceClient

    client = InferenceClient(
        api_key=os.environ["HF_TOKEN"],
    )

    completion = client.chat.completions.create(
        model="moonshotai/Kimi-K2-Instruct-0905:groq",
        messages=[
            {
                "role": "user",
                "content": "Generate a dialogue script for a podcast episode about the topic: {topic}. It should be a conversation between a host and a guest. Return the script as a JSON list with the following structure: [{'speaker': 'host', 'text': '...'}, {'speaker': 'guest', 'text': '...'}, ...]"
            }
        ],
    )

    print(completion.choices[0].message)      

dialogue = FnNode(
    fn=generate_dialogue,
    inputs={"topic": gr.Textbox(label="Topic", value="AI in healthcare...")},
    outputs={"dialogue": gr.JSON(label="Dialogue", visible=False), "markdown": gr.Markdown(label="Dialogue")}
)

graph = Graph(name="Podcast Generator")

graph \
    .edge(host_voice, dialogue.host_voice)
    .edge(guest_voice, dialogue.guest_voice)

graph.launch()



