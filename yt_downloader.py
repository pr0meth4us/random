import yt_dlp
import os
import re
import subprocess

def clean_filename(filename):
    """Removes invalid characters from a filename and tidies up whitespace."""
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'\s+', ' ', filename).strip()
    return filename

def download_video(search_query):
    """Searches for a video and downloads its audio, prioritizing direct M4A streams."""
    try:
        ydl_opts_search = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }

        print(f"Searching for: '{search_query}'...")

        with yt_dlp.YoutubeDL(ydl_opts_search) as ydl:
            search_results = ydl.extract_info(f"ytsearch5:{search_query}", download=False)

        if not search_results or 'entries' not in search_results or not search_results['entries']:
            print(f"❌ No videos found for: '{search_query}'")
            return

        videos = search_results['entries']

        print(f"\n--- YouTube Results for '{search_query}' ---")
        for i, video in enumerate(videos):
            title = video.get('title', 'Unknown Title')
            uploader = video.get('uploader', 'Unknown Channel')
            print(f"{i + 1}. {title} ({uploader})")

        while True:
            try:
                choice_input = input(f"Enter the number of the video to download (1-{len(videos)}): ")
                choice = int(choice_input)
                if 1 <= choice <= len(videos):
                    selected_video = videos[choice - 1]
                    break
                else:
                    print(f"Invalid number. Please enter a number between 1 and {len(videos)}.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        video_title = selected_video.get('title', 'Unknown Title')
        video_url = selected_video.get('url') or f"https://www.youtube.com/watch?v={selected_video['id']}"
        clean_title = clean_filename(video_title)

        print(f"\n⬇️ Downloading highest quality audio for: '{video_title}'")

        downloads_dir = "downloads"
        os.makedirs(downloads_dir, exist_ok=True)
        final_filepath = os.path.join(downloads_dir, f"{clean_title}.m4a")

        ydl_opts_download = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '0',
            }, {
                'key': 'EmbedThumbnail',
            }, {
                'key': 'FFmpegMetadata',
            }],
            'writethumbnail': True,
            'outtmpl': os.path.join(downloads_dir, f'{clean_title}.%(ext)s'),
            'quiet': False,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
            ydl.download([video_url])

        print(f"\n✅ Successfully downloaded audio: {final_filepath}")
        print("🎨 Thumbnail embedded as album art!")
        print("🖼️ Thumbnail image also saved as a separate file!")
        print("💡 Quality is preserved by avoiding re-encoding whenever possible.")

    except Exception as e:
        print(f"An error occurred while processing '{search_query}': {e}")

def main():
    """Main function to run the downloader."""
    print("YouTube High-Quality Audio Downloader")
    print("=========================================")
    print("🎵 Downloads in M4A (AAC) for high quality and wide compatibility!")
    print("🖼️ Embeds album art and saves a separate thumbnail image!")
    print("📁 Files saved to 'downloads' folder")
    print()

    try:
        import yt_dlp
    except ImportError as e:
        print(f"❌ Missing required dependency: {e}")
        print("   Please run: pip install yt-dlp")
        return

    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, text=True)
        print("✅ FFmpeg detected - ready for high-quality conversion!")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  WARNING: FFmpeg not found. It is required for audio conversion.")
        print("   Please install it from: https://ffmpeg.org/download.html")

    print()

    while True:
        try:
            search_input = input("Enter video title(s) (separate multiple with commas): ").strip()
            if not search_input:
                print("Please enter a valid search query.")
                continue

            search_queries = [query.strip() for query in search_input.split(',') if query.strip()]
            if not search_queries:
                print("Please enter valid search queries.")
                continue

            for query in search_queries:
                download_video(query)
                print("-" * 50)

            another = input("\nDownload more audio? (y/n): ").lower().strip()
            if another not in ['y', 'yes']:
                print("\nThanks for using the downloader! 🎵")
                break
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            break
        except Exception as e:
            # This block is now simplified as requested
            print(f"\nAn unexpected error occurred: {e}")
            print("Restarting prompt...")
            continue

if __name__ == "__main__":
    main()