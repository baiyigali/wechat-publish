"""Offline unit tests for wechat_publish — no real WeChat API calls.

Network calls are patched, so this runs in CI with zero credentials.
"""

from pathlib import Path

import pytest

from wechat_publish import (
    MAX_ARTICLES,
    WeChatAPIError,
    __version__,
    push_articles,
    upload_content_images,
)
from wechat_publish.core import _check


class _FakeResp:
    def __init__(self, data):
        self._data = data
        self.headers = {}

    def json(self):
        return self._data


def test_version_exported():
    assert isinstance(__version__, str)
    assert __version__


def test_check_raises_on_errcode():
    with pytest.raises(WeChatAPIError):
        _check(_FakeResp({"errcode": 40001, "errmsg": "invalid credential"}), "test")


def test_check_passes_when_no_errcode():
    data = {"access_token": "abc"}
    assert _check(_FakeResp(data), "test") is data


def test_push_articles_requires_at_least_one():
    with pytest.raises(ValueError):
        push_articles("wx", "secret", [])


def test_push_articles_caps_at_eight():
    articles = [{"html_path": "x", "title": "t", "cover_path": "x"}] * (MAX_ARTICLES + 1)
    with pytest.raises(ValueError):
        push_articles("wx", "secret", articles)


def test_upload_content_images_no_images_returns_unchanged():
    html = "<p>hello</p>"
    assert upload_content_images("token", html) == html


def test_upload_content_images_skips_wechat_hosts(monkeypatch):
    # mmbiz images must NOT be downloaded / re-uploaded
    html = '<p><img src="https://mmbiz.qpic.cn/aaa/640"></p>'
    calls = []

    def _no_get(*a, **k):
        calls.append(a)
        raise AssertionError("should not download mmbiz image")

    monkeypatch.setattr("wechat_publish.core.requests.get", _no_get)
    out = upload_content_images("token", html)
    assert out == html
    assert calls == []


def test_upload_content_images_replaces_external_image(monkeypatch):
    html = '<p><img src="https://example.com/a.png"></p>'

    class _ImgResp:
        headers = {"Content-Type": "image/png"}

        def raise_for_status(self):
            pass

        content = b"\x89PNG fake"

    def fake_get(url, timeout=0):
        return _ImgResp()

    def fake_post(url, params=None, files=None, timeout=0):
        return _FakeResp({"url": "https://mmbiz.qpic.cn/wechat/new.png"})

    monkeypatch.setattr("wechat_publish.core.requests.get", fake_get)
    monkeypatch.setattr("wechat_publish.core.requests.post", fake_post)

    out = upload_content_images("token", html)
    assert "example.com/a.png" not in out
    assert "mmbiz.qpic.cn/wechat/new.png" in out


def test_push_articles_missing_html_file_raises(tmp_path, monkeypatch):
    # token fetch succeeds, but html_path does not exist
    monkeypatch.setattr(
        "wechat_publish.core.get_access_token", lambda a, s: "tok"
    )
    missing = tmp_path / "nope.html"
    with pytest.raises(FileNotFoundError):
        push_articles(
            "wx", "secret",
            [{"html_path": str(missing), "title": "t", "cover_path": str(tmp_path / "c.jpg")}],
        )
