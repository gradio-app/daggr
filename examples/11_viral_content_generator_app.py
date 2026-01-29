# Showcases a social media content pipeline: idea expansion → parallel image/video generation → content packaging.
import random

import gradio as gr

from daggr import FnNode, GradioNode, Graph


def expand_content_idea(
    topic: str, platform: str, tone: str, include_cta: bool
) -> tuple[str, str, str, str, str]:
    """
    Expands a simple topic into full content strategy.
    Returns: (image_prompt, alt_image_prompt, video_prompt, caption, hashtags)

    In production, use an LLM for more creative output.
    """

    platform_styles = {
        "Instagram": {
            "aspect": "square, centered composition",
            "tone_prefix": "aesthetic, instagram-worthy",
            "video_style": "smooth transitions, satisfying",
        },
        "TikTok": {
            "aspect": "vertical, dynamic framing",
            "tone_prefix": "eye-catching, bold",
            "video_style": "fast-paced, trendy",
        },
        "Twitter/X": {
            "aspect": "horizontal, clean design",
            "tone_prefix": "attention-grabbing",
            "video_style": "informative, quick",
        },
        "LinkedIn": {
            "aspect": "professional, clean",
            "tone_prefix": "business-appropriate, polished",
            "video_style": "professional, educational",
        },
    }

    style = platform_styles.get(platform, platform_styles["Instagram"])

    base_prompt = f"{style['tone_prefix']}, {topic}, {tone} mood, {style['aspect']}, high quality, trending"
    image_prompt = f"{base_prompt}, vibrant colors, professional photography style"
    alt_image_prompt = f"{base_prompt}, minimalist design, artistic interpretation"

    video_prompt = (
        f"{topic}, {style['video_style']}, {tone} atmosphere, cinematic, 4k quality"
    )

    tone_emojis = {
        "Professional": "📊",
        "Fun & Playful": "🎉",
        "Inspirational": "✨",
        "Educational": "💡",
        "Trending/Viral": "🔥",
    }
    emoji = tone_emojis.get(tone, "✨")

    hook = f"{emoji} {topic.capitalize()}"
    body = f"Here's something that changed my perspective on {topic}..."
    cta = "\n\n👇 Drop your thoughts below!" if include_cta else ""
    caption = f"{hook}\n\n{body}{cta}"

    topic_words = topic.lower().replace(",", "").split()
    base_hashtags = [f"#{word}" for word in topic_words[:3] if len(word) > 3]
    platform_hashtags = {
        "Instagram": ["#instagood", "#photooftheday", "#explore"],
        "TikTok": ["#fyp", "#viral", "#trending"],
        "Twitter/X": ["#tech", "#innovation"],
        "LinkedIn": ["#leadership", "#growth", "#business"],
    }
    all_hashtags = base_hashtags + platform_hashtags.get(platform, [])[:3]
    hashtags = " ".join(all_hashtags[:7])

    return image_prompt, alt_image_prompt, video_prompt, caption, hashtags


content_strategy = FnNode(
    fn=expand_content_idea,
    inputs={
        "topic": gr.Textbox(
            label="💡 What's your content about?",
            placeholder="e.g., AI tools that save time, morning routine tips, startup lessons",
            value="the future of AI and creativity",
            lines=2,
        ),
        "platform": gr.Dropdown(
            label="📱 Primary Platform",
            choices=["Instagram", "TikTok", "Twitter/X", "LinkedIn"],
            value="Instagram",
        ),
        "tone": gr.Radio(
            label="🎭 Content Tone",
            choices=[
                "Professional",
                "Fun & Playful",
                "Inspirational",
                "Educational",
                "Trending/Viral",
            ],
            value="Inspirational",
        ),
        "include_cta": gr.Checkbox(label="📣 Include Call-to-Action", value=True),
    },
    outputs={
        "image_prompt": gr.Textbox(label="🖼️ Primary Image Prompt"),
        "alt_image_prompt": gr.Textbox(label="🖼️ Alternative Image Prompt"),
        "video_prompt": gr.Textbox(label="🎬 Video Prompt"),
        "caption": gr.Textbox(label="📝 Caption", lines=4),
        "hashtags": gr.Textbox(label="#️⃣ Hashtags"),
    },
)

primary_image = GradioNode(
    space_or_url="hf-applications/Z-Image-Turbo",
    api_name="/generate_image",
    inputs={
        "prompt": content_strategy.image_prompt,
        "seed": random.randint(0, 999999),
        "width": 1024,
        "height": 1024,
    },
    outputs={
        "image": gr.Image(label="🖼️ Primary Image"),
    },
)

alt_image = GradioNode(
    space_or_url="hf-applications/Z-Image-Turbo",
    api_name="/generate_image",
    inputs={
        "prompt": content_strategy.alt_image_prompt,
        "seed": random.randint(0, 999999),
        "width": 1024,
        "height": 1024,
    },
    outputs={
        "image": gr.Image(label="🖼️ Alternative Image (A/B Test)"),
    },
)

content_video = GradioNode(
    space_or_url="Lightricks/ltx-2-distilled",
    api_name="/generate_video",
    inputs={
        "input_image": primary_image.image,
        "prompt": content_strategy.video_prompt,
        "duration": 3,
    },
    outputs={
        "video": gr.Video(label="🎬 Animated Content"),
        "seed": None,
    },
)


def package_content(
    primary_img: str,
    alt_img: str,
    video: str,
    caption: str,
    hashtags: str,
    platform: str,
) -> tuple[str, str]:
    """
    Packages all content and generates a preview/summary.
    """
    import json

    package = {
        "platform": platform,
        "primary_image": primary_img,
        "alternative_image": alt_img,
        "video": video,
        "caption": caption,
        "hashtags": hashtags,
        "ready_to_post": all([primary_img, caption]),
    }

    preview_html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 500px; margin: 0 auto;">
        
        <!-- Phone Frame -->
        <div style="background: #000; border-radius: 40px; padding: 20px 12px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25);">
            
            <!-- Status Bar -->
            <div style="display: flex; justify-content: space-between; color: white; font-size: 12px; padding: 0 20px 10px;">
                <span>9:41</span>
                <span>📶 100%</span>
            </div>
            
            <!-- App Header -->
            <div style="background: linear-gradient(135deg, #833ab4, #fd1d1d, #fcb045); padding: 12px 16px; color: white; font-weight: bold;">
                📱 {platform}
            </div>
            
            <!-- Post Preview -->
            <div style="background: white; padding: 16px;">
                
                <!-- User Info -->
                <div style="display: flex; align-items: center; margin-bottom: 12px;">
                    <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #833ab4, #fcb045); border-radius: 50%;"></div>
                    <div style="margin-left: 12px;">
                        <div style="font-weight: bold; color: #666; font-size: 14px;">your_brand</div>
                        <div style="font-size: 12px; color: #666;">Just now</div>
                    </div>
                </div>
                
                <!-- Image Preview -->
                <div style="background: #f0f0f0; height: 300px; border-radius: 8px; display: flex; align-items: center; justify-content: center; margin-bottom: 12px; overflow: hidden;">
                    {"<img src='/gradio_api/file=" + primary_img + "' style='width: 100%; height: 100%; object-fit: cover;' />" if primary_img else "<span style='color: #999;'>📷 Image Preview</span>"}
                </div>
                
                <!-- Caption -->
                <div style="font-size: 14px; line-height: 1.5; color: #666; margin-bottom: 8px;">
                    <span style="font-weight: bold;">your_brand</span> {caption[:150]}{"..." if len(caption) > 150 else ""}
                </div>
                
                <!-- Hashtags -->
                <div style="font-size: 12px; color: #00376b;">
                    {hashtags}
                </div>
                
                <!-- Engagement -->
                <div style="display: flex; gap: 16px; margin-top: 12px; padding-top: 12px; color: #333; border-top: 1px solid #eee;">
                    <span>❤️ 0</span>
                    <span>💬 0</span>
                    <span>📤 Share</span>
                </div>
            </div>
            
        </div>
        
        <!-- Content Summary -->
        <div style="margin-top: 20px; padding: 16px; color: #666; background: #f8fafc; border-radius: 12px;">
            <h3 style="margin: 0 0 12px 0; font-size: 16px;">📦 Content Package Ready!</h3>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; color: #2563eb; font-size: 13px;">
                <div>✅ Primary Image</div>
                <div>✅ A/B Test Image</div>
                <div>{"✅" if video else "⏳"} Video Content</div>
                <div>✅ Caption & Hashtags</div>
            </div>
        </div>
        
    </div>
    """

    return json.dumps(package, indent=2), preview_html


final_package = FnNode(
    fn=package_content,
    inputs={
        "primary_img": primary_image.image,
        "alt_img": alt_image.image,
        "video": content_video.video,
        "caption": content_strategy.caption,
        "hashtags": content_strategy.hashtags,
        "platform": content_strategy.image_prompt,
    },
    outputs={
        "package_json": gr.Code(label="📦 Content Package (JSON)", language="json"),
        "preview": gr.HTML(label="📱 Post Preview"),
    },
)

graph = Graph(
    name="📱 Viral Content Generator",
    nodes=[
        content_strategy,
        primary_image,
        alt_image,
        content_video,
        final_package,
    ],
)

if __name__ == "__main__":
    graph.launch()
