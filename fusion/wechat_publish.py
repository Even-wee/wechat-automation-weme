#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号草稿箱发布（认证号走 WeChat API）。

流程：
  1. 读取 markdown 文章 -> 转为微信兼容的内联样式 HTML（图片先用占位符）
  2. 用 appid+secret 换 access_token
  3. 上传封面图（thumb_media_id）+ 正文内 3 张配图（取 mmbiz url）
  4. 把正文图片占位符替换为真实 url
  5. 调用 draft/add 建草稿，输出 media_id

依赖：curl + jq（系统自带即可）；不依赖第三方 Python 包。

用法：
  python wechat_publish.py \
      --article /path/article.md \
      --cover   /path/cover.png \
      --title   "标题" \
      --digest  "摘要" \
      --author  "湘月姐" \
      --env-file /path/.env        # 内含 WECHAT_APPID / WECHAT_SECRET
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile


def log(tag, msg, level="ok"):
    icon = {"ok": "✅", "warn": "⚠️", "err": "❌", "info": "ℹ️"}.get(level, "•")
    print(f"{icon} [{tag}] {msg}", flush=True)


def run(cmd):
    """运行 shell 命令，返回 (stdout, returncode)。"""
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return p.stdout.strip(), p.returncode


def get_token(appid, secret):
    url = (f"https://api.weixin.qq.com/cgi-bin/token"
           f"?grant_type=client_credential&appid={appid}&secret={secret}")
    out, _ = run(f"curl -s '{url}'")
    try:
        data = json.loads(out)
    except Exception:
        raise RuntimeError(f"解析 token 失败：{out[:200]}")
    if "access_token" not in data:
        raise RuntimeError(f"获取 token 失败：{out[:300]}")
    return data["access_token"]


def upload_image(token, image_path):
    """上传图片到素材库，返回 (media_id, url)。"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图片不存在：{image_path}")
    out, _ = run(
        f"curl -s -X POST "
        f"'https://api.weixin.qq.com/cgi-bin/material/add_material"
        f"?access_token={token}&type=image' -F 'media=@{image_path}'"
    )
    try:
        data = json.loads(out)
    except Exception:
        raise RuntimeError(f"解析图片上传结果失败：{out[:200]}")
    if "media_id" not in data:
        raise RuntimeError(f"图片上传失败：{out[:300]}")
    return data.get("media_id"), data.get("url", "")


def fit_title(title):
    """微信标题上限 64 字节（约 21 个中文字符），超限按字节截断。"""
    b = title.encode("utf-8")
    if len(b) <= 64:
        return title, False
    # 按字符截断到 <=64 字节
    out = ""
    for ch in title:
        if len((out + ch).encode("utf-8")) > 64:
            break
        out += ch
    return out, True


# ---------- markdown -> 微信内联 HTML ----------
IMG_PLACEHOLDER = "🔳IMGSLOT{}🔳"  # 占位符，上传后替换


def md_to_wechat_html(md, title):
    lines = md.splitlines()
    html_parts = []
    wrapper_open = (
        '<section style="font-family:-apple-system,BlinkMacSystemFont,'
        '\'PingFang SC\',\'Helvetica Neue\',sans-serif;'
        'padding:16px;background:#fff;">'
    )
    html_parts.append(wrapper_open)

    # 顶部重复标题（视觉一致性）
    html_parts.append(
        f'<h1 style="font-size:22px;font-weight:bold;color:#1a1a1a;'
        f'margin:0 0 20px;line-height:1.4;">{title}</h1>'
    )

    img_index = [0]  # 闭包计数

    def esc(t):
        return (t.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))

    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i].rstrip()
        i += 1
        if not ln.strip():
            continue
        # 图片行 ![alt](path)
        m = re.match(r"^!\[(.*?)\]\((.*?)\)\s*$", ln)
        if m:
            img_index[0] += 1
            slot = IMG_PLACEHOLDER.format(img_index[0])
            html_parts.append(slot)
            continue
        # H2
        if ln.startswith("## "):
            text = esc(ln[3:].strip())
            html_parts.append(
                f'<h2 style="font-size:18px;font-weight:bold;color:#1a1a1a;'
                f'border-left:4px solid #09B83E;padding-left:10px;'
                f'margin:28px 0 14px;">{text}</h2>'
            )
            continue
        # 行内图片（少见，保险处理）
        if ln.startswith("# "):
            continue  # 顶部已渲染标题
        # 话题标签行
        if ln.strip().startswith("#") and " " not in ln.strip().split("#")[1]:
            tags = esc(ln.strip())
            html_parts.append(
                f'<p style="font-size:14px;color:#888;margin:24px 0 0;">'
                f'{tags}</p>'
            )
            continue
        # 普通段落（合并连续文本行）
        text = esc(ln)
        html_parts.append(
            f'<p style="font-size:16px;line-height:1.8;color:#333;'
            f'margin:0 0 18px;">{text}</p>'
        )

    html_parts.append("</section>")
    return "\n".join(html_parts)


def build_inline_img(url, alt=""):
    return (
        f'<p style="text-align:center;margin:20px 0;">'
        f'<img src="{url}" alt="{alt}" '
        f'style="max-width:100%;border-radius:6px;'
        f'display:block;margin:0 auto;"></p>'
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--article", required=True)
    ap.add_argument("--cover", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--digest", default="")
    ap.add_argument("--author", default="湘月姐")
    ap.add_argument("--env-file", default="")
    args = ap.parse_args()

    # 加载凭证
    if args.env_file and os.path.exists(args.env_file):
        with open(args.env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")
    appid = os.environ.get("WECHAT_APPID")
    secret = os.environ.get("WECHAT_SECRET")
    if not appid or not secret:
        log("PUB", "缺少 WECHAT_APPID / WECHAT_SECRET（用 --env-file 传入）", "err")
        sys.exit(1)

    md = open(args.article, encoding="utf-8").read()
    title, trimmed = fit_title(args.title)
    if trimmed:
        log("PUB", f"标题超 64 字节已截断为：{title}", "warn")

    # 1. 转 HTML（含占位符）
    html = md_to_wechat_html(md, title)
    slots = re.findall(re.escape(IMG_PLACEHOLDER).format(r"(\d+)"), html)
    slots = [int(s) for s in slots]
    log("PUB", f"检测到正文配图 {len(slots)} 张，准备上传", "info")

    # 2. token
    token = get_token(appid, secret)
    log("PUB", "access_token 获取成功", "ok")

    # 3. 封面上传 -> thumb_media_id
    cover_id, _ = upload_image(token, args.cover)
    log("PUB", f"封面上传完成 media_id={cover_id[:12]}…", "ok")

    # 4. 正文配图上传 -> url，替换占位符
    for slot in slots:
        # 按顺序取封面外的图片：article 内图片在 runs/.../images/final/image-{slot}.png
        img_path = os.path.join(
            os.path.dirname(args.article), "images", "final",
            f"image-{slot}.png"
        )
        if not os.path.exists(img_path):
            # 回退：尝试绝对路径推测
            img_path = os.path.join(
                os.path.dirname(os.path.dirname(args.article)),
                "images", "final", f"image-{slot}.png"
            )
        if not os.path.exists(img_path):
            log("PUB", f"找不到配图 {slot}：{img_path}", "err")
            sys.exit(1)
        _, url = upload_image(token, img_path)
        if not url:
            log("PUB", f"配图 {slot} 未返回 url，跳过", "err")
            sys.exit(1)
        html = html.replace(IMG_PLACEHOLDER.format(slot), build_inline_img(url))
        log("PUB", f"配图 {slot} 上传完成并嵌入", "ok")

    # 5. 建草稿
    digest = args.digest or title
    draft = {
        "articles": [{
            "title": title,
            "author": args.author,
            "digest": digest,
            "content": html,
            "thumb_media_id": cover_id,
            "need_open_comment": 1,
            "only_fans_can_comment": 0,
        }]
    }
    draft_path = os.path.join(tempfile.gettempdir(),
                              f"draft_{os.getpid()}.json")
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False)

    out, _ = run(
        f"curl -s -X POST "
        f"'https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}'"
        f" -H 'Content-Type: application/json' -d @{draft_path}"
    )
    try:
        data = json.loads(out)
    except Exception:
        raise RuntimeError(f"解析建草稿结果失败：{out[:200]}")
    os.remove(draft_path)

    media_id = data.get("media_id")
    if not media_id:
        log("PUB", f"建草稿失败：{out[:300]}", "err")
        sys.exit(1)

    log("PUB", "草稿发布成功！", "ok")
    print(f"\n📝 文章信息")
    print(f"  标题：{title}")
    print(f"  摘要：{digest}")
    print(f"  草稿 media_id：{media_id}")
    print(f"\n📌 前往公众号后台查看并发布：")
    print(f"   https://mp.weixin.qq.com （登录后 → 内容管理 → 草稿箱）")


if __name__ == "__main__":
    main()
