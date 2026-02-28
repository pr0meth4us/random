import json
import sys


def get_structure(data, indent="", is_last=True):
    # Branch symbols
    marker = "└── " if is_last else "├── "

    if isinstance(data, dict):
        items = list(data.items())
        for i, (key, value) in enumerate(items):
            last_item = (i == len(items) - 1)
            new_marker = "└── " if last_item else "├── "

            if isinstance(value, (dict, list)):
                print(f"{indent}{new_marker}📂 {key} ({type(value).__name__})")
                # Add vertical line for nesting if not the last item
                extension = "    " if last_item else "│   "
                get_structure(value, indent + extension, last_item)
            else:
                print(f"{indent}{new_marker}📄 {key}: {type(value).__name__}")

    elif isinstance(data, list):
        if len(data) > 0:
            print(f"{indent}└── 📦 List contains {type(data[0]).__name__} items")
            get_structure(data[0], indent + "    ", True)
        else:
            print(f"{indent}└── 📦 (Empty List)")


def read_structure(file_path):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        print(f"--- Structure of {file_path} ---")
        get_structure(data)
        print("-" * 30)
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        read_structure(sys.argv[1])
    else:
        print("Usage: python structure.py <file_path>")