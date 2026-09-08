# Česká televize (iVysílání) Downloader 📺

A cross-platform Python toolkit (CLI + GUI) for downloading high-quality, DRM-free shows and documentaries from the Česká televize (iVysílání) archive.

This project bypasses recent site API changes (which break standard extractors) by directly querying the official backend to retrieve raw MPEG-DASH streams. It processes the video, audio, subtitles, and artwork to create clean, Plex-ready media files.

## ✨ Features

* **Plex/Jellyfin Ready:** Automatically parses webpage titles to generate clean `Series - S1E0X - Episode Title.mp4` filenames.
* **Batch Downloading:** Paste a master series link to automatically scrape and download all available episodes sequentially.
* **Smart "Skip Existing":** Checks your local directory and instantly skips episodes you've already downloaded.
* **Automatic Subtitles:** Downloads official Czech closed captions, silently converts them from web `.vtt` to standard `.srt`, and soft-embeds them directly into the `.mp4` file (while keeping the external `.srt` file for media servers).
* **Artwork Fetching:** Scrapes and saves the official high-resolution episode poster as a `.jpg`.
* **Quality Selection:** Choose your maximum resolution limit (1080p, 720p, 540p, 360p) to save hard drive space.
* **Two Interfaces:** Includes a desktop GUI and command-line wrappers for Windows, Linux, and macOS.

## 🛠️ Prerequisites

To run this tool, you need the following installed and accessible in your `PATH`:
1. **Python 3.9 or newer**
2. **`yt-dlp`** (The core downloading engine)
3. **`ffmpeg`** (Required to merge DASH video/audio streams and embed subtitles)
4. **Tkinter** (required by the GUI; on Debian/Ubuntu install `python3-tk`)

The GUI uses the standard Python Tkinter library. On macOS and Windows it is
normally included with the official Python installer. Linux distributions may
provide it as a separate package.

Python runtime dependencies are listed in `requirements.txt`.

## 🚀 Installation & Setup

Follow the procedure for your operating system. Keep these files together in
one installation directory:

```text
ct_gui.pyw
ct_downloader.py
ct-dlp.bat    # Windows
ct-dlp        # Linux/macOS
```

### Windows

1. Install Python 3.9 or newer from [python.org](https://www.python.org/downloads/windows/).
   During setup, enable **Add Python to PATH**.
2. Install `yt-dlp`:
   ```powershell
   py -m pip install --upgrade -r requirements.txt
   ```
3. Install `ffmpeg` and add its `bin` directory to `PATH`.
4. Download or clone this repository, then open PowerShell in its directory.
5. Run the GUI by double-clicking `ct_gui.pyw`, or create a desktop shortcut.
6. To use the CLI, add the repository directory to `PATH`, then run:
   ```powershell
   .\ct-dlp.bat "https://www.ceskatelevize.cz/porady/..."
   ```

### Linux

1. Install Python, Tkinter, and FFmpeg using your distribution's package manager.
   On Debian or Ubuntu:
   ```sh
   sudo apt update
   sudo apt install python3 python3-tk python3-pip ffmpeg
   ```
2. Install `yt-dlp`:
   ```sh
   python3 -m pip install --user --upgrade -r requirements.txt
   ```
3. Download or clone this repository, then open a terminal in its directory.
4. Make the CLI launcher executable:
   ```sh
   chmod +x ct-dlp
   ```
5. Start the GUI:
   ```sh
   python3 ct_gui.pyw
   ```
6. Run the CLI:
   ```sh
   ./ct-dlp "https://www.ceskatelevize.cz/porady/..."
   ```

### macOS

1. Install Python 3.9 or newer from [python.org](https://www.python.org/downloads/macos/)
   or with Homebrew:
   ```sh
   brew install python
   ```
2. Install FFmpeg with Homebrew:
   ```sh
   brew install ffmpeg
   ```
3. Install `yt-dlp`:
   ```sh
   python3 -m pip install --user --upgrade -r requirements.txt
   ```
4. Download or clone this repository, then open Terminal in its directory.
5. Make the CLI launcher executable:
   ```sh
   chmod +x ct-dlp
   ```
6. Start the GUI:
   ```sh
   python3 ct_gui.pyw
   ```
7. Run the CLI:
   ```sh
   ./ct-dlp "https://www.ceskatelevize.cz/porady/..."
   ```

### Optional download directory

The default output directory is the current user's `Videos` folder. Set
`CT_DOWNLOAD_DIR` before starting the GUI to choose another location:

```powershell
# Windows PowerShell
$env:CT_DOWNLOAD_DIR = "D:\Media\Ceska televize"
py .\ct_gui.pyw
```

```sh
# Linux/macOS
export CT_DOWNLOAD_DIR="$HOME/Videos/Ceska televize"
python3 ct_gui.pyw
```

## 💻 Usage

### Option 1: The Desktop GUI
Start `ct_gui.pyw` using the command for your operating system. Paste an episode or series URL from iVysílání, select a maximum quality, and click **Download Video**. The GUI launches the downloader in a new terminal where supported.

### Option 2: The Command Line (CLI)
Open a terminal in your target download folder and use the wrapper for your operating system:

**Download a single episode:**
```text
# Windows
ct-dlp.bat "https://www.ceskatelevize.cz/porady/11248773911-habsburkove/215562260670001/"

# Linux/macOS
ct-dlp "https://www.ceskatelevize.cz/porady/11248773911-habsburkove/215562260670001/"

## ✅ Development checks

Install the development dependencies and run the same checks used by GitHub
Actions:

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m ruff check .
python3 -m compileall -q .
python3 -m pytest --cov=ct_downloader --cov=ct_gui --cov-report=term-missing --cov-fail-under=80 -q
```

The tests use mocked network and subprocess calls, so they do not contact
Česká televize or download media files. The GitHub Actions workflow runs these
checks on Windows, Linux, and macOS.