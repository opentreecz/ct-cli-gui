import ct_downloader


def test_extract_transcript_from_json():
    assert ct_downloader._extract_transcript(r'{"transcriptText":"Hello \u010desk\u00fd"}') == (
        "Hello \u010desk\u00fd"
    )


def test_extract_transcript_from_meta_and_returns_none():
    assert (
        ct_downloader._extract_transcript('<meta name="transcript" content="Hello &amp; world">')
        == "Hello & world"
    )
    assert ct_downloader._extract_transcript("<html>no transcript</html>") is None


def test_download_subtitles_can_save_plain_text(monkeypatch, tmp_path):
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
    assert (tmp_path / result).read_text(encoding="utf-8") == "Hello world\n"
    assert not (tmp_path / "Episode.cs.srt").exists()


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


def test_download_episode_downloads_transcript_only(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        ct_downloader,
        "get_html",
        lambda url: (
            '<title>Episode - Series</title><section id="transcript">Hello &amp; welcome.</section>'
        ),
    )

    ct_downloader.download_episode(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/",
        download_mode="transcript",
    )

    assert (tmp_path / "Episode - Series.txt").read_text(encoding="utf-8") == ("Hello & welcome.\n")
    assert "Saved transcript" in capsys.readouterr().out


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
