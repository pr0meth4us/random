import yt_dlp
import os
import re

def clean_filename(filename):
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'\s+', ' ', filename).strip()
    return filename

def download_video(search_query):
    try:
        ydl_opts_search = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }

        print(f"Searching for: {search_query}")

        with yt_dlp.YoutubeDL(ydl_opts_search) as ydl:
            search_results = ydl.extract_info(f"ytsearch5:{search_query}", download=False)

        if not search_results or 'entries' not in search_results:
            print(f"No videos found for: {search_query}")
            return

        videos = search_results['entries']

        print(f"\n--- YouTube Search Results for '{search_query}' ---")
        for i, video in enumerate(videos):
            title = video.get('title', 'Unknown Title')
            uploader = video.get('uploader', 'Unknown Channel')
            print(f"{i + 1}. {title} ({uploader})")

        while True:
            try:
                choice = input(f"Enter the number of the video to download (1-{len(videos)}): ")
                choice = int(choice)
                if 1 <= choice <= len(videos):
                    selected_video = videos[choice - 1]
                    break
                else:
                    print(f"Invalid number. Please enter a number between 1 and {len(videos)}.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        video_title = selected_video.get('title', 'Unknown Title')
        video_url = selected_video.get('url') or f"https://www.youtube.com/watch?v={selected_video['id']}"

        print(f"\nDownloading highest quality audio for: {video_title}")

        downloads_dir = "downloads"
        os.makedirs(downloads_dir, exist_ok=True)

        clean_title = clean_filename(video_title)

        ydl_opts_download = {
            'format': 'bestaudio[ext=opus]/bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'flac',
                'preferredquality': '0',
            }, {
                'key': 'EmbedThumbnail',
                'already_have_thumbnail': False,
            }, {
                'key': 'FFmpegMetadata',
            }],
            'outtmpl': os.path.join(downloads_dir, f'{clean_title}.%(ext)s'),
            'quiet': False,
            'no_warnings': True,
            'writeinfojson': False,
            'writethumbnail': True,
            'embedsubs': False,
            'writesubtitles': False,
            'ignoreerrors': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
            ydl.download([video_url])

        local_file_path = os.path.join(downloads_dir, f"{clean_title}.flac")
        print(f"✅ Successfully downloaded in FLAC format: {local_file_path}")
        print("🎨 Thumbnail embedded as album art!")
        print("💡 FLAC provides lossless audio quality - the best YouTube has to offer!")

    except Exception as e:
        print(f"An error occurred while downloading '{search_query}': {e}")

def main():
    print("YouTube MAXIMUM QUALITY Audio Downloader")
    print("========================================")
    print("🎵 Downloads in FLAC format for lossless quality!")
    print("🎨 Embeds thumbnails as album art!")
    print("📁 Files saved to 'downloads' folder")
    print()

    try:
        import yt_dlp
    except ImportError as e:
        print(f"Missing required dependency: {e}")
        print("Please run: pip install yt-dlp")
        return

    try:
        import subprocess
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ FFmpeg detected - ready for high quality conversion!")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  WARNING: FFmpeg not found. You may need to install it for audio conversion.")
        print("   Visit: https://ffmpeg.org/download.html")

    print()

    while True:
        try:
            search_input = input("Enter video titles (separate multiple with commas): ").strip()

            if not search_input:
                print("Please enter valid search queries.")
                continue

            search_queries = [query.strip() for query in search_input.split(',') if query.strip()]

            if not search_queries:
                print("Please enter valid search queries.")
                continue

            for query in search_queries:
                download_video(query)
                print("-" * 50)

            another = input("\nDownload more songs? (y/n): ").lower().strip()
            if another not in ['y', 'yes']:
                print("Thanks for using the High Quality YouTube Downloader! 🎵")
                break

        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            continue_choice = input("Continue with another download? (y/n): ").lower().strip()
            if continue_choice not in ['y', 'yes']:
                break

if __name__ == "__main__":
    main()