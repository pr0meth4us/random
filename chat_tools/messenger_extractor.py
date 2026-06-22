#!/usr/bin/env python3
"""
Facebook Messenger HTML Chat Extractor
Supports both old (2022-era) and new (2026-era) FB export formats.

Usage:
    python3 extract_chat.py message_1.html [options]

Options:
    --output, -o    Output file path
    --format, -f    csv | json | txt (default: csv)
    --sender, -s    Filter by sender name (partial match, case-insensitive)
    --text-only     Skip messages with no text
    --no-reactions  Don't include reaction data
    --verbose, -v   Print progress
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup


def parse_messages(html_path: str, verbose: bool = False) -> dict:
    if verbose:
        print(f"Reading {html_path}...", file=sys.stderr)

    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    title_el = soup.find("title")
    title = title_el.get_text(strip=True) if title_el else "Unknown"

    # Detect format: new uses <section class="_a6-g">, old uses <div class="_a6-g">
    new_format = bool(soup.find("section", class_="_a6-g"))
    if verbose:
        print(f"Format: {'new (2026)' if new_format else 'old (2022)'}", file=sys.stderr)

    # Participants
    participants = []
    if new_format:
        h2 = soup.find("h2", class_="_a6-h")
        if h2 and "Participants:" in h2.get_text():
            raw = h2.get_text(strip=True).replace("Participants:", "").strip()
            participants = [p.strip() for p in raw.split(",")]
    else:
        for block in soup.find_all("div", class_="_a6-g"):
            sender_div = block.find("div", class_="_a6-h")
            if sender_div and "Participants:" in sender_div.get_text():
                raw = sender_div.get_text(strip=True).replace("Participants:", "").strip()
                participants = [p.strip() for p in raw.split(",")]
                break

    if verbose:
        print(f"Title: {title}", file=sys.stderr)
        print(f"Participants: {len(participants)}", file=sys.stderr)

    if new_format:
        messages = parse_new_format(soup, verbose)
    else:
        messages = parse_old_format(soup, verbose)

    return {"title": title, "participants": participants, "messages": messages}


def parse_new_format(soup, verbose):
    sections = soup.find_all("section", class_="_a6-g")
    real = [s for s in sections if s.find("h2", class_="_a6-i") and s.find("div", class_="_a6-p")]
    if verbose:
        print(f"Found {len(real)} message blocks", file=sys.stderr)

    messages = []
    for s in real:
        sender_el = s.find("h2", class_="_a6-i")
        sender = sender_el.get_text(strip=True) if sender_el else ""
        if not sender or sender.startswith("Participants:"):
            continue

        content_div = s.find("div", class_="_a6-p")
        ts_div = s.find("div", class_="_a72d")
        timestamp = ts_div.get_text(strip=True) if ts_div else ""

        messages.append(extract_content(sender, timestamp, content_div))

    messages.reverse()
    if verbose:
        print(f"Parsed {len(messages)} messages", file=sys.stderr)
    return messages


def parse_old_format(soup, verbose):
    message_blocks = [
        m for m in soup.find_all("div", class_="_a6-g")
        if m.find("div", class_="_a6-h") and m.find("div", class_="_a6-p")
    ]
    if verbose:
        print(f"Found {len(message_blocks)} message blocks", file=sys.stderr)

    messages = []
    for block in message_blocks:
        sender_div = block.find("div", class_="_a6-h")
        if not sender_div:
            continue
        sender = sender_div.get_text(strip=True)
        if sender.startswith("Participants:"):
            continue

        content_div = block.find("div", class_="_a6-p")
        ts_div = block.find("div", class_="_a72d")
        timestamp = ts_div.get_text(strip=True) if ts_div else ""

        messages.append(extract_content(sender, timestamp, content_div))

    messages.reverse()
    if verbose:
        print(f"Parsed {len(messages)} messages", file=sys.stderr)
    return messages


def extract_content(sender, timestamp, content_div):
    text_parts = []
    unsent = False

    for child in content_div.find_all("div"):
        if child.get_text() and "unsent" in child.get_text().lower():
            unsent = True
            continue
        if child.find(["img", "audio", "video", "a", "ul"]):
            continue
        t = child.get_text(strip=True)
        if t:
            text_parts.append(t)

    # Deduplicate consecutive identical parts
    deduped = []
    for t in text_parts:
        if not deduped or t != deduped[-1]:
            deduped.append(t)
    text = " ".join(deduped)

    images = [img["src"] for img in content_div.find_all("img") if img.get("src")]
    stickers = [s for s in images if "stickers_used" in s]
    photos = [i for i in images if "stickers_used" not in i]
    audio_files = [a["src"] for a in content_div.find_all("audio") if a.get("src")]
    video_files = [v["src"] for v in content_div.find_all("video") if v.get("src")]

    attachment_note = ""
    for div in content_div.find_all("div"):
        t = div.get_text(strip=True)
        if "ឯកសារភ្ជាប់" in t or "attachment" in t.lower():
            attachment_note = t
            break

    reactions = []
    reactions_ul = content_div.find("ul", class_="_a6-q")
    if reactions_ul:
        for li in reactions_ul.find_all("li"):
            reactions.append(li.get_text(strip=True))

    return {
        "timestamp": timestamp,
        "sender": sender,
        "text": text,
        "photos": photos,
        "stickers": stickers,
        "audio": audio_files,
        "video": video_files,
        "reactions": reactions,
        "unsent": unsent,
        "attachment_note": attachment_note,
    }


def filter_messages(data, sender_filter=None, text_only=False):
    msgs = data["messages"]
    if sender_filter:
        msgs = [m for m in msgs if sender_filter.lower() in m["sender"].lower()]
    if text_only:
        msgs = [m for m in msgs if m["text"]]
    return {**data, "messages": msgs}


def write_csv(data, output_path, include_reactions=True):
    fieldnames = ["timestamp", "sender", "text", "photos", "stickers", "audio", "video", "unsent", "attachment_note"]
    if include_reactions:
        fieldnames.append("reactions")
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in data["messages"]:
            row = {k: m[k] for k in fieldnames if k in m}
            for key in ["photos", "stickers", "audio", "video", "reactions"]:
                if key in row and isinstance(row[key], list):
                    row[key] = " | ".join(row[key])
            writer.writerow(row)


def write_json(data, output_path, include_reactions=True):
    out = dict(data)
    if not include_reactions:
        out["messages"] = [{k: v for k, v in m.items() if k != "reactions"} for m in out["messages"]]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


def write_txt(data, output_path, include_reactions=True):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"=== {data['title']} ===\n")
        if data["participants"]:
            f.write(f"Participants: {', '.join(data['participants'][:5])}")
            if len(data["participants"]) > 5:
                f.write(f" and {len(data['participants']) - 5} more")
            f.write("\n")
        f.write(f"Total messages: {len(data['messages'])}\n")
        f.write("=" * 60 + "\n\n")
        for m in data["messages"]:
            f.write(f"[{m['timestamp']}] {m['sender']}\n")
            if m["unsent"]:
                f.write("  <message was unsent>\n")
            elif m["text"]:
                f.write(f"  {m['text']}\n")
            if m["photos"]: f.write(f"  [📷 {len(m['photos'])} photo(s)]\n")
            if m["stickers"]: f.write(f"  [🎭 sticker]\n")
            if m["audio"]: f.write(f"  [🔊 audio clip]\n")
            if m["video"]: f.write(f"  [🎥 video]\n")
            if m["attachment_note"]: f.write(f"  [📎 {m['attachment_note']}]\n")
            if include_reactions and m["reactions"]:
                f.write(f"  Reactions: {', '.join(m['reactions'])}\n")
            f.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Extract Facebook Messenger HTML chat export")
    parser.add_argument("input")
    parser.add_argument("--output", "-o")
    parser.add_argument("--format", "-f", choices=["csv", "json", "txt"], default="csv")
    parser.add_argument("--sender", "-s")
    parser.add_argument("--text-only", action="store_true")
    parser.add_argument("--no-reactions", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output or str(input_path.parent / f"chat_{input_path.stem}.{args.format}")

    data = parse_messages(str(input_path), verbose=args.verbose)
    data = filter_messages(data, sender_filter=args.sender, text_only=args.text_only)

    msg_count = len(data["messages"])
    include_reactions = not args.no_reactions

    if args.format == "csv":
        write_csv(data, output_path, include_reactions)
    elif args.format == "json":
        write_json(data, output_path, include_reactions)
    elif args.format == "txt":
        write_txt(data, output_path, include_reactions)

    print(f"Done. {msg_count} messages written to: {output_path}")
    if data["title"]:
        print(f"Conversation: {data['title']}")


if __name__ == "__main__":
    main()