import importlib.machinery
import importlib.util
from pathlib import Path

GUI_PATH = Path(__file__).parents[1] / "ct_gui.pyw"
loader = importlib.machinery.SourceFileLoader("ct_gui", str(GUI_PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
ct_gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ct_gui)


def test_build_download_command_without_quality():
    command = ct_gui.build_download_command("https://example.test/episode/123", "Highest Available")

    assert command[1] == str(GUI_PATH.parents[0] / "ct_downloader.py")
    assert command[-1] == "https://example.test/episode/123"
    assert "--quality" not in command


def test_build_download_command_with_quality():
    command = ct_gui.build_download_command("https://example.test/episode/123", "720p")

    assert command[-2:] == ["--quality", "720"]


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
