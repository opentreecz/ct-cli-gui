# Česká televize (iVysílání) Downloader 📺

A custom, native Windows toolkit (CLI + GUI) for downloading high-quality, DRM-free shows and documentaries from the Česká televize (iVysílání) archive. 

This project bypasses recent site API changes (which break standard extractors) by directly querying the official backend to retrieve raw MPEG-DASH streams. It processes the video, audio, subtitles, and artwork to create clean, Plex-ready media files.

## ✨ Features

* **Plex/Jellyfin Ready:** Automatically parses webpage titles to generate clean `Series - S1E0X - Episode Title.mp4` filenames.
* **Batch Downloading:** Paste a master series link to automatically scrape and download all available episodes sequentially.
* **Smart "Skip Existing":** Checks your local directory and instantly skips episodes you've already downloaded.
* **Automatic Subtitles:** Downloads official Czech closed captions, silently converts them from web `.vtt` to standard `.srt`, and soft-embeds them directly into the `.mp4` file (while keeping the external `.srt` file for media servers).
* **Artwork Fetching:** Scrapes and saves the official high-resolution episode poster as a `.jpg`.
* **Quality Selection:** Choose your maximum resolution limit (1080p, 720p, 540p, 360p) to save hard drive space.
* **Two Interfaces:** Includes a seamless desktop GUI and a native command-line wrapper.

## 🛠️ Prerequisites

To run this tool, you need the following installed and accessible on your Windows machine:
1. **Python 3.x**
2. **`yt-dlp`** (The core downloading engine)
3. **`ffmpeg`** (Required to merge DASH video/audio streams and embed subtitles)

## 🚀 Installation & Setup

1. **Clone or Download this repository:**
   Extract the files to your preferred script directory.

2. **Set up the Command Line Wrapper (`ct-dlp`):**
   * Ensure the folder containing the scripts is added to your Windows `PATH` environment variable.
   * If you haven't already, run the following in PowerShell inside that folder to generate the executable wrapper:
     ```powershell
     $lines = "@echo off", 'python "%~dp0ct_downloader.py" %*'
     [System.IO.File]::WriteAllLines("$PWD\ct-dlp.bat", $lines)
     ```

3. **Set up the GUI Desktop App:**
   * Right-click `ct_gui.pyw` and select **Create shortcut**.
   * Move the shortcut to your Desktop.
   * *(Optional)* Right-click the shortcut, go to Properties -> Change Icon, and give it a custom app icon.
   * **Note:** Edit line 10 in `ct_gui.pyw` (`download_dir = r"C:\Users\...\Videos"`) to match your preferred download destination so the terminal opens in the correct folder.

## 💻 Usage

### Option 1: The Desktop GUI
Simply double-click your Desktop shortcut. Paste an episode or series URL from iVysílání, select your maximum desired quality from the dropdown menu, and click **Download Video**. A terminal will pop up showing the background progress.

### Option 2: The Command Line (CLI)
Open PowerShell in your target download folder and use your new custom command:

**Download a single episode:**
```powershell
ct-dlp "[https://www.ceskatelevize.cz/porady/11248773911-habsburkove/215562260670001/](https://www.ceskatelevize.cz/porady/11248773911-habsburkove/215562260670001/)"