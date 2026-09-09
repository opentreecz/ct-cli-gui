import argparse
import contextlib
import html
import json
import os
import re
import subprocess
import sys
import urllib.request
import uuid

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 30
SITE_URL = "https://www.ceskatelevize.cz"
STREAM_API_URL = (
    "https://api.ceskatelevize.cz/video/v1/playlist-vod/v1/stream-data/"
    "media/external/{video_id}?canPlayDrm=true&quality=web&streamType=dash"
    "&deviceId={device_id}&origin=ivysilani&client=iVysilaniWeb"
    "&clientVersion=0.37.8"
)


def format_episode_name(raw_title):
    name = raw_title.split("|")[0].strip()
    parts = name.split(" - ")
    if len(parts) >= 2:
        series_name = parts[-1].strip()
        ep_info = " - ".join(parts[:-1]).strip()
        match = re.match(r"^(\d+)/\d+\s+(.*)", ep_info)
        if match:
            ep_num = match.group(1)
            ep_title = match.group(2).strip()
            formatted_name = f"{series_name} - S1E{int(ep_num):02d} - {ep_title}"
            return re.sub(r'[\\/*?:"<>|]', "-", formatted_name)
    return re.sub(r'[\\/*?:"<>|]', "-", name)


def get_html(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            return response.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"[-] Error fetching page: {error}")
        return ""


def _extract_transcript(page_html):
    """Return a transcript from common iVysílání HTML/JSON representations."""
    for pattern in (
        r'"(?:transcript|transcriptText)"\s*:\s*"((?:\\.|[^"\\])*)"',
        r'<meta[^>]+(?:name|property)="transcript"[^>]+content="([^"]+)"',
    ):
        match = re.search(pattern, page_html, re.IGNORECASE)
        if match:
            value = match.group(1)
            if pattern.startswith('"'):
                with contextlib.suppress(json.JSONDecodeError):
                    value = json.loads(f'"{value}"')
            return html.unescape(value).strip()

    match = re.search(
        r'<(?:section|div)[^>]+(?:id|class)="[^"]*transcript[^"]*"[^>]*>(.*?)</(?:section|div)>',
        page_html,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", match.group(1)))).strip()
    return None


def _srt_to_text(srt_content):
    """Strip SRT index numbers, timestamps and inline tags, returning plain text."""
    lines = []
    for line in srt_content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.isdigit() or "-->" in stripped:
            continue
        lines.append(re.sub(r"<[^>]+>", "", stripped))
    return "\n".join(lines)


def _download_subtitles(data, clean_title, subtitle_format="srt"):
    sub_match = re.search(r'"(https://[^"]+\.vtt[^"]*)"', data)
    if not sub_match:
        return None

    sub_url = sub_match.group(1).replace("\\/", "/")
    vtt_filename = f"{clean_title}.cs.vtt"
    srt_filename = f"{clean_title}.cs.srt"
    try:
        urllib.request.urlretrieve(sub_url, vtt_filename)
        subprocess.run(
            ["ffmpeg", "-i", vtt_filename, srt_filename, "-y"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if os.path.exists(srt_filename):
            os.remove(vtt_filename)
            print(f"[+] Generated standard subtitle file: {srt_filename}")
            if subtitle_format == "txt":
                txt_filename = f"{clean_title}.cs.txt"
                with open(srt_filename, encoding="utf-8") as subtitle_file:
                    subtitle_text = _srt_to_text(subtitle_file.read())
                with open(txt_filename, "w", encoding="utf-8") as subtitle_file:
                    subtitle_file.write(subtitle_text + "\n")
                print(f"[+] Also saved as plain-text subtitle file: {txt_filename}")
            return srt_filename
    except (OSError, subprocess.SubprocessError):
        print("[-] Could not download or convert subtitles.")
    return None


def download_episode(episode_url, quality=None, download_mode="video", subtitle_format="srt"):
    print(f"\nAnalyzing: {episode_url}")

    id_match = re.search(r"/(\d{10,})/?$", episode_url)
    if not id_match:
        print("[-] Could not extract video ID.")
        return
    video_id = id_match.group(1)

    html = get_html(episode_url)
    title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)

    clean_title = (
        format_episode_name(title_match.group(1)) if title_match else f"CeskaTelevize_{video_id}"
    )
    if download_mode == "transcript":
        transcript = _extract_transcript(html)
        if not transcript:
            print("[-] Transcript not found for this episode.")
            return
        transcript_filename = f"{clean_title}.txt"
        with open(transcript_filename, "w", encoding="utf-8") as transcript_file:
            transcript_file.write(transcript + "\n")
        print(f"[+] Saved transcript: {transcript_filename}")
        return

    output_filename = f"{clean_title}.mp4"

    if download_mode == "video" and os.path.exists(output_filename):
        print(f"[!] '{output_filename}' already exists. Skipping...")
        return

    print(f"[+] Found Episode: {clean_title}")
    if quality:
        print(f"[+] Target Quality: {quality}p (or closest match)")

    if download_mode == "video":
        # --- POSTER DOWNLOAD ---
        poster_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        if poster_match:
            poster_url = poster_match.group(1).replace("&amp;", "&")
            poster_filename = f"{clean_title}.jpg"
            if not os.path.exists(poster_filename):
                try:
                    urllib.request.urlretrieve(poster_url, poster_filename)
                    print("[+] Saved episode poster artwork.")
                except OSError:
                    print("[-] Could not download episode poster.")

    device_id = str(uuid.uuid4())
    api_url = STREAM_API_URL.format(video_id=video_id, device_id=device_id)

    req = urllib.request.Request(
        api_url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = response.read().decode("utf-8")

            srt_filename = _download_subtitles(
                data,
                clean_title,
                subtitle_format if download_mode == "subtitles" else "srt",
            )
            has_subs = srt_filename is not None
            if download_mode == "subtitles":
                if not has_subs:
                    print("[-] Subtitles not found for this episode.")
                return

            stream_match = re.search(r'"(https://[^"]+(?:token=[^"]+|m3u8|mpd[^"]*))"', data)
            if not stream_match:
                print("[-] Error: Stream URL not found. It may be DRM protected.")
                if has_subs:
                    os.remove(srt_filename)
                return

            stream_url = stream_match.group(1).replace("\\/", "/")

            # --- YT-DLP DOWNLOAD ---
            print("[+] Starting video download...")
            command = ["yt-dlp", "-o", output_filename]

            # Add resolution limit if specified
            if quality:
                command.extend(["-S", f"res:{quality}"])

            command.append(stream_url)
            result = subprocess.run(command, check=False)
            if result.returncode != 0:
                print("[-] Video download failed.")
                if has_subs and os.path.exists(srt_filename):
                    os.remove(srt_filename)
                return

            # --- SUBTITLE EMBEDDING ---
            if has_subs and os.path.exists(output_filename):
                print("[+] Embedding subtitles directly into the MP4 file...")
                temp_video = f"{clean_title}.temp.mp4"
                os.rename(output_filename, temp_video)

                ffmpeg_cmd = [
                    "ffmpeg",
                    "-i",
                    temp_video,
                    "-i",
                    srt_filename,
                    "-c",
                    "copy",
                    "-c:s",
                    "mov_text",
                    "-metadata:s:s:0",
                    "language=cze",
                    "-metadata:s:s:0",
                    "title=Czech",
                    output_filename,
                    "-y",
                ]

                result = subprocess.run(
                    ffmpeg_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if result.returncode == 0 and os.path.exists(output_filename):
                    os.remove(temp_video)
                    print("[+] Subtitles successfully embedded! (External .srt file kept)")
                else:
                    os.rename(temp_video, output_filename)
                    print("[-] Failed to embed subtitles. Kept original video.")

    except (OSError, UnicodeDecodeError) as error:
        print(f"[-] Connection error getting stream: {error}")


def main():
    parser = argparse.ArgumentParser(description="Česká televize Downloader")
    parser.add_argument("url", nargs="?", help="The iVysílání Episode or Series URL")
    parser.add_argument(
        "-q",
        "--quality",
        type=str,
        help="Max resolution limit (e.g. 1080, 720, 540)",
    )
    parser.add_argument(
        "--mode",
        choices=("video", "subtitles", "transcript"),
        default="video",
        help="Download video (default), subtitles only, or transcript only",
    )
    parser.add_argument(
        "--subtitles-only",
        action="store_const",
        const="subtitles",
        dest="mode",
        help="Download subtitles only",
    )
    parser.add_argument(
        "--transcript-only",
        action="store_const",
        const="transcript",
        dest="mode",
        help="Download transcript only",
    )
    parser.add_argument(
        "--subtitle-format",
        choices=("srt", "txt"),
        default="srt",
        help=(
            "Format for subtitle-only downloads: srt (default)."
            " When txt is selected, both .srt and .txt files are saved."
        ),
    )
    args = parser.parse_args()

    if args.url:
        url = args.url.strip()
        quality = args.quality.lower().replace("p", "") if args.quality else None
    else:
        print("=== Česká televize Downloader ===")
        url = input("Paste the iVysílání URL (Episode or Series): ").strip()
        quality = input("Max resolution (e.g. 1080, 720, 540) [Press Enter for Highest]: ").strip()
        quality = quality.lower().replace("p", "") if quality else None

    episode_match = re.search(r"/porady/\d+-[^/]+/(\d{10,})/?$", url)
    series_match = re.search(r"(/porady/\d+-[^/]+)/?$", url)

    if episode_match:
        if args.mode == "video":
            download_episode(url, quality)
        else:
            download_episode(url, quality, args.mode, args.subtitle_format)

    elif series_match:
        print("[+] Series URL detected. Searching for episodes...")
        series_path = series_match.group(1)
        html = get_html(url)

        matches = re.findall(rf"{series_path}/(\d{{10,}})/?", html)
        if not matches:
            print("[-] No episodes found on this page.")
            return

        unique_ids = list(dict.fromkeys(matches))
        print(f"[+] Found {len(unique_ids)} episodes. Starting batch download...\n")

        for vid_id in unique_ids:
            ep_url = f"{SITE_URL}{series_path}/{vid_id}/"
            if args.mode == "video":
                download_episode(ep_url, quality)
            else:
                download_episode(ep_url, quality, args.mode, args.subtitle_format)
            print("-" * 60)

        print("\n[+] Batch download complete!")
    else:
        print("[-] Invalid Česká televize URL format.")


if __name__ == "__main__":
    main()
    # Pause terminal if run directly without arguments
    if len(sys.argv) == 1:
        input("\nPress Enter to exit...")
