import os
import cv2
import numpy as np
import wave
from PIL import Image, ImageDraw, ImageFont
import subprocess

def create_beep_audio(filename, duration_sec=303, countdown_sec=300, sample_rate=44100):
    """Generates a mono audio track with countdown beeps and a final alarm."""
    print("Generating audio track...")
    audio_data = np.zeros(sample_rate * duration_sec, dtype=np.float32)

    def insert_beep(start_sec, dur_sec, freq=1000.0, volume=0.5):
        t = np.arange(0, dur_sec, 1.0 / sample_rate)
        beep = volume * np.sin(2 * np.pi * freq * t)
        
        # Smooth fade-in and fade-out to prevent clicks
        fade_len = min(int(0.01 * sample_rate), len(beep) // 2)
        fade_in = np.linspace(0, 1, fade_len)
        fade_out = np.linspace(1, 0, fade_len)
        beep[:fade_len] *= fade_in
        beep[-fade_len:] *= fade_out

        start_idx = int(start_sec * sample_rate)
        end_idx = start_idx + len(beep)
        if end_idx <= len(audio_data):
            audio_data[start_idx:end_idx] = beep

    # 1. Beep 3 times when it hits 4:00 (which is exactly t = 60s elapsed in a 5-minute countdown), spaced by 100ms
    insert_beep(60.0, 0.15, freq=1000.0, volume=0.5)
    insert_beep(60.25, 0.15, freq=1000.0, volume=0.5)
    insert_beep(60.50, 0.15, freq=1000.0, volume=0.5)

    # 2. Short warning beeps at 3, 2, 1 seconds remaining (t = 297, 298, 299)
    insert_beep(countdown_sec - 3.0, 0.15, freq=1000.0, volume=0.4)
    insert_beep(countdown_sec - 2.0, 0.15, freq=1000.0, volume=0.4)
    insert_beep(countdown_sec - 1.0, 0.15, freq=1000.0, volume=0.4)

    # 3. Final alarm beeps (three beeps) at t = 300s
    insert_beep(countdown_sec + 0.0, 0.5, freq=1000.0, volume=0.6)
    insert_beep(countdown_sec + 0.75, 0.5, freq=1000.0, volume=0.6)
    insert_beep(countdown_sec + 1.50, 0.8, freq=1000.0, volume=0.6)

    # Convert float32 to 16-bit PCM integer
    int_data = (audio_data * 32767).astype(np.int16)

    # Write to WAV file
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 2 bytes per sample (16-bit)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(int_data.tobytes())
    print(f"Audio track saved to {filename}")
# (Rest of get_text_frame remains unchanged)
# Let's target lines after 80 to update generate_video_frames calls and main() function.


def get_text_frame(text, width, height, font_path, max_width=1800, max_height=900):
    """Renders a frame with the countdown text centered and maximized in size."""
    # Find the optimal font size starting at 100
    font_size = 100
    font = ImageFont.truetype(font_path, font_size)
    bbox = font.getbbox(text)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    # Scale the font size to fit constraints
    scale_w = max_width / w
    scale_h = max_height / h
    optimal_size = int(font_size * min(scale_w, scale_h))

    # Load font with the optimal size
    font = ImageFont.truetype(font_path, optimal_size)
    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Create white canvas
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # Center the text accounting for bounding box offsets
    x = (width - text_w) // 2 - bbox[0]
    y = (height - text_h) // 2 - bbox[1]

    draw.text((x, y), text, font=font, fill="black")
    return np.array(img)

def generate_video_frames(filename, font_path, width=1920, height=1080, fps=10, countdown_sec=180, extra_sec=3):
    """Generates the silent video track displaying the countdown timer."""
    print("Generating video frames...")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, fps, (width, height))

    total_frames = (countdown_sec + extra_sec) * fps

    # Cache frames for the unique text representations to avoid redundant rendering
    frame_cache = {}

    for f in range(total_frames):
        current_sec = f // fps
        remaining_sec = max(0, countdown_sec - current_sec)
        
        minutes = remaining_sec // 60
        seconds = remaining_sec % 60
        text = f"{minutes}:{seconds:02d}"

        if text not in frame_cache:
            # Render and cache the frame image
            img_np = get_text_frame(text, width, height, font_path)
            # OpenCV expects BGR
            frame_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            frame_cache[text] = frame_bgr
        
        out.write(frame_cache[text])

        if f % (10 * fps) == 0:
            print(f"Rendered frame {f}/{total_frames} ({current_sec}s / {countdown_sec + extra_sec}s)")

    out.release()
    print(f"Silent video saved to {filename}")

def main():
    # Workspace paths
    scratch_dir = "/Users/nicksng/code/random/scratch"
    downloads_dir = "/Users/nicksng/code/random/downloads"
    os.makedirs(scratch_dir, exist_ok=True)
    os.makedirs(downloads_dir, exist_ok=True)

    temp_audio = os.path.join(scratch_dir, "temp_audio.wav")
    temp_video = os.path.join(scratch_dir, "temp_video.mp4")
    output_video = os.path.join(downloads_dir, "5 Minute Timer.mp4")

    # Font path
    font_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    if not os.path.exists(font_path):
        font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
    if not os.path.exists(font_path):
        # Fallback to standard library/default if supplemental doesn't exist
        font_path = "/System/Library/Fonts/Helvetica.dfont"
        
    print(f"Using font: {font_path}")

    # Generate assets
    create_beep_audio(temp_audio, duration_sec=303, countdown_sec=300)
    generate_video_frames(temp_video, font_path, countdown_sec=300, extra_sec=3, fps=10)

    # Mux using ffmpeg
    print("Muxing video and audio with FFmpeg...")
    cmd = [
        "ffmpeg", "-y",
        "-i", temp_video,
        "-i", temp_audio,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_video
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Success! Timer video generated at: {output_video}")
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg error: {e}")
    finally:
        # Clean up temporary files
        if os.path.exists(temp_audio):
            os.remove(temp_audio)
        if os.path.exists(temp_video):
            os.remove(temp_video)

if __name__ == "__main__":
    main()
