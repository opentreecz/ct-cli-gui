import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import os
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
DOWNLOADER_SCRIPT = SCRIPT_DIR / "ct_downloader.py"
DEFAULT_DOWNLOAD_DIR = Path.home() / "Videos"
DOWNLOAD_DIR = Path(
    os.environ.get("CT_DOWNLOAD_DIR", str(DEFAULT_DOWNLOAD_DIR))
).expanduser()


def get_console_python():
    executable = Path(sys.executable)
    if sys.platform == "win32" and executable.name.lower() == "pythonw.exe":
        return executable.with_name("python.exe")
    return executable


def launch_download(command):
    options = {"cwd": DOWNLOAD_DIR}
    if sys.platform == "win32":
        options["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    elif sys.platform == "darwin":
        shell_command = " ".join(shlex.quote(argument) for argument in command)
        shell_command = f"cd {shlex.quote(str(DOWNLOAD_DIR))} && {shell_command}"
        command = [
            "osascript",
            "-e",
            f'tell app "Terminal" to do script {json.dumps(shell_command)}',
        ]
    elif sys.platform.startswith("linux"):
        terminal = next(
            (
                candidate
                for candidate in (
                    "x-terminal-emulator",
                    "gnome-terminal",
                    "konsole",
                    "xfce4-terminal",
                )
                if shutil.which(candidate)
            ),
            None,
        )
        if terminal:
            command = [terminal, "--"] + command
    subprocess.Popen(command, **options)


def start_download():
    url = url_entry.get().strip()
    selected_quality = quality_var.get()
    
    if url:
        command = [str(get_console_python()), str(DOWNLOADER_SCRIPT), url]
        if selected_quality != "Highest Available":
            resolution = selected_quality.replace("p", "")
            command.extend(["--quality", resolution])
        
        try:
            DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
            launch_download(command)
        except OSError as error:
            messagebox.showerror("Unable to start download", str(error))
            return

        url_entry.delete(0, tk.END)

# Build the main window
root = tk.Tk()
root.title("ČT Downloader")
root.geometry("550x170")
root.resizable(False, False)

# Add the text and input box
tk.Label(root, text="Paste Česká televize URL:", font=("Segoe UI", 11)).pack(pady=(10, 5))
url_entry = tk.Entry(root, width=60, font=("Segoe UI", 10))
url_entry.pack(pady=5)

# Add the Quality Dropdown menu
quality_var = tk.StringVar(value="Highest Available")
quality_dropdown = ttk.Combobox(root, textvariable=quality_var, state="readonly", font=("Segoe UI", 9), width=18)
quality_dropdown['values'] = ("Highest Available", "1080p", "720p", "540p", "360p")
quality_dropdown.pack(pady=(0, 10))

# Add the download button
tk.Button(root, text="Download Video", command=start_download, font=("Segoe UI", 10, "bold"), bg="#E2001A", fg="white", width=20).pack(pady=5)

root.mainloop()