# Showcases a full document-to-podcast pipeline: URL extraction → dialogue generation → TTS → audio combining.
import gradio as gr

from daggr import FnNode, Graph


def extract_content(url: str, custom_text: str) -> tuple[str, str]:
    """
    Extracts and cleans text content from a URL or uses custom text.
    Returns: (cleaned_text, title)
    """
    import re

    import requests
    from bs4 import BeautifulSoup

    if custom_text.strip():
        lines = custom_text.strip().split("\n")
        title = lines[0][:50] if lines else "Custom Content"
        return custom_text, title

    if not url.strip():
        return "Please provide a URL or paste your content.", "No Content"

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.find("title")
        title = title.text.strip() if title else "Untitled"

        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        article = soup.find("article") or soup.find("main") or soup.body

        if article:
            text = article.get_text(separator="\n")
            text = re.sub(r"\n\s*\n", "\n\n", text)
            text = re.sub(r" +", " ", text)
            text = text.strip()

            if len(text) > 10000:
                text = text[:10000] + "..."

            return text, title

        return "Could not extract content from URL.", title

    except Exception as e:
        return f"Error fetching URL: {str(e)}", "Error"


content_extractor = FnNode(
    fn=extract_content,
    inputs={
        "url": gr.Textbox(
            label="🔗 Article URL",
            placeholder="https://github.com/gradio-app/daggr/blob/main/README.md",
            value="",
        ),
        "custom_text": gr.Textbox(
            label="📝 Or paste your content directly",
            placeholder="Paste article text, research paper, or any content here...",
            lines=5,
        ),
    },
    outputs={
        "content": gr.Textbox(label="📄 Extracted Content", lines=10),
        "title": gr.Textbox(label="📰 Title"),
    },
)


def generate_dialogue(
    content: str, title: str, host_style: str, episode_length: str
) -> tuple[list, str]:
    """
    Generates a natural conversation script between two podcast hosts.
    Returns: (dialogue_lines for scatter, html_preview)

    In production, this would use an LLM. Demo shows expected structure.
    """
    exchanges = {
        "Short (2-3 min)": 6,
        "Medium (5-7 min)": 12,
        "Long (10+ min)": 20,
    }.get(episode_length, 8)

    dialogue = []

    dialogue.append(
        {
            "speaker": "host",
            "text": f"Welcome back to the show! Today we're diving into something fascinating: {title}. I've been really excited to discuss this one.",
            "voice_style": host_style,
        }
    )

    dialogue.append(
        {
            "speaker": "guest",
            "text": "Me too! When I first read through this, I was struck by how relevant it is. There's a lot to unpack here.",
            "voice_style": "friendly, curious",
        }
    )

    dialogue.append(
        {
            "speaker": "host",
            "text": "So let's start with the main point. Can you give our listeners the key takeaway?",
            "voice_style": host_style,
        }
    )

    dialogue.append(
        {
            "speaker": "guest",
            "text": "Absolutely. The core idea here is really about understanding the bigger picture. The author makes a compelling case that we need to think differently about this topic.",
            "voice_style": "thoughtful, explaining",
        }
    )

    for i in range((exchanges - 4) // 2):
        dialogue.append(
            {
                "speaker": "host",
                "text": f"That's a great point. What really stood out to you in section {i + 1}?",
                "voice_style": host_style,
            }
        )
        dialogue.append(
            {
                "speaker": "guest",
                "text": "Well, I think the author's argument about context is particularly strong. It challenges conventional thinking in a productive way.",
                "voice_style": "engaged, analytical",
            }
        )

    dialogue.append(
        {
            "speaker": "host",
            "text": "This has been such a great conversation. Any final thoughts for our listeners?",
            "voice_style": host_style,
        }
    )

    dialogue.append(
        {
            "speaker": "guest",
            "text": "I'd encourage everyone to check out the original piece. There's so much more depth there. Thanks for having me!",
            "voice_style": "warm, grateful",
        }
    )

    dialogue.append(
        {
            "speaker": "host",
            "text": "Thanks for listening everyone! Don't forget to subscribe and we'll see you next time.",
            "voice_style": host_style,
        }
    )

    html = f"""
    <div style="font-family: Georgia, serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #ffffff; border-radius: 12px;">
        <h2 style="border-bottom: 2px solid #333; padding-bottom: 10px; color: #1a1a1a;">🎙️ {title}</h2>
        <p style="color: #1a1a1a; font-style: italic;">Episode Preview • {len(dialogue)} segments</p>
    """

    for line in dialogue[:6]:
        speaker_color = "#2563eb" if line["speaker"] == "host" else "#059669"
        speaker_label = "🎤 Host" if line["speaker"] == "host" else "🗣️ Guest"
        html += f"""
        <div style="margin: 15px 0; padding: 10px; background: {"#f0f9ff" if line["speaker"] == "host" else "#f0fdf4"}; border-radius: 8px;">
            <strong style="color: {speaker_color};">{speaker_label}</strong>
            <p style="margin: 5px 0 0 0; color: #1a1a1a;">{line["text"]}</p>
        </div>
        """

    if len(dialogue) > 6:
        html += f"<p style='color: #1a1a1a; text-align: center;'>... and {len(dialogue) - 6} more segments</p>"

    html += "</div>"

    return dialogue, html


dialogue_generator = FnNode(
    fn=generate_dialogue,
    inputs={
        "content": content_extractor.content,
        "title": content_extractor.title,
        "host_style": gr.Dropdown(
            label="🎭 Host Personality",
            choices=[
                "enthusiastic, energetic",
                "calm, professional",
                "casual, conversational",
                "intellectual, thoughtful",
            ],
            value="enthusiastic, energetic",
        ),
        "episode_length": gr.Radio(
            label="⏱️ Episode Length",
            choices=["Short (2-3 min)", "Medium (5-7 min)", "Long (10+ min)"],
            value="Medium (5-7 min)",
        ),
    },
    outputs={
        "dialogue": gr.JSON(label="📋 Dialogue Script", visible=False),
        "preview": gr.HTML(label="👀 Script Preview"),
    },
)


def generate_all_voice_segments(dialogue: list) -> list:
    """
    Generate TTS audio for ALL dialogue lines in a single node.
    Bypasses daggr's scatter/gather which has a bug.
    """
    from gradio_client import Client

    client = Client("ysharma/Qwen3-TTS")
    audio_files = []

    for i, item in enumerate(dialogue):
        print(f"Generating audio for segment {i + 1}/{len(dialogue)}...")
        try:
            result = client.predict(
                text=item["text"],
                language="Auto",
                voice_description=item.get("voice_style", "friendly"),
                api_name="/generate_voice_design",
            )
            audio_path = result[0] if isinstance(result, tuple) else result
            audio_files.append(audio_path)
            print(f"  ✓ Generated: {audio_path}")
        except Exception as e:
            print(f"  ✗ Error on segment {i + 1}: {e}")
            audio_files.append(None)

    return audio_files


voice_generator = FnNode(
    fn=generate_all_voice_segments,
    inputs={
        "dialogue": dialogue_generator.dialogue,
    },
    outputs={
        "audio_files": gr.JSON(label="🔊 Generated Audio Files", visible=False),
    },
)


def combine_podcast(
    audio_files: list,
    dialogue: list,
    title: str,
) -> tuple[str, str]:
    """
    Combines all audio segments into a final podcast episode.
    """
    import tempfile

    from pydub import AudioSegment

    combined = AudioSegment.silent(duration=500)
    successful_segments = 0

    for i, audio_path in enumerate(audio_files):
        if audio_path:
            try:
                segment = AudioSegment.from_file(audio_path)
                combined += segment
                pause_duration = 300 if i < len(dialogue) - 1 else 0
                combined += AudioSegment.silent(duration=pause_duration)
                successful_segments += 1
            except Exception as e:
                print(f"Error loading segment {i}: {e}")
                continue

    combined += AudioSegment.silent(duration=1000)
    combined = combined.normalize()

    output_path = tempfile.mktemp(suffix=".mp3")
    combined.export(output_path, format="mp3", bitrate="192k")

    duration_mins = len(combined) / 60000
    summary = f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 16px; border-radius: 16px; font-family: Arial, sans-serif;">
    <h2 style="margin: 0 0 12px 0; font-size: 18px;">🎙️ Podcast Ready!</h2>
    <h3 style="margin: 0 0 12px 0; font-weight: normal; opacity: 0.9; font-size: 14px;">{title}</h3>
    <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; text-align: center;">
        <div style="background: rgba(255,255,255,0.2); padding: 8px; border-radius: 8px;">
            <div style="font-size: 20px; font-weight: bold;">{duration_mins:.1f}</div>
            <div style="font-size: 11px; opacity: 0.8;">minutes</div>
        </div>
        <div style="background: rgba(255,255,255,0.2); padding: 8px; border-radius: 8px;">
            <div style="font-size: 20px; font-weight: bold;">{successful_segments}</div>
            <div style="font-size: 11px; opacity: 0.8;">segments</div>
        </div>
        <div style="background: rgba(255,255,255,0.2); padding: 8px; border-radius: 8px;">
            <div style="font-size: 20px; font-weight: bold;">2</div>
            <div style="font-size: 11px; opacity: 0.8;">speakers</div>
        </div>
    </div>
</div>
    """

    return output_path, summary


final_podcast = FnNode(
    fn=combine_podcast,
    inputs={
        "audio_files": voice_generator.audio_files,
        "dialogue": dialogue_generator.dialogue,
        "title": content_extractor.title,
    },
    outputs={
        "podcast": gr.Audio(label="🎙️ Final Podcast Episode"),
        "summary": gr.HTML(label="📊 Episode Summary"),
    },
)

graph = Graph(
    name="🎙️ Document to Podcast Generator",
    nodes=[
        content_extractor,
        dialogue_generator,
        voice_generator,
        final_podcast,
    ],
)

if __name__ == "__main__":
    graph.launch()
