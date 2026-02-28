import os
import subprocess
import argparse

def check_ffmpeg():
    """Checks if FFmpeg is installed and accessible in the system's PATH."""
    try:
        subprocess.run(
            ['ffmpeg', '-version'],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

def convert_file(input_path, to_format, quality_setting):
    """
    Converts a single audio file to a new format using FFmpeg.
    """
    if not os.path.exists(input_path):
        print(f"❌ Error: Input file not found at '{input_path}'")
        return

    base_name = os.path.splitext(input_path)[0]
    output_path = f"{base_name}.{to_format}"

    print(f"🔁 Converting '{os.path.basename(input_path)}' to .{to_format}...")

    quality_flag = '-q:a' if not quality_setting.endswith('k') else '-b:a'

    command = [
        'ffmpeg',
        '-i', input_path,
        '-vn',
        quality_flag, quality_setting,
        '-y',
        output_path
    ]

    try:
        # THE FIX IS HERE: Added errors='ignore' to handle non-UTF-8 output from ffmpeg
        result = subprocess.run(command, check=True, capture_output=True, text=True, errors='ignore')
        print(f"✅ Successfully created '{os.path.basename(output_path)}'")
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg Error during conversion of '{os.path.basename(input_path)}':")
        # Decode the error output manually with a fallback
        error_message = e.stderr.decode('utf-8', errors='replace') if isinstance(e.stderr, bytes) else e.stderr
        print(error_message)

def main():
    """Main function to parse arguments and trigger conversions."""
    print("--- 🎧 Audio Format Converter ---")

    if not check_ffmpeg():
        print("❌ CRITICAL ERROR: FFmpeg is not installed or not in your system's PATH.")
        print("   Please install it from: https://ffmpeg.org/download.html")
        return

    parser = argparse.ArgumentParser(
        description="A versatile audio converter using FFmpeg.",
        epilog="Example (default): python convert_audio.py\n"
               "Example (specific): python convert_audio.py -i my_song.wav -t mp3 -q 320k"
    )

    parser.add_argument(
        '-i', '--input',
        help="Path to a single input audio file. If not provided, runs in default batch mode."
    )
    parser.add_argument(
        '-t', '--to_format',
        default='m4a',
        help="Target audio format (e.g., m4a, mp3, ogg). Default: m4a"
    )
    parser.add_argument(
        '-s', '--from_format',
        default='flac',
        help="Source audio format to look for in batch mode. Default: flac"
    )
    parser.add_argument(
        '-q', '--quality',
        default='0',
        help="Audio quality. For M4A/AAC, '0' is best VBR. For MP3, use bitrate like '320k'. Default: 0"
    )

    args = parser.parse_args()

    if args.input:
        print(f"\n-- Single File Mode --")
        convert_file(args.input, args.to_format, args.quality)
    else:
        print(f"\n-- Default Batch Mode --")
        print(f"Scanning current directory for .{args.from_format} files to convert to .{args.to_format}...\n")

        found_files = [f for f in os.listdir('downloads') if os.path.isfile(f) and f.lower().endswith(f".{args.from_format}")]

        if not found_files:
            print(f"No .{args.from_format} files found in this directory.")
            return

        for filename in found_files:
            convert_file(filename, args.to_format, args.quality)

        print(f"\n✨ Batch conversion complete. Processed {len(found_files)} file(s).")

if __name__ == "__main__":
    main()