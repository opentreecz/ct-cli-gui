import importlib.util
from pathlib import Path

GUI_PATH = Path(__file__).parents[1] / "ct_gui.pyw"
spec = importlib.util.spec_from_file_location("ct_gui", GUI_PATH)
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
