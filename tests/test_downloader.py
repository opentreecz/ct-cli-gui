import ct_downloader


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

    assert called == [
        ("https://www.ceskatelevize.cz/porady/123-show/12345678901/", None)
    ]


def test_download_episode_rejects_url_without_video_id(capsys):
    ct_downloader.download_episode("https://example.test/not-an-episode")

    assert "Could not extract video ID" in capsys.readouterr().out


def test_download_episode_reports_missing_stream(monkeypatch, tmp_path, capsys):
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
            return b'{"subtitles": []}'

    monkeypatch.setattr(ct_downloader.urllib.request, "urlopen", lambda *args, **kwargs: Response())

    ct_downloader.download_episode(
        "https://www.ceskatelevize.cz/porady/123-show/12345678901/"
    )

    assert "Stream URL not found" in capsys.readouterr().out
