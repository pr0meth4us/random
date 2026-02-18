import json
import html
import os
import re
import sys

def format_tiktok_card(link):
    """Mnemosyne-style TikTok card using dark-mode aesthetics."""
    # Matches the styling logic from app/utils/formatContent.tsx [cite: 267, 268]
    return f"""
    <div style="margin-top: 10px; border-radius: 12px; overflow: hidden; background-color: #000; border: 1px solid #333;">
        <a href="{link}" target="_blank" style="text-decoration: none; display: flex; align-items: center; padding: 12px;">
            <div style="width: 40px; height: 40px; background: #222; border-radius: 50%; display: flex; items-center; justify-content: center; margin-right: 12px;">
                <svg viewBox="0 0 24 24" width="24" height="24" fill="#fff"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/></svg>
            </div>
            <span style="color: #fff; font-weight: 600; font-family: sans-serif; font-size: 14px;">TikTok Video</span>
        </a>
    </div>
    """

def format_image_embed(link):
    """Mnemosyne-style image handling."""
    # Matches the link cleaning and rendering from app/utils/ExtractText.tsx [cite: 244, 277]
    return f"""
    <div style="margin-top: 8px;">
        <a href="{link}" target="_blank">
            <img src="{link}" style="max-width: 100%; max-height: 300px; border-radius: 10px; display: block;" />
        </a>
    </div>
    """

def render_chat_to_html(json_file_path, output_html_path, display_as_me_user=None):
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    messages = data.get("messages", [])
    total_messages = len(messages)

    if not messages:
        return

    unique_senders = list(dict.fromkeys(m.get("sender") for m in messages if m.get("sender")))

    if not display_as_me_user and unique_senders:
        display_as_me_user = unique_senders[0]

    # Mnemosyne Regex Patterns [cite: 243, 244]
    tiktok_regex = r"(https?://(?:www\.)?tiktokv\.com/[@\w/\-]+)"
    image_regex = r"(https?://\S+\.(?:png|jpg|jpeg|gif|webp))"

    # Your original iOS/Clean styling [cite: 246]
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, sans-serif; background-color: #f0f2f5; padding: 20px; display: flex; justify-content: center; }}
        .chat-container {{ width: 100%; max-width: 700px; display: flex; flex-direction: column; gap: 10px; }}
        .message {{ padding: 10px 15px; border-radius: 18px; max-width: 75%; font-size: 15px; line-height: 1.4; position: relative; }}
        .message.me {{ background-color: #007aff; color: white; align-self: flex-end; border-bottom-right-radius: 4px; }}
        .message.other {{ background-color: #e5e5ea; color: black; align-self: flex-start; border-bottom-left-radius: 4px; }}
        .sender {{ font-size: 11px; font-weight: 600; margin-bottom: 3px; opacity: 0.7; }}
        .meta {{ font-size: 10px; margin-top: 5px; opacity: 0.5; }}
    </style>
</head>
<body>
    <div class="chat-container">
"""

    for i, msg in enumerate(messages, 1):
        # Progress Loader
        sys.stdout.write(f"\r🚀 Processing: {i}/{total_messages} messages...")
        sys.stdout.flush()

        sender_name = msg.get("sender") or "Unknown"
        sender_class = "me" if sender_name == display_as_me_user else "other"
        raw_msg = str(msg.get("message") or "")
        source = msg.get("source", "Unknown")

        sanitized_text = html.escape(raw_msg)
        tiktok_extra = ""

        # Apply Mnemosyne logic for TikTok sources [cite: 242]
        if source.lower() == "tiktok":
            # Link detection [cite: 243]
            tk_match = re.search(tiktok_regex, raw_msg)
            if tk_match:
                tiktok_extra += format_tiktok_card(tk_match.group(0))

            img_match = re.search(image_regex, raw_msg)
            if img_match:
                tiktok_extra += format_image_embed(img_match.group(0))

        # Original media handling for non-tiktok or specific attachments [cite: 246]
        media_html = ""
        if source.lower() != "tiktok" and msg.get("has_media") and msg.get("media_path"):
            m_path = msg.get("media_path")
            if str(msg.get("media_type")).lower() in ["image", "gif"]:
                media_html = f'<div style="margin-top:8px;"><img src="{m_path}" style="max-width:100%; border-radius:8px;"/></div>'
            elif str(msg.get("media_type")).lower() == "video":
                media_html = f'<div style="margin-top:8px;"><video src="{m_path}" controls style="max-width:100%; border-radius:8px;"></video></div>'

        html_content += f"""
        <div class="message {sender_class}">
            <div class="sender">{sender_name}</div>
            <div>{sanitized_text}</div>
            {tiktok_extra}
            {media_html}
            <div class="meta">{source} • {msg.get("timestamp", "")}</div>
        </div>"""

    html_content += "</div></body></html>"

    with open(output_html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n\n✅ Done! File saved as: {output_html_path}")

if __name__ == "__main__":
    render_chat_to_html("2026-02-18T233422.200.json", "hybrid_chat.html", display_as_me_user="Adam")