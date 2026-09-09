import ct_downloader


def test_download_subtitles_returns_none_without_url():
    assert (
        ct_downloader._download_subtitles('{"stream":"https://media.example/video.mpd"}', "Episode")
        is None
    )


def test_download_subtitles_returns_none_when_conversion_does_not_create_file(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader.urllib.request,
        "urlretrieve",
        lambda url, filename: (tmp_path / filename).write_text("vtt"),
    )
    monkeypatch.setattr(
        ct_downloader.subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {"returncode": 1})(),
    )

    assert (
        ct_downloader._download_subtitles(
            '{"subtitle":"https://media.example/subtitle.vtt"}', "Episode"
        )
        is None
    )


def test_format_episode_name():
    result = ct_downloader.format_episode_name(
        "3/10 The Episode: Title - Example Series | iVysílání"
    )

    assert result == "Example Series - S1E03 - The Episode- Title"


def test_format_episode_name_fallback_sanitizes_filename():
    assert ct_downloader.format_episode_name("A/B: C | iVysílání") == "A-B- C"


def test_stream_api_url_contains_video_and_device_ids():
    url = ct_downloader.STREAM_API_URL.format(
        video_id="12345678901",
        device_id="device-id",
    )

    assert "/external/12345678901?" in url
    assert "deviceId=device-id" in url
    assert "streamType=dash" in url


def test_get_html_returns_response_content(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b"<html>ok</html>"

    monkeypatch.setattr(ct_downloader.urllib.request, "urlopen", lambda *args, **kwargs: Response())

    assert ct_downloader.get_html("https://example.test") == "<html>ok</html>"


def test_get_html_returns_empty_string_on_network_error(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr(ct_downloader.urllib.request, "urlopen", fail)

    assert ct_downloader.get_html("https://example.test") == ""
    assert "Error fetching page" in capsys.readouterr().out


def test_srt_to_text_strips_timing_and_indices():
    srt = (
        "1\n"
        "00:00:01,000 --> 00:00:02,000\n"
        "Hello <i>world</i>\n"
        "\n"
        "2\n"
        "00:00:03,000 --> 00:00:04,000\n"
        "Second line\n"
    )
    assert ct_downloader._srt_to_text(srt) == "Hello world\nSecond line"


def test_srt_to_text_returns_empty_string_for_empty_input():
    assert ct_downloader._srt_to_text("") == ""


def test_main_dispatches_episode_url(monkeypatch):
    called = []
    monkeypatch.setattr(
        ct_downloader,
        "download_episode",
        lambda url, quality: called.append((url, quality)),
    )
    monkeypatch.setattr(
        ct_downloader.sys,
        "argv",
        ["ct_downloader.py", "https://www.ceskatelevize.cz/porady/123-show/12345678901/"],
    )

    ct_downloader.main()

    assert called == [("https://www.ceskatelevize.cz/porady/123-show/12345678901/", None)]


def test_download_episode_rejects_url_without_video_id(capsys):
    ct_downloader.download_episode("https://example.test/not-an-episode")

    assert "Could not extract video ID" in capsys.readouterr().out


def test_download_episode_reports_missing_subtitles_in_only_mode(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "<title>Episode - Series</title>",
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"stream": "https://media.example/episode.mpd"}'

    monkeypatch.setattr(ct_downloader.urllib.request, "urlopen", lambda *args, **kwargs: Response())

    ct_downloader.download_episode(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        download_mode="subtitles",
    )

    assert "Subtitles not found" in capsys.readouterr().out


def test_download_episode_reports_missing_stream(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "<title>1/10 Episode - Series</title>",
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"subtitles": []}'

    monkeypatch.setattr(ct_downloader.urllib.request, "urlopen", lambda *args, **kwargs: Response())

    ct_downloader.download_episode("https://www.ceskatelevize.cz/porady/123-show/12345678901/")

    assert "Stream URL not found" in capsys.readouterr().out


def test_download_episode_passes_quality_to_ytdlp(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "<title>1/10 Episode - Series</title>",
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"stream": "https://media.example/episode.mpd"}'

    commands = []

    def run(command, **kwargs):
        commands.append(command)
        (tmp_path / "Series - S1E01 - Episode.mp4").touch()
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(ct_downloader.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(ct_downloader.subprocess, "run", run)

    ct_downloader.download_episode(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        quality="720",
    )

    assert commands == [
        [
            "yt-dlp",
            "-o",
            "Series - S1E01 - Episode.mp4",
            "-S",
            "res:720",
            "https://media.example/episode.mpd",
        ]
    ]


def test_download_episode_embeds_subtitles(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "<title>1/10 Episode - Series</title>",
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return (
                b'{"subtitle": "https://media.example/subtitle.vtt", '
                b'"stream": "https://media.example/episode.mpd"}'
            )

    def download(url, filename):
        (tmp_path / filename).write_text("subtitle")

    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[0] == "yt-dlp":
            (tmp_path / "Series - S1E01 - Episode.mp4").write_text("video")
        elif len(command) > 5:
            (tmp_path / "Series - S1E01 - Episode.mp4").write_text("embedded")
        else:
            (tmp_path / "Series - S1E01 - Episode.cs.srt").write_text("converted")
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(ct_downloader.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(ct_downloader.urllib.request, "urlretrieve", download)
    monkeypatch.setattr(ct_downloader.subprocess, "run", run)

    ct_downloader.download_episode("https://www.ceskatelevize.cz/porady/123-show/12345678901/")

    assert len(calls) == 3
    assert "Subtitles successfully embedded" in capsys.readouterr().out


def test_main_dispatches_series_episodes(monkeypatch):
    called = []
    monkeypatch.setattr(ct_downloader, "download_episode", lambda url, quality: called.append(url))
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "/porady/123-show/12345678901/ /porady/123-show/12345678902/",
    )
    monkeypatch.setattr(
        ct_downloader.sys,
        "argv",
        ["ct_downloader.py", "https://www.ceskatelevize.cz/porady/123-show/"],
    )

    ct_downloader.main()

    assert called == [
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        "https://www.ceskatelevize.cz/porady/123-show/12345678902/",
    ]


def test_download_episode_skips_existing_file(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Episode - Series.mp4").write_text("existing")
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "<title>Episode - Series</title>",
    )

    ct_downloader.download_episode("https://www.ceskatelevize.cz/porady/123-show/12345678901/")

    assert "already exists" in capsys.readouterr().out


def test_download_episode_reports_failed_video_download(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "<title>Episode - Series</title>",
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"stream": "https://media.example/episode.mpd"}'

    monkeypatch.setattr(
        ct_downloader.urllib.request,
        "urlopen",
        lambda *args, **kwargs: Response(),
    )
    monkeypatch.setattr(
        ct_downloader.subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {"returncode": 1})(),
    )

    ct_downloader.download_episode("https://www.ceskatelevize.cz/porady/123-show/12345678901/")

    assert "Video download failed" in capsys.readouterr().out


def test_main_rejects_invalid_url(monkeypatch, capsys):
    monkeypatch.setattr(ct_downloader.sys, "argv", ["ct_downloader.py", "not-a-url"])

    ct_downloader.main()

    assert "Invalid Česká televize URL format" in capsys.readouterr().out


def test_main_normalizes_quality_argument(monkeypatch):
    called = []
    monkeypatch.setattr(
        ct_downloader,
        "download_episode",
        lambda url, quality: called.append((url, quality)),
    )
    monkeypatch.setattr(
        ct_downloader.sys,
        "argv",
        [
            "ct_downloader.py",
            "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
            "--quality",
            "720p",
        ],
    )

    ct_downloader.main()

    assert called == [("https://www.ceskatelevize.cz/porady/123-show/12345678901/", "720")]


def test_main_passes_subtitle_mode_to_episode(monkeypatch):
    called = []
    monkeypatch.setattr(
        ct_downloader,
        "download_episode",
        lambda url, quality, mode, subtitle_format: called.append(
            (url, quality, mode, subtitle_format)
        ),
    )
    monkeypatch.setattr(
        ct_downloader.sys,
        "argv",
        [
            "ct_downloader.py",
            "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
            "--subtitles-only",
        ],
    )

    ct_downloader.main()

    assert called == [
        (
            "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
            None,
            "subtitles",
            "srt",
        )
    ]


def test_main_reports_empty_series(monkeypatch, capsys):
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "<html>no episodes</html>",
    )
    monkeypatch.setattr(
        ct_downloader.sys,
        "argv",
        ["ct_downloader.py", "https://www.ceskatelevize.cz/porady/123-show/"],
    )

    ct_downloader.main()

    assert "No episodes found" in capsys.readouterr().out


def test_download_episode_handles_poster_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: (
            "<title>Episode - Series</title>"
            '<meta property="og:image" content="https://media.example/poster.jpg">'
        ),
    )

    def fail_download(*args, **kwargs):
        raise OSError("poster unavailable")

    monkeypatch.setattr(ct_downloader.urllib.request, "urlretrieve", fail_download)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"stream": "https://media.example/episode.mpd"}'

    monkeypatch.setattr(ct_downloader.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(
        ct_downloader.subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {"returncode": 1})(),
    )

    ct_downloader.download_episode("https://www.ceskatelevize.cz/porady/123-show/12345678901/")

    assert "Could not download episode poster" in capsys.readouterr().out


def test_download_episode_handles_subtitle_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "<title>1/10 Episode - Series</title>",
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return (
                b'{"subtitle": "https://media.example/subtitle.vtt", '
                b'"stream": "https://media.example/episode.mpd"}'
            )

    def fail_subtitle(url, filename):
        raise OSError("subtitle unavailable")

    monkeypatch.setattr(ct_downloader.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(ct_downloader.urllib.request, "urlretrieve", fail_subtitle)
    monkeypatch.setattr(
        ct_downloader.subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {"returncode": 1})(),
    )

    ct_downloader.download_episode("https://www.ceskatelevize.cz/porady/123-show/12345678901/")

    assert "Could not download or convert subtitles" in capsys.readouterr().out


def test_download_episode_handles_stream_connection_error(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "<title>Episode - Series</title>",
    )
    monkeypatch.setattr(
        ct_downloader.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")),
    )

    ct_downloader.download_episode("https://www.ceskatelevize.cz/porady/123-show/12345678901/")

    assert "Connection error getting stream" in capsys.readouterr().out


def test_download_episode_restores_video_when_subtitle_embedding_fails(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "<title>1/10 Episode - Series</title>",
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return (
                b'{"subtitle": "https://media.example/subtitle.vtt", '
                b'"stream": "https://media.example/episode.mpd"}'
            )

    def download(url, filename):
        (tmp_path / filename).write_text("subtitle")

    def run(command, **kwargs):
        if command[0] == "yt-dlp":
            (tmp_path / "Series - S1E01 - Episode.mp4").write_text("video")
            return type("Result", (), {"returncode": 0})()
        (tmp_path / "Series - S1E01 - Episode.cs.srt").write_text("converted")
        return type("Result", (), {"returncode": 1})()

    monkeypatch.setattr(ct_downloader.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(ct_downloader.urllib.request, "urlretrieve", download)
    monkeypatch.setattr(ct_downloader.subprocess, "run", run)

    ct_downloader.download_episode("https://www.ceskatelevize.cz/porady/123-show/12345678901/")

    assert (tmp_path / "Series - S1E01 - Episode.mp4").read_text() == "video"
    assert "Failed to embed subtitles" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _download_subtitles: subtitle_format three-way logic (srt / txt / both)
# ---------------------------------------------------------------------------


def test_download_subtitles_both_keeps_srt_and_writes_txt(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader.urllib.request,
        "urlretrieve",
        lambda url, filename: (tmp_path / filename).write_text("vtt"),
    )

    def run(command, **kwargs):
        (tmp_path / "Episode.cs.srt").write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nHello <i>world</i>\n"
        )
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(ct_downloader.subprocess, "run", run)

    result = ct_downloader._download_subtitles(
        '{"subtitle":"https://media.example/subtitle.vtt"}', "Episode", "both"
    )

    assert result == "Episode.cs.srt"
    assert (tmp_path / "Episode.cs.srt").exists()
    assert (tmp_path / "Episode.cs.txt").read_text(encoding="utf-8") == "Hello world\n"


def test_download_subtitles_txt_only_deletes_srt(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader.urllib.request,
        "urlretrieve",
        lambda url, filename: (tmp_path / filename).write_text("vtt"),
    )

    def run(command, **kwargs):
        (tmp_path / "Episode.cs.srt").write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nHello <i>world</i>\n"
        )
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(ct_downloader.subprocess, "run", run)

    result = ct_downloader._download_subtitles(
        '{"subtitle":"https://media.example/subtitle.vtt"}', "Episode", "txt"
    )

    assert result == "Episode.cs.txt"
    assert not (tmp_path / "Episode.cs.srt").exists()
    assert (tmp_path / "Episode.cs.txt").read_text(encoding="utf-8") == "Hello world\n"


def test_download_subtitles_default_format_does_not_write_txt(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader.urllib.request,
        "urlretrieve",
        lambda url, filename: (tmp_path / filename).write_text("vtt"),
    )

    def run(command, **kwargs):
        (tmp_path / "Episode.cs.srt").write_text("subtitle content")
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(ct_downloader.subprocess, "run", run)

    result = ct_downloader._download_subtitles(
        '{"subtitle":"https://media.example/subtitle.vtt"}', "Episode"
    )

    assert result == "Episode.cs.srt"
    assert not (tmp_path / "Episode.cs.txt").exists()


# ---------------------------------------------------------------------------
# download_episode: subtitle_format is threaded through in subtitles mode
# ---------------------------------------------------------------------------


def test_download_episode_subtitles_mode_both_writes_both_files(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "<title>Episode - Series</title>",
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"subtitle": "https://media.example/subtitle.vtt"}'

    def download(url, filename):
        (tmp_path / filename).write_text("vtt")

    def run(command, **kwargs):
        (tmp_path / "Episode - Series.cs.srt").write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nHello world\n"
        )
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(ct_downloader.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(ct_downloader.urllib.request, "urlretrieve", download)
    monkeypatch.setattr(ct_downloader.subprocess, "run", run)

    ct_downloader.download_episode(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        download_mode="subtitles",
        subtitle_format="both",
    )

    assert (tmp_path / "Episode - Series.cs.srt").exists()
    assert (tmp_path / "Episode - Series.cs.txt").exists()
    out = capsys.readouterr().out
    assert "Generated standard subtitle file" in out
    assert "Also saved as plain-text subtitle file" in out


def test_download_episode_subtitles_mode_txt_only_produces_txt_only(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "<title>Episode - Series</title>",
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"subtitle": "https://media.example/subtitle.vtt"}'

    def download(url, filename):
        (tmp_path / filename).write_text("vtt")

    def run(command, **kwargs):
        (tmp_path / "Episode - Series.cs.srt").write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nHello world\n"
        )
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(ct_downloader.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(ct_downloader.urllib.request, "urlretrieve", download)
    monkeypatch.setattr(ct_downloader.subprocess, "run", run)

    ct_downloader.download_episode(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        download_mode="subtitles",
        subtitle_format="txt",
    )

    assert not (tmp_path / "Episode - Series.cs.srt").exists()
    assert (tmp_path / "Episode - Series.cs.txt").exists()
    out = capsys.readouterr().out
    assert "Also saved as plain-text subtitle file" in out


def test_download_episode_video_mode_ignores_subtitle_format(monkeypatch, tmp_path):
    """subtitle_format is irrelevant in video mode — always uses srt for embedding."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "<title>Episode - Series</title>",
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"stream": "https://media.example/episode.mpd"}'

    monkeypatch.setattr(ct_downloader.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(
        ct_downloader.subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {"returncode": 1})(),
    )

    # Should not raise even when subtitle_format="txt" is passed in video mode
    ct_downloader.download_episode(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        download_mode="video",
        subtitle_format="txt",
    )

    assert not (tmp_path / "Episode - Series.cs.txt").exists()


# ---------------------------------------------------------------------------
# CLI argument parsing smoke tests
# ---------------------------------------------------------------------------


def test_main_accepts_subtitle_format_srt_argument(monkeypatch):
    """--subtitle-format srt must be accepted by argparse without SystemExit."""
    called = []
    monkeypatch.setattr(
        ct_downloader,
        "download_episode",
        lambda url, quality, mode, subtitle_format: called.append(subtitle_format),
    )
    monkeypatch.setattr(
        ct_downloader.sys,
        "argv",
        [
            "ct_downloader.py",
            "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
            "--mode",
            "subtitles",
            "--subtitle-format",
            "srt",
        ],
    )

    ct_downloader.main()

    assert called == ["srt"]


def test_main_accepts_subtitle_format_txt_argument(monkeypatch):
    """--subtitle-format txt must be accepted and normalized to 'txt'."""
    called = []
    monkeypatch.setattr(
        ct_downloader,
        "download_episode",
        lambda url, quality, mode, subtitle_format: called.append(subtitle_format),
    )
    monkeypatch.setattr(
        ct_downloader.sys,
        "argv",
        [
            "ct_downloader.py",
            "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
            "--mode",
            "subtitles",
            "--subtitle-format",
            "txt",
        ],
    )

    ct_downloader.main()

    assert called == ["txt"]


def test_main_accepts_subtitle_format_both_argument(monkeypatch):
    """--subtitle-format both must be accepted and normalized to 'both'."""
    called = []
    monkeypatch.setattr(
        ct_downloader,
        "download_episode",
        lambda url, quality, mode, subtitle_format: called.append(subtitle_format),
    )
    monkeypatch.setattr(
        ct_downloader.sys,
        "argv",
        [
            "ct_downloader.py",
            "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
            "--mode",
            "subtitles",
            "--subtitle-format",
            "both",
        ],
    )

    ct_downloader.main()

    assert called == ["both"]


def test_main_rejects_unknown_subtitle_format(monkeypatch, capsys):
    """Unrecognised --subtitle-format values must be rejected by argparse."""
    import pytest

    monkeypatch.setattr(
        ct_downloader.sys,
        "argv",
        [
            "ct_downloader.py",
            "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
            "--subtitle-format",
            "docx",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        ct_downloader.main()

    assert exc_info.value.code == 2


def test_main_passes_subtitle_format_txt_to_series(monkeypatch):
    """Series batch dispatch must forward subtitle_format to every episode."""
    called = []
    monkeypatch.setattr(
        ct_downloader,
        "download_episode",
        lambda url, quality, mode, subtitle_format: called.append((mode, subtitle_format)),
    )
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: "/porady/123-show/12345678901/ /porady/123-show/12345678902/",
    )
    monkeypatch.setattr(
        ct_downloader.sys,
        "argv",
        [
            "ct_downloader.py",
            "https://www.ceskatelevize.cz/porady/123-show/",
            "--mode",
            "subtitles",
            "--subtitle-format",
            "txt",
        ],
    )

    ct_downloader.main()

    assert called == [("subtitles", "txt"), ("subtitles", "txt")]


# ---------------------------------------------------------------------------
# Subtitle format synonym normalization
# ---------------------------------------------------------------------------


def test_subtitle_format_synonyms_normalize_to_both():
    for synonym in ("both", "srt,txt", "txt,srt", "srt+txt", "srt + txt"):
        assert ct_downloader._normalize_subtitle_format(synonym) == "both", synonym


def test_subtitle_format_srt_and_txt_stay_as_is():
    assert ct_downloader._normalize_subtitle_format("srt") == "srt"
    assert ct_downloader._normalize_subtitle_format("txt") == "txt"


def test_subtitle_format_rejects_unknown_value():
    import argparse

    import pytest

    with pytest.raises(argparse.ArgumentTypeError):
        ct_downloader._normalize_subtitle_format("docx")


def test_main_accepts_srt_comma_txt_synonym(monkeypatch):
    """--subtitle-format srt,txt must normalize to 'both'."""
    called = []
    monkeypatch.setattr(
        ct_downloader,
        "download_episode",
        lambda url, quality, mode, subtitle_format: called.append(subtitle_format),
    )
    monkeypatch.setattr(
        ct_downloader.sys,
        "argv",
        [
            "ct_downloader.py",
            "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
            "--mode",
            "subtitles",
            "--subtitle-format",
            "srt,txt",
        ],
    )

    ct_downloader.main()

    assert called == ["both"]


def test_main_rejects_transcript_mode(monkeypatch):
    """--mode transcript must now be rejected (transcript removed)."""
    import pytest

    monkeypatch.setattr(
        ct_downloader.sys,
        "argv",
        [
            "ct_downloader.py",
            "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
            "--mode",
            "transcript",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        ct_downloader.main()

    assert exc_info.value.code == 2
