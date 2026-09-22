"""Usage example for wechat_publish.

This does NOT run against the real API by default — it shows how to build the
``articles`` payload and call ``push_articles()``. Set real credentials to go live.

Run:
    python examples/demo.py
"""

from pathlib import Path

from wechat_publish import push_articles

# 1) Prepare your rendered HTML + cover somewhere on disk.
#    (wechat-publish expects already-rendered HTML; pair it with a formatter
#    such as the `wechat-formatter` package to produce the HTML.)
here = Path(__file__).resolve().parent
html_path = here / "article.html"
cover_path = here / "cover.jpg"

# 2) Point to your公众号 credentials. Prefer env vars over hardcoding.
import os

appid = os.environ.get("WECHAT_APPID", "wx你的AppID")
secret = os.environ.get("WECHAT_SECRET", "你的AppSecret")

# 3) Push. publish_now=False -> save to draft box only.
if html_path.exists() and cover_path.exists():
    draft_id = push_articles(
        appid=appid,
        secret=secret,
        articles=[
            {
                "html_path": str(html_path),
                "title": "示例文章标题",
                "cover_path": str(cover_path),
                "digest": "文章摘要，最长120字",
                # "source_url": "https://example.com/read-more",  # 可选：阅读原文
            },
        ],
        author="程序员白大力",
        open_comment=True,
        publish_now=False,  # 改成 True 立即群发
    )
    print("draft media_id =", draft_id)
else:
    print("article.html / cover.jpg 不存在，仅演示调用方式（未真正请求微信接口）。")
    print("把渲染好的 HTML 和封面放到 examples/ 下，或在代码里指定真实路径。")
