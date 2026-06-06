from PIL import Image
import sys

def convert_to_favicon(input_path, output_path="favicon.ico"):
    try:
        img = Image.open(input_path)
        img = img.convert("RGBA")
        sizes = [(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]
        img.save(output_path, format="ICO", sizes=sizes)
        print(f"Favicon saved as {output_path}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_to_favicon.py <input_image>")
    else:
        convert_to_favicon(sys.argv[1])
