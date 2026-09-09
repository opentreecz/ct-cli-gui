import importlib.machinery
import importlib.util
from pathlib import Path

GUI_PATH = Path(__file__).parents[1] / "ct_gui.pyw"
loader = importlib.machinery.SourceFileLoader("ct_gui", str(GUI_PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
ct_gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ct_gui)


def test_build_download_command_without_quality(monkeypatch):
    monkeypatch.setattr(
        ct_gui,
        "get_downloader_command",
        lambda: [str(ct_gui.get_console_python()), str(GUI_PATH.parents[0] / "ct_downloader.py")],
    )
    command = ct_gui.build_download_command("https://example.test/episode/123", "Highest Available")

    assert command[1] == str(GUI_PATH.parents[0] / "ct_downloader.py")
    assert command[-1] == "https://example.test/episode/123"
    assert "--quality" not in command


def test_get_downloader_command_uses_configured_path(monkeypatch, tmp_path):
    downloader = tmp_path / "ct_downloader.py"
    downloader.write_text("")
    monkeypatch.setenv("CT_DOWNLOADER_PATH", str(downloader))
    monkeypatch.setattr(ct_gui, "get_console_python", lambda: Path("python"))

    assert ct_gui.get_downloader_command() == ["python", str(downloader)]


def test_get_downloader_command_uses_installed_cli(monkeypatch):
    monkeypatch.delenv("CT_DOWNLOADER_PATH", raising=False)
    monkeypatch.setattr(ct_gui.shutil, "which", lambda name: "/bin/ct-dlp")

    assert ct_gui.get_downloader_command() == ["/bin/ct-dlp"]


def test_get_downloader_command_reports_missing_configured_path(monkeypatch, tmp_path):
    monkeypatch.setenv("CT_DOWNLOADER_PATH", str(tmp_path / "missing.py"))

    try:
        ct_gui.get_downloader_command()
    except FileNotFoundError as error:
        assert "Configured downloader was not found" in str(error)
    else:
        raise AssertionError("Expected missing configured downloader to fail")


def test_build_download_command_with_quality():
    command = ct_gui.build_download_command("https://example.test/episode/123", "720p")

    assert command[-2:] == ["--quality", "720"]


def test_build_download_command_with_download_mode():
    command = ct_gui.build_download_command(
        "https://example.test/episode/123",
        "Highest Available",
        "subtitles",
    )

    assert command[-2:] == ["--mode", "subtitles"]


def test_launch_download_uses_direct_process_when_no_linux_terminal(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(ct_gui.sys, "platform", "linux")
    monkeypatch.setattr(ct_gui.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        ct_gui.subprocess,
        "Popen",
        lambda command, **options: calls.append((command, options)),
    )
    monkeypatch.setattr(ct_gui, "DOWNLOAD_DIR", tmp_path)

    ct_gui.launch_download(["python", "ct_downloader.py", "https://example.test"])

    assert calls == [
        (
            ["python", "ct_downloader.py", "https://example.test"],
            {"cwd": tmp_path},
        )
    ]


def test_launch_download_uses_linux_terminal(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(ct_gui.sys, "platform", "linux")
    monkeypatch.setattr(
        ct_gui.shutil,
        "which",
        lambda name: "/usr/bin/gnome-terminal" if name == "gnome-terminal" else None,
    )
    monkeypatch.setattr(
        ct_gui.subprocess,
        "Popen",
        lambda command, **options: calls.append((command, options)),
    )
    monkeypatch.setattr(ct_gui, "DOWNLOAD_DIR", tmp_path)

    ct_gui.launch_download(["python", "ct_downloader.py"])

    assert calls[0][0] == ["gnome-terminal", "--", "python", "ct_downloader.py"]


def test_launch_download_uses_macos_terminal(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(ct_gui.sys, "platform", "darwin")
    monkeypatch.setattr(
        ct_gui.subprocess,
        "Popen",
        lambda command, **options: calls.append((command, options)),
    )
    monkeypatch.setattr(ct_gui, "DOWNLOAD_DIR", tmp_path)

    ct_gui.launch_download(["python", "ct_downloader.py", "URL with spaces"])

    assert calls[0][0][0] == "osascript"
    assert "Terminal" in calls[0][0][2]


def test_get_console_python_uses_python_on_windows(monkeypatch):
    monkeypatch.setattr(ct_gui.sys, "platform", "win32")
    monkeypatch.setattr(ct_gui.sys, "executable", "/Python/pythonw.exe")

    assert ct_gui.get_console_python().name == "python.exe"


def test_launch_download_uses_windows_console(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(ct_gui.sys, "platform", "win32")
    monkeypatch.setattr(
        ct_gui.subprocess,
        "Popen",
        lambda command, **options: calls.append((command, options)),
    )
    monkeypatch.setattr(ct_gui, "DOWNLOAD_DIR", tmp_path)

    ct_gui.launch_download(["python", "ct_downloader.py"])

    assert calls[0][1] == {
        "cwd": tmp_path,
        "creationflags": getattr(ct_gui.subprocess, "CREATE_NEW_CONSOLE", 0),
    }


def test_start_download_ignores_empty_url(monkeypatch):
    class Field:
        def get(self):
            return "  "

    class Quality:
        def get(self):
            return "720p"

    monkeypatch.setattr(ct_gui, "url_entry", Field(), raising=False)
    monkeypatch.setattr(ct_gui, "quality_var", Quality(), raising=False)
    monkeypatch.setattr(
        ct_gui,
        "launch_download",
        lambda command: (_ for _ in ()).throw(AssertionError("not called")),
    )

    ct_gui.start_download()


def test_start_download_launches_and_clears_url(monkeypatch, tmp_path):
    class Field:
        def __init__(self):
            self.cleared = False

        def get(self):
            return "https://example.test/video"

        def delete(self, start, end):
            self.cleared = (start, end)

    class Quality:
        def get(self):
            return "720p"

    field = Field()
    launched = []
    monkeypatch.setattr(ct_gui, "url_entry", field, raising=False)
    monkeypatch.setattr(ct_gui, "quality_var", Quality(), raising=False)
    monkeypatch.setattr(ct_gui, "DOWNLOAD_DIR", tmp_path / "downloads")
    monkeypatch.setattr(ct_gui, "launch_download", launched.append)

    ct_gui.start_download()

    assert launched[0][-2:] == ["--quality", "720"]
    assert field.cleared == (0, ct_gui.tk.END)
    assert (tmp_path / "downloads").is_dir()


def test_start_download_reports_launch_error(monkeypatch, tmp_path):
    class Field:
        def get(self):
            return "https://example.test/video"

    class Quality:
        def get(self):
            return "Highest Available"

    errors = []
    monkeypatch.setattr(ct_gui, "url_entry", Field(), raising=False)
    monkeypatch.setattr(ct_gui, "quality_var", Quality(), raising=False)
    monkeypatch.setattr(ct_gui, "DOWNLOAD_DIR", tmp_path)
    monkeypatch.setattr(
        ct_gui,
        "launch_download",
        lambda command: (_ for _ in ()).throw(OSError("cannot launch")),
    )
    monkeypatch.setattr(
        ct_gui.messagebox,
        "showerror",
        lambda title, message: errors.append((title, message)),
    )

    ct_gui.start_download()

    assert errors == [("Unable to start download", "cannot launch")]


def test_start_download_includes_selected_mode(monkeypatch, tmp_path):
    class Field:
        def get(self):
            return "https://example.test/video"

        def delete(self, start, end):
            pass

    class Value:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

    launched = []
    monkeypatch.setattr(ct_gui, "url_entry", Field(), raising=False)
    monkeypatch.setattr(ct_gui, "quality_var", Value("Highest Available"), raising=False)
    monkeypatch.setattr(ct_gui, "mode_var", Value("transcript"), raising=False)
    monkeypatch.setattr(ct_gui, "DOWNLOAD_DIR", tmp_path)
    monkeypatch.setattr(ct_gui, "launch_download", launched.append)

    ct_gui.start_download()

    assert launched[0][-2:] == ["--mode", "transcript"]
