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


# ---------- local image support (v1.0.1) ----------

class _FakeUploadResp:
    def __init__(self, url):
        self._data = {"url": url}

    def json(self):
        return self._data


PNG_BYTES = b"\x89PNG\r\n\x1a\nfakepng"


def _patch_uploadimg(monkeypatch, captured):
    def fake_post(url, params=None, files=None, timeout=None):
        captured["files"] = files
        return _FakeUploadResp("https://mmbiz.qpic.cn/uploaded")
    monkeypatch.setattr("wechat_publish.core.requests.post", fake_post)


def test_upload_content_images_local_relative_path(tmp_path, monkeypatch):
    """相对路径的本地 <img> 应基于 base_dir 找到文件并上传替换。"""
    img = tmp_path / "cover.png"
    img.write_bytes(PNG_BYTES)
    html = f'<p><img src="cover.png"></p>'
    captured = {}
    _patch_uploadimg(monkeypatch, captured)

    result = upload_content_images("token", html, base_dir=tmp_path)

    assert captured["files"]["media"][0] == "img.png"
    assert captured["files"]["media"][2] == "image/png"
    assert 'src="https://mmbiz.qpic.cn/uploaded"' in result
    assert 'src="cover.png"' not in result


def test_upload_content_images_local_absolute_path(tmp_path, monkeypatch):
    img = tmp_path / "sub"
    img.mkdir()
    img = img / "pic.jpg"
    img.write_bytes(b"\xff\xd8fakejpg")
    html = f'<img src="{img}">'
    captured = {}
    _patch_uploadimg(monkeypatch, captured)

    result = upload_content_images("token", html)

    assert captured["files"]["media"][2] == "image/jpeg"
    assert 'src="https://mmbiz.qpic.cn/uploaded"' in result


def test_upload_content_images_local_file_scheme(tmp_path, monkeypatch):
    img = tmp_path / "a.png"
    img.write_bytes(PNG_BYTES)
    html = f'<img src="file://{img}">'
    captured = {}
    _patch_uploadimg(monkeypatch, captured)

    result = upload_content_images("token", html, base_dir=tmp_path)
    assert 'src="https://mmbiz.qpic.cn/uploaded"' in result


def test_upload_content_images_missing_local_file_warns(tmp_path, monkeypatch, capsys):
    """本地文件不存在时跳过并告警，不抛异常、不改写 src。"""
    html = '<img src="not_exist.png">'
    result = upload_content_images("token", html, base_dir=tmp_path)
    assert 'src="not_exist.png"' in result  # 原样保留
    assert "local image not found" in capsys.readouterr().out


def test_upload_content_images_mixed_sources(tmp_path, monkeypatch):
    """远程 URL 与本地路径混用时各自正确处理。"""
    img = tmp_path / "local.png"
    img.write_bytes(PNG_BYTES)
    html = ('<img src="local.png">'
            '<img src="https://example.com/remote.jpg">')
    captured = {}
    _patch_uploadimg(monkeypatch, captured)

    def fake_get(url, timeout=None):
        class R:
            content = b"remotebytes"
            headers = {"Content-Type": "image/jpeg"}
            def raise_for_status(self): pass
        return R()
    monkeypatch.setattr("wechat_publish.core.requests.get", fake_get)

    result = upload_content_images("token", html, base_dir=tmp_path)
    assert result.count('src="https://mmbiz.qpic.cn/uploaded"') == 2
    assert "local.png" not in result and "example.com" not in result
