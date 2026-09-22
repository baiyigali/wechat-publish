"""Low-level and high-level API for publishing to WeChat Official Account (公众号).

This module is a faithful refactor of the original ``wechat_publish.py`` script:
all behavior (error handling, image re-hosting, draft + publish flow) is kept.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import requests

BASE = "https://api.weixin.qq.com/cgi-bin"
MAX_ARTICLES = 8  # WeChat allows 1-8 articles per draft


class WeChatAPIError(RuntimeError):
    """Raised when WeChat returns an errcode != 0."""


def _check(resp: requests.Response, action: str) -> dict:
    """Parse a WeChat JSON response and raise on API error."""
    data = resp.json()
    if "errcode" in data and data["errcode"] != 0:
        raise WeChatAPIError(
            f"{action} failed: errcode={data['errcode']} errmsg={data.get('errmsg', '')}"
        )
    return data


# ---------------------------------------------------------------------------
# Low-level API
# ---------------------------------------------------------------------------
def get_access_token(appid: str, secret: str) -> str:
    """Fetch a valid access_token. Valid for ~2 hours."""
    resp = requests.get(
        f"{BASE}/token",
        params={"grant_type": "client_credential", "appid": appid, "secret": secret},
        timeout=15,
    )
    data = _check(resp, "get access_token")
    token = data.get("access_token")
    if not token:
        raise WeChatAPIError(f"no access_token in response: {data}")
    return token


def upload_cover(token: str, image_path: str | Path) -> str:
    """Upload an image as a permanent material, returns thumb_media_id."""
    image_path = Path(image_path)
    with open(image_path, "rb") as f:
        resp = requests.post(
            f"{BASE}/material/add_material",
            params={"access_token": token, "type": "image"},
            files={"media": (image_path.name, f, "image/jpeg")},
            timeout=30,
        )
    data = _check(resp, "upload cover")
    media_id = data.get("media_id")
    if not media_id:
        raise WeChatAPIError(f"no media_id in response: {data}")
    return media_id


def upload_content_images(token: str, html: str) -> str:
    """Download every external <img> in *html*, upload it to WeChat, and
    rewrite the ``src`` to WeChat's own CDN URL.

    WeChat filters non-WeChat image URLs out of article content, so we
    must proxy them through ``/cgi-bin/media/uploadimg`` first.
    """
    img_urls = re.findall(r'<img[^>]+src="([^"]+)"', html)
    if not img_urls:
        return html

    replaced = html
    for url in img_urls:
        host = urlparse(url).netloc
        if "mmbiz.qpic.cn" in host or "mmecoa.com" in host:
            continue

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"  [warn] failed to download {url}: {e}")
            continue

        content_type = resp.headers.get("Content-Type", "image/jpeg")
        ext_map = {
            "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png",
            "image/gif": "gif", "image/webp": "webp",
        }
        ext = ext_map.get(content_type, "jpg")
        fname = f"img.{ext}"

        up = requests.post(
            f"{BASE}/media/uploadimg",
            params={"access_token": token},
            files={"media": (fname, resp.content, content_type)},
            timeout=30,
        )
        up_data = up.json()
        if "url" not in up_data:
            print(f"  [warn] uploadimg failed for {url}: {up_data}")
            continue

        wechat_url = up_data["url"]
        print(f"  [image] {url} -> {wechat_url}")
        replaced = replaced.replace(f'src="{url}"', f'src="{wechat_url}"')

    return replaced


def add_draft(token: str, articles: list[dict]) -> str:
    """Create a draft with 1-8 articles. Returns draft media_id."""
    body = json.dumps({"articles": articles}, ensure_ascii=False).encode("utf-8")
    resp = requests.post(
        f"{BASE}/draft/add",
        params={"access_token": token},
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=60,
    )
    data = _check(resp, "add draft")
    media_id = data.get("media_id")
    if not media_id:
        raise WeChatAPIError(f"no media_id in draft response: {data}")
    return media_id


def publish(token: str, media_id: str) -> dict:
    """Submit a draft for publishing. Returns the publish job info."""
    body = json.dumps({"media_id": media_id}, ensure_ascii=False).encode("utf-8")
    resp = requests.post(
        f"{BASE}/freepublish/submit",
        params={"access_token": token},
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=30,
    )
    return _check(resp, "publish")


# ---------------------------------------------------------------------------
# High-level API — call this from your own code
# ---------------------------------------------------------------------------
def push_articles(
    appid: str,
    secret: str,
    articles: list[dict],
    *,
    author: str = "",
    open_comment: bool = False,
    publish_now: bool = False,
) -> str:
    """Push one or more articles to WeChat MP.

    Parameters
    ----------
    appid : str
        WeChat official account AppID.
    secret : str
        WeChat official account AppSecret.
    articles : list[dict]
        Each dict must contain:
          - ``html_path``  — path to the rendered HTML file
          - ``title``      — article title (max 32 chars)
          - ``cover_path`` — path to the cover image (jpg/png)
        Optional keys per article:
          - ``digest``     — summary (max 120 chars)
          - ``source_url`` — "read more" URL
        Up to 8 articles allowed.
    author : str
        Author name for all articles (max 16 chars).
    open_comment : bool
        Whether to enable comments on all articles.
    publish_now : bool
        If True, publish immediately after creating the draft.
        If False, only save to draft box.

    Returns
    -------
    str
        The draft ``media_id`` (pass to ``publish()`` to publish later).
    """
    n = len(articles)
    if n < 1:
        raise ValueError("at least one article is required")
    if n > MAX_ARTICLES:
        raise ValueError(f"WeChat allows at most {MAX_ARTICLES} articles per push (got {n})")

    # Token
    token = get_access_token(appid, secret)
    print(f"[1/3] got access_token")

    # Build articles
    wechat_articles = []
    for i, art in enumerate(articles):
        title = art["title"]
        print(f"[2/3] article {i + 1}/{n}: {title}")

        html_path = Path(art["html_path"])
        if not html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_path}")
        content = html_path.read_text(encoding="utf-8")

        # Rehost external images
        content = upload_content_images(token, content)

        # Upload cover
        cover_path = Path(art["cover_path"])
        if not cover_path.exists():
            raise FileNotFoundError(f"cover image not found: {cover_path}")
        thumb_id = upload_cover(token, cover_path)

        wechat_articles.append({
            "title": title,
            "author": author[:16],
            "digest": art.get("digest", ""),
            "content": content,
            "content_source_url": art.get("source_url", ""),
            "thumb_media_id": thumb_id,
            "need_open_comment": 1 if open_comment else 0,
            "only_fans_can_comment": 0,
        })

    # Create draft
    draft_id = add_draft(token, wechat_articles)
    print(f"[3/3] draft created -> media_id={draft_id}")

    if publish_now:
        result = publish(token, draft_id)
        print(f"published! publish_id={result.get('publish_id')}")
    else:
        print("draft saved (not published). pass publish_now=True to publish immediately.")

    return draft_id
