import json
import os
import shlex
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

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


def get_downloader_command():
    configured_path = os.environ.get("CT_DOWNLOADER_PATH")
    if configured_path:
        configured = Path(configured_path).expanduser()
        if not configured.is_file():
            raise FileNotFoundError(f"Configured downloader was not found: {configured}")
        return [str(get_console_python()), str(configured)]

    installed_command = shutil.which("ct-dlp")
    if installed_command:
        return [installed_command]

    installed_script = shutil.which("ct_downloader.py")
    if installed_script:
        return [str(get_console_python()), installed_script]

    if DOWNLOADER_SCRIPT.is_file():
        return [str(get_console_python()), str(DOWNLOADER_SCRIPT)]

    raise FileNotFoundError(
        "ct_downloader.py was not found. Set CT_DOWNLOADER_PATH or install ct-cli-gui."
    )


def launch_download(command):
    options = {"cwd": DOWNLOAD_DIR}
    if sys.platform == "win32":
        options["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
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


def build_download_command(url, selected_quality, download_mode="video", subtitle_format="srt"):
    command = get_downloader_command() + [url]
    if download_mode != "video":
        command.extend(["--mode", download_mode])
    if download_mode == "subtitles" and subtitle_format != "srt":
        command.extend(["--subtitle-format", subtitle_format])
    if selected_quality != "Highest Available":
        command.extend(["--quality", selected_quality.replace("p", "")])
    return command


def start_download():
    url = url_entry.get().strip()
    selected_quality = quality_var.get()
    selected_mode = mode_var.get() if "mode_var" in globals() else "video"
    selected_subtitle_format = (
        subtitle_format_var.get() if "subtitle_format_var" in globals() else "srt"
    )

    if url:
        try:
            command = build_download_command(
                url, selected_quality, selected_mode, selected_subtitle_format
            )
            DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
            launch_download(command)
        except OSError as error:
            messagebox.showerror("Unable to start download", str(error))
            return

        url_entry.delete(0, tk.END)


def main():
    global quality_var, url_entry, mode_var, subtitle_format_var

    root = tk.Tk()
    root.title("ČT Downloader")
    root.geometry("550x220")
    root.resizable(False, False)

    tk.Label(
        root, text="Paste Česká televize URL:", font=("Segoe UI", 11)
    ).pack(pady=(10, 5))
    url_entry = tk.Entry(root, width=60, font=("Segoe UI", 10))
    url_entry.pack(pady=5)

    quality_var = tk.StringVar(value="Highest Available")
    quality_dropdown = ttk.Combobox(
        root,
        textvariable=quality_var,
        state="readonly",
        font=("Segoe UI", 9),
        width=18,
    )
    quality_dropdown["values"] = ("Highest Available", "1080p", "720p", "540p", "360p")
    quality_dropdown.pack(pady=(0, 10))

    mode_var = tk.StringVar(value="video")
    mode_dropdown = ttk.Combobox(
        root,
        textvariable=mode_var,
        state="readonly",
        font=("Segoe UI", 9),
        width=18,
    )
    mode_dropdown["values"] = ("video", "subtitles", "transcript")
    mode_dropdown.pack(pady=(0, 10))

    subtitle_format_var = tk.StringVar(value="srt")
    subtitle_format_dropdown = ttk.Combobox(
        root,
        textvariable=subtitle_format_var,
        state="readonly",
        font=("Segoe UI", 9),
        width=18,
    )
    subtitle_format_dropdown["values"] = ("srt", "txt")
    subtitle_format_dropdown.pack(pady=(0, 10))

    tk.Button(
        root,
        text="Download",
        command=start_download,
        font=("Segoe UI", 10, "bold"),
        bg="#E2001A",
        fg="white",
        width=20,
    ).pack(pady=5)
    root.mainloop()


if __name__ == "__main__":
    main()