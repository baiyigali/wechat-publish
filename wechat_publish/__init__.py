"""wechat_publish — programmatically publish rendered HTML articles to a
WeChat Official Account (公众号).

Public API::

    from wechat_publish import push_articles, WeChatAPIError

    draft_id = push_articles(
        appid="wx...",
        secret="...",
        articles=[
            {"html_path": "a1.html", "title": "标题1", "cover_path": "c1.jpg"},
        ],
        author="程序员白大力",
        open_comment=True,
        publish_now=True,
    )

A ``wechat-publish`` console script is also installed for quick testing.
"""

from __future__ import annotations

from .core import (
    MAX_ARTICLES,
    WeChatAPIError,
    add_draft,
    get_access_token,
    publish,
    push_articles,
    upload_content_images,
    upload_cover,
)

__all__ = [
    "MAX_ARTICLES",
    "WeChatAPIError",
    "add_draft",
    "get_access_token",
    "publish",
    "push_articles",
    "upload_content_images",
    "upload_cover",
]

__version__ = "1.0.1"
