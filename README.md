# wechat-publish

把渲染好的 **HTML 文章一键发布到微信公众号**：自动获取 access_token、把正文里的图片转存到微信 CDN、上传封面、创建草稿，可选择立即群发。

正文图片支持两种来源（v1.0.1+）：**远程 http(s) URL**（下载后转存）和**本地文件路径**（相对路径基于渲染 HTML 所在目录解析，也支持绝对路径与 `file://` 前缀），都会自动上传到微信并替换为 `mmbiz.qpic.cn` 地址；本地文件不存在时跳过并告警，不中断发布。

支持一次推送 **1–8 篇图文**（微信草稿上限），同时提供 Python API 和命令行两种用法。

## 安装

```bash
pip install wechat-publish
```

或从源码安装：

```bash
cd wechat-publish
pip install .
```

依赖仅 [`requests`](https://docs.python-requests.org/)。

## 快速开始

### Python API

```python
from wechat_publish import push_articles

draft_id = push_articles(
    appid="wx你的AppID",
    secret="你的AppSecret",
    articles=[
        {"html_path": "a1.html", "title": "标题1", "cover_path": "c1.jpg"},
        {"html_path": "a2.html", "title": "标题2", "cover_path": "c2.jpg"},
    ],
    author="程序员白大力",
    open_comment=True,
    publish_now=True,   # True=立即群发；False=只存草稿箱
)
print("draft media_id =", draft_id)
```

### 命令行

安装后会得到 `wechat-publish` 命令。AppID / AppSecret 优先读环境变量：

```bash
export WECHAT_APPID="wx你的AppID"
export WECHAT_SECRET="你的AppSecret"

wechat-publish \
    --html a1.html --title "标题1" --cover c1.jpg \
    --html a2.html --title "标题2" --cover c2.jpg \
    --author "程序员白大力" --comment --publish
```

不传 `--publish` 则只存草稿箱；也可以用 `--appid` / `--secret` 直接传入。

## 文章字段说明

`articles` 列表里每一项是一个 dict：

| 字段 | 必填 | 说明 |
|---|---|---|
| `html_path` | 是 | 渲染好的 HTML 文件路径（UTF-8） |
| `title` | 是 | 文章标题，最长 32 字 |
| `cover_path` | 是 | 封面图路径（jpg/png），会作为永久素材上传 |
| `digest` | 否 | 摘要，最长 120 字 |
| `source_url` | 否 | “阅读原文”跳转链接 |

公共参数：

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `author` | `str` | `""` | 作者名，最长 16 字 |
| `open_comment` | `bool` | `False` | 是否打开评论 |
| `publish_now` | `bool` | `False` | True 立即群发，False 仅存草稿 |

## 工作流程

调用 `push_articles()` 时内部按顺序执行：

1. **获取 access_token** —— `cgi-bin/token`，有效期约 2 小时。
2. **处理正文图片** —— 扫描 HTML 里所有 `<img src>`，把非微信域名（`mmbiz.qpic.cn` / `mmecoa.com` 除外）的图片下载后通过 `cgi-bin/media/uploadimg` 转存，并把 `src` 改写成微信 CDN 地址（微信会过滤外链图片）。
3. **上传封面** —— 通过 `cgi-bin/material/add_material` 上传为永久图片素材，拿到 `thumb_media_id`。
4. **创建草稿** —— `cgi-bin/draft/add`，一次最多 8 篇。
5. **（可选）群发** —— `cgi-bin/freepublish/submit`。

任一接口返回 `errcode != 0` 都会抛出 `wechat_publish.WeChatAPIError`，错误信息里带 errcode / errmsg。

## API 一览

```python
from wechat_publish import (
    push_articles,          # 高层入口，从自己代码里调用
    WeChatAPIError,         # 接口错误异常
    get_access_token,        # 低层：取 token
    upload_cover,           # 低层：上传封面永久素材
    upload_content_images,  # 低层：转存正文图片并改写 src
    add_draft,              # 低层：创建草稿
    publish,                # 低层：提交群发
    MAX_ARTICLES,           # 8
)
```

> 常见用法：先 `push_articles(..., publish_now=False)` 存草稿，在公众号后台人工预览确认后，再用返回的 `draft media_id` 调 `publish(token, media_id)` 正式群发。

## CI / 自动发布

仓库自带 GitHub Actions（`.github/workflows/publish.yml`），与常见开源 Python 包一致：

- **push 到 `main`** → 编译 sdist + wheel，自动发布到 **TestPyPI**（官方测试源，验证打包流程不污染正式版）；
- **打 tag `v*`**（如 `v1.0.0`）→ 编译后发布到**正式 PyPI**；
- 也支持在 Actions 页面手动触发（`workflow_dispatch`），只编译不发布。

免密推送：在 PyPI / TestPyPI 后台把本仓库配置为 **Trusted Publisher（OIDC）**，workflow 里 `id-token: write` 自动换取临时凭据，不需要任何 `PYPI_API_TOKEN`。

## 技术交流

扫码添加微信，交流使用问题、定制与合作：

<p align="center">
  <img src="docs/images/wechat-contact-qr.jpg" alt="微信二维码" width="240" />
</p>

## 项目赞助

本项目由微信公众号 **「程序员白大力」** 提供赞助，感谢支持：

<p align="center">
  <img src="docs/images/wechat-official-account-qr.png" alt="程序员白大力公众号二维码" width="240" />
</p>

## License

MIT
