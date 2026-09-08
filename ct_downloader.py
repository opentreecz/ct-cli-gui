import argparse
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
    name = raw_title.split('|')[0].strip()
    parts = name.split(' - ')
    if len(parts) >= 2:
        series_name = parts[-1].strip()
        ep_info = " - ".join(parts[:-1]).strip() 
        match = re.match(r'^(\d+)/\d+\s+(.*)', ep_info)
        if match:
            ep_num = match.group(1)
            ep_title = match.group(2).strip()
            formatted_name = f"{series_name} - S1E{int(ep_num):02d} - {ep_title}"
            return re.sub(r'[\\/*?:"<>|]', "-", formatted_name)
    return re.sub(r'[\\/*?:"<>|]', "-", name)

def get_html(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT
    })
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            return response.read().decode('utf-8')
    except (OSError, UnicodeDecodeError) as error:
        print(f"[-] Error fetching page: {error}")
        return ""

def download_episode(episode_url, quality=None):
    print(f"\nAnalyzing: {episode_url}")
    
    id_match = re.search(r'/(\d{10,})/?$', episode_url)
    if not id_match:
        print("[-] Could not extract video ID.")
        return
    video_id = id_match.group(1)
    
    html = get_html(episode_url)
    title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    
    clean_title = (
        format_episode_name(title_match.group(1))
        if title_match
        else f"CeskaTelevize_{video_id}"
    )
    output_filename = f"{clean_title}.mp4"
    
    if os.path.exists(output_filename):
        print(f"[!] '{output_filename}' already exists. Skipping...")
        return
        
    print(f"[+] Found Episode: {clean_title}")
    if quality:
        print(f"[+] Target Quality: {quality}p (or closest match)")
    
    # --- POSTER DOWNLOAD ---
    poster_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
    if poster_match:
        poster_url = poster_match.group(1).replace('&amp;', '&')
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
            data = response.read().decode('utf-8')
            
            # --- SUBTITLES ---
            vtt_filename = f"{clean_title}.cs.vtt"
            srt_filename = f"{clean_title}.cs.srt"
            has_subs = False
            
            sub_match = re.search(r'"(https://[^"]+\.vtt[^"]*)"', data)
            if sub_match:
                sub_url = sub_match.group(1).replace('\\/', '/')
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
                        has_subs = True
                        print(f"[+] Generated standard subtitle file: {srt_filename}")
                except (OSError, subprocess.SubprocessError):
                    print("[-] Could not download or convert subtitles.")

            stream_match = re.search(r'"(https://[^"]+(?:token=[^"]+|m3u8|mpd[^"]*))"', data)
            if not stream_match:
                print("[-] Error: Stream URL not found. It may be DRM protected.")
                if has_subs:
                    os.remove(srt_filename)
                return
                
            stream_url = stream_match.group(1).replace('\\/', '/')
            
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
                    "ffmpeg", "-i", temp_video, "-i", srt_filename,
                    "-c", "copy", "-c:s", "mov_text",
                    "-metadata:s:s:0", "language=cze",
                    "-metadata:s:s:0", "title=Czech",
                    output_filename, "-y"
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
    args = parser.parse_args()

    if args.url:
        url = args.url.strip()
        quality = args.quality.lower().replace('p', '') if args.quality else None
    else:
        print("=== Česká televize Downloader ===")
        url = input("Paste the iVysílání URL (Episode or Series): ").strip()
        quality = input("Max resolution (e.g. 1080, 720, 540) [Press Enter for Highest]: ").strip()
        quality = quality.lower().replace('p', '') if quality else None
        
    episode_match = re.search(r'/porady/\d+-[^/]+/(\d{10,})/?$', url)
    series_match = re.search(r'(/porady/\d+-[^/]+)/?$', url)
    
    if episode_match:
        download_episode(url, quality)
        
    elif series_match:
        print("[+] Series URL detected. Searching for episodes...")
        series_path = series_match.group(1)
        html = get_html(url)
        
        matches = re.findall(rf'{series_path}/(\d{{10,}})/?', html)
        if not matches:
            print("[-] No episodes found on this page.")
            return
            
        unique_ids = list(dict.fromkeys(matches))
        print(f"[+] Found {len(unique_ids)} episodes. Starting batch download...\n")
        
        for vid_id in unique_ids:
            ep_url = f"{SITE_URL}{series_path}/{vid_id}/"
            download_episode(ep_url, quality)
            print("-" * 60)
            
        print("\n[+] Batch download complete!")
    else:
        print("[-] Invalid Česká televize URL format.")

if __name__ == "__main__":
    main()
    # Pause terminal if run directly without arguments
    if len(sys.argv) == 1:
        input("\nPress Enter to exit...")