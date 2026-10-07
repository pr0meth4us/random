"""Parse Gemini JSON responses, tolerating the ```json code fences it sometimes
wraps them in even when asked for raw JSON."""
import json


def strip_json_fences(text):
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def parse_gemini_json(text):
    return json.loads(strip_json_fences(text))


if __name__ == "__main__":
    assert strip_json_fences('```json\n[1,2]\n```') == "[1,2]"
    assert strip_json_fences('```\n{"a":1}\n```') == '{"a":1}'
    assert strip_json_fences('plain') == "plain"
    assert parse_gemini_json('```json\n{"a": 1}\n```') == {"a": 1}
    print("gemini_json self-check passed")
