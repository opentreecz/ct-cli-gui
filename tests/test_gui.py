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


def test_build_download_command_with_text_subtitle_format():
    command = ct_gui.build_download_command(
        "https://example.test/episode/123",
        "Highest Available",
        "subtitles",
        "txt",
    )

    assert command[-2:] == ["--subtitle-format", "txt"]


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
    monkeypatch.setattr(ct_gui, "mode_var", Value("subtitles"), raising=False)
    monkeypatch.setattr(ct_gui, "DOWNLOAD_DIR", tmp_path)
    monkeypatch.setattr(ct_gui, "launch_download", launched.append)

    ct_gui.start_download()

    assert launched[0][-2:] == ["--mode", "subtitles"]


def test_start_download_includes_selected_subtitle_format(monkeypatch, tmp_path):
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
    monkeypatch.setattr(ct_gui, "mode_var", Value("subtitles"), raising=False)
    monkeypatch.setattr(ct_gui, "subtitle_format_var", Value("txt"), raising=False)
    monkeypatch.setattr(ct_gui, "DOWNLOAD_DIR", tmp_path)
    monkeypatch.setattr(ct_gui, "launch_download", launched.append)

    ct_gui.start_download()

    assert launched[0][-2:] == ["--subtitle-format", "txt"]


# ---------------------------------------------------------------------------
# GUI ↔ CLI contract tests
# These tests feed the command built by the GUI into the downloader's REAL
# argparser (ct_downloader.build_arg_parser), proving both sides agree on
# the CLI interface.  A failure here means one side was changed without
# updating the other — exactly the class of regression introduced in
# commit 68af0e4 / fixed in 0da6f63.
# ---------------------------------------------------------------------------

import ct_downloader  # noqa: E402


def _gui_args(url, quality, mode, subtitle_format):
    """Build the command the GUI would launch and strip the interpreter/script prefix."""
    command = ct_gui.build_download_command(url, quality, mode, subtitle_format)
    # The first two entries are [python, ct_downloader.py]; drop them so we can
    # feed the remaining tokens directly to argparse.
    return command[2:]


def test_gui_srt_command_is_accepted_by_downloader_cli():
    """GUI command for srt subtitles must parse without error."""
    args = _gui_args(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        "Highest Available",
        "subtitles",
        "srt",
    )
    parsed = ct_downloader.build_arg_parser().parse_args(args)
    assert parsed.mode == "subtitles"
    assert parsed.subtitle_format == "srt"


def test_gui_txt_command_is_accepted_by_downloader_cli():
    """GUI command for txt subtitles must parse without error."""
    args = _gui_args(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        "Highest Available",
        "subtitles",
        "txt",
    )
    parsed = ct_downloader.build_arg_parser().parse_args(args)
    assert parsed.mode == "subtitles"
    assert parsed.subtitle_format == "txt"


def test_gui_srt_txt_command_is_accepted_by_downloader_cli():
    """GUI 'srt,txt' selection must emit --subtitle-format both and parse."""
    args = _gui_args(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        "Highest Available",
        "subtitles",
        "srt,txt",
    )
    parsed = ct_downloader.build_arg_parser().parse_args(args)
    assert parsed.mode == "subtitles"
    assert parsed.subtitle_format == "both"


def test_gui_video_command_is_accepted_by_downloader_cli():
    """Default video download command from the GUI must also parse cleanly."""
    args = _gui_args(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        "720p",
        "video",
        "srt",
    )
    parsed = ct_downloader.build_arg_parser().parse_args(args)
    assert parsed.mode == "video"
    assert parsed.quality == "720"


def test_build_download_command_srt_txt_maps_to_both():
    """GUI dropdown 'srt,txt' must map to CLI --subtitle-format both."""
    command = ct_gui.build_download_command(
        "https://example.test/episode/123",
        "Highest Available",
        "subtitles",
        "srt,txt",
    )
    assert "--subtitle-format" in command
    idx = command.index("--subtitle-format")
    assert command[idx + 1] == "both"


def test_start_download_includes_srt_txt_subtitle_format(monkeypatch, tmp_path):
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
    monkeypatch.setattr(ct_gui, "mode_var", Value("subtitles"), raising=False)
    monkeypatch.setattr(ct_gui, "subtitle_format_var", Value("srt,txt"), raising=False)
    monkeypatch.setattr(ct_gui, "DOWNLOAD_DIR", tmp_path)
    monkeypatch.setattr(ct_gui, "launch_download", launched.append)

    ct_gui.start_download()

    assert launched[0][-2:] == ["--subtitle-format", "both"]


# ---------------------------------------------------------------------------
# Frozen-mode tests (sys.frozen)
# ---------------------------------------------------------------------------


def test_get_downloader_command_returns_none_when_frozen(monkeypatch):
    """When running as a frozen binary, get_downloader_command returns None."""
    monkeypatch.setattr(ct_gui.sys, "frozen", True, raising=False)

    assert ct_gui.get_downloader_command() is None


def test_build_download_command_returns_none_when_frozen(monkeypatch):
    """Frozen mode: build_download_command returns None (handled in-process)."""
    monkeypatch.setattr(ct_gui.sys, "frozen", True, raising=False)

    result = ct_gui.build_download_command(
        "https://example.test/episode/123",
        "Highest Available",
        "subtitles",
        "txt",
    )
    assert result is None


def test_get_downloader_command_uses_script_when_not_frozen(monkeypatch):
    """Source-mode: get_downloader_command still finds ct_downloader.py."""
    monkeypatch.delattr(ct_gui.sys, "frozen", raising=False)
    monkeypatch.delenv("CT_DOWNLOADER_PATH", raising=False)
    monkeypatch.setattr(ct_gui.shutil, "which", lambda name: None)
    monkeypatch.setattr(ct_gui, "DOWNLOADER_SCRIPT", GUI_PATH.parents[0] / "ct_downloader.py")

    command = ct_gui.get_downloader_command()
    assert command is not None
    assert "ct_downloader.py" in command[-1]


# ---------------------------------------------------------------------------
# _run_frozen_download tests (in-process downloader when frozen)
# ---------------------------------------------------------------------------


def test_run_frozen_download_dispatches_episode(monkeypatch):
    """_run_frozen_download calls download_episode for an episode URL."""
    called = []
    monkeypatch.setattr(
        ct_downloader,
        "download_episode",
        lambda url, quality: called.append((url, quality)),
    )

    ct_gui._run_frozen_download(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        "Highest Available",
        "video",
        "srt",
    )

    assert called == [("https://www.ceskatelevize.cz/porady/123-show/12345678901/", None)]


def test_run_frozen_download_dispatches_subtitles_with_format(monkeypatch):
    """_run_frozen_download passes subtitle_format for subtitles mode."""
    called = []
    monkeypatch.setattr(
        ct_downloader,
        "download_episode",
        lambda url, quality, mode, subtitle_format: called.append(
            (url, quality, mode, subtitle_format)
        ),
    )

    ct_gui._run_frozen_download(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        "720p",
        "subtitles",
        "srt,txt",
    )

    assert called == [
        (
            "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
            "720",
            "subtitles",
            "both",
        )
    ]


def test_run_frozen_download_dispatches_series(monkeypatch, capsys):
    """_run_frozen_download handles series URLs."""
    called = []
    monkeypatch.setattr(
        ct_downloader,
        "download_episode",
        lambda url, quality: called.append(url),
    )
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "/porady/123-show/12345678901/",
    )

    ct_gui._run_frozen_download(
        "https://www.ceskatelevize.cz/porady/123-show/",
        "Highest Available",
        "video",
        "srt",
    )

    assert called == ["https://www.ceskatelevize.cz/porady/123-show/12345678901/"]
    assert "Batch download complete" in capsys.readouterr().out


def test_run_frozen_download_reports_invalid_url(capsys):
    """_run_frozen_download prints error for non-matching URLs."""
    ct_gui._run_frozen_download(
        "https://example.test/not-valid",
        "Highest Available",
        "video",
        "srt",
    )

    assert "Invalid" in capsys.readouterr().out


def test_run_frozen_download_series_no_episodes(monkeypatch, capsys):
    """_run_frozen_download handles series with no episodes found."""
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "<html>nothing here</html>",
    )

    ct_gui._run_frozen_download(
        "https://www.ceskatelevize.cz/porady/123-show/",
        "Highest Available",
        "video",
        "srt",
    )

    assert "No episodes found" in capsys.readouterr().out


def test_start_download_uses_frozen_path(monkeypatch, tmp_path):
    """When frozen, start_download calls _run_frozen_download instead of launch_download."""

    class Field:
        def get(self):
            return "https://example.test/porady/123-show/12345678901/"

        def delete(self, start, end):
            pass

    class Value:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

    monkeypatch.setattr(ct_gui.sys, "frozen", True, raising=False)
    monkeypatch.setattr(ct_gui, "url_entry", Field(), raising=False)
    monkeypatch.setattr(ct_gui, "quality_var", Value("Highest Available"), raising=False)
    monkeypatch.setattr(ct_gui, "mode_var", Value("video"), raising=False)
    monkeypatch.setattr(ct_gui, "subtitle_format_var", Value("srt"), raising=False)
    monkeypatch.setattr(ct_gui, "DOWNLOAD_DIR", tmp_path)

    frozen_calls = []
    monkeypatch.setattr(
        ct_gui,
        "_run_frozen_download",
        lambda url, quality, mode, fmt: frozen_calls.append((url, quality, mode, fmt)),
    )

    ct_gui.start_download()

    assert len(frozen_calls) == 1
    assert frozen_calls[0][0] == "https://example.test/porady/123-show/12345678901/"
