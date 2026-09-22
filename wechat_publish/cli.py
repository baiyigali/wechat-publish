"""CLI entry point for wechat_publish.

Installs the ``wechat-publish`` console script via ``[project.scripts]``.
"""

from __future__ import annotations

import argparse
import os
import sys

from .core import push_articles


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wechat-publish",
        description="Push rendered HTML files to WeChat MP (1-8 articles per push).",
        epilog="""\
Examples:
  wechat-publish --html a.html --title "标题" --cover c.jpg
  wechat-publish \\
      --html a1.html --title "标题1" --cover c1.jpg \\
      --html a2.html --title "标题2" --cover c2.jpg \\
      --author "程序员白大力" --comment --publish
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--html", action="append", required=True,
                        help="Path to rendered HTML file (repeat for multiple articles)")
    parser.add_argument("--title", action="append", required=True,
                        help="Article title (repeat, one per --html)")
    parser.add_argument("--cover", action="append", required=True,
                        help="Cover image path (repeat, one per --html)")
    parser.add_argument("--author", default="", help="Author name (max 16 chars)")
    parser.add_argument("--comment", action="store_true", help="Open comments")
    parser.add_argument("--publish", action="store_true", help="Publish immediately")
    parser.add_argument("--appid", default=os.environ.get("WECHAT_APPID", ""))
    parser.add_argument("--secret", default=os.environ.get("WECHAT_SECRET", ""))
    args = parser.parse_args()

    if not args.appid or not args.secret:
        sys.exit("Error: set WECHAT_APPID / WECHAT_SECRET env vars or pass --appid/--secret")

    if not (len(args.html) == len(args.title) == len(args.cover)):
        sys.exit("Error: --html, --title and --cover must be repeated the same number of times")

    articles = [
        {"html_path": h, "title": t, "cover_path": c}
        for h, t, c in zip(args.html, args.title, args.cover)
    ]

    push_articles(
        args.appid, args.secret, articles,
        author=args.author,
        open_comment=args.comment,
        publish_now=args.publish,
    )


if __name__ == "__main__":
    main()
