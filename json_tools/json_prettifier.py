import json
import sys


def prettify_json(input_file, output_file):
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)

        with open(output_file, 'w') as f:
            # indent=4 makes it readable; sort_keys=True keeps it organized
            json.dump(data, f, indent=4, sort_keys=True)

        print(f"✅ Success! Prettified JSON saved to: {output_file}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    # Usage: python prettify.py input.json output.json
    if len(sys.argv) > 2:
        prettify_json(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python prettify.py <source_file> <destination_file>")