"""D6 · 视觉与排版引擎：先出 AI 配图计划，再调用排版引擎出 HTML。

排版引擎策略（自动选择，零外部依赖优先）：
  1. 内置引擎：直接 import wewrite 包（已装即用，无需 CLI 调用）
  2. wewrite CLI：subprocess 调 `wewrite preview`（兼容旧用法）
  3. stub 极简 HTML：以上都失败时兜底

真实环境：
  1. 调用 image_gen.plan 生成封面 + 内文配图请求（image_requests.json）。
  2. Agent 按请求调用 ImageGen，把图片放到 run_dir/images/final/。
  3. layout.py 检测到图片已存在，自动嵌入 article.md，再调排版引擎出 HTML。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from common import load_config, log, read_text
import image_gen

WEWRITE_BIN = "wewrite"
DEFAULT_THEMES_FALLBACK = "warm-editorial"


def _try_internal_converter():
    """尝试导入 wewrite 包的内部 converter（无 CLI 调用）。

    Returns:
        (WeChatConverter, theme_names) 或 (None, [])。
    """
    try:
        from wewrite.toolkit.converter import WeChatConverter
        from wewrite.toolkit.theme import _theme_search_dirs
        theme_dirs = _theme_search_dirs()
        themes = []
        for d in theme_dirs:
            if d and d.exists():
                themes.extend([p.stem for p in d.glob("*.yaml")])
        return WeChatConverter, sorted(set(themes))
    except Exception as e:  # noqa: BLE001
        log("D6", f"内置 converter 不可用：{e}", "info")
        return None, []


def layout(article_path: Path, run_dir: Path, theme: str | None = None) -> Path:
    config = load_config()
    theme = theme or config.get("publish", {}).get("theme", DEFAULT_THEMES_FALLBACK)
    out = run_dir / "preview.html"

    # 1) AI 配图计划：生成 image_requests.json 并尝试嵌入已生成图片
    try:
        prepared_article = image_gen.plan(article_path, run_dir)
        if prepared_article != article_path:
            article_path = prepared_article
            log("D6", "使用带图片占位符的文章继续排版", "info")
    except Exception as e:  # noqa: BLE001
        log("D6", f"图片计划生成失败，继续排版原文：{e}", "warn")

    # 2) 优先尝试内置 converter（导入 wewrite 包的内部模块）
    WCC, themes = _try_internal_converter()
    if WCC and (not themes or theme in themes):
        try:
            md_text = read_text(article_path)
            conv = WCC(theme_name=theme)
            result = conv.convert(md_text)
            html = result.html if hasattr(result, "html") else str(result)
            out.write_text(html, encoding="utf-8")
            log("D6", f"内置 converter 排版完成（{theme}）：{out}", "ok")
            return out
        except Exception as e:  # noqa: BLE001
            log("D6", f"内置 converter 调用失败，回退 CLI：{e}", "warn")

    # 3) 回退：subprocess 调 wewrite CLI
    try:
        subprocess.run([WEWRITE_BIN, "preview", str(article_path),
                        "--theme", theme, "--output", str(out)],
                       check=True, timeout=120, capture_output=True)
        if out.exists():
            log("D6", f"wewrite CLI 排版完成（{theme}）：{out}", "ok")
            return out
    except Exception as e:  # noqa: BLE001
        log("D6", f"wewrite CLI 不可用，回退极简 HTML：{e}", "warn")

    # 4) stub 极简包裹
    md = read_text(article_path)
    html = _md_to_html(md, run_dir)
    out.write_text(html, encoding="utf-8")
    log("D6", f"极简 HTML 包裹（stub）：{out}", "info")
    return out


def _md_to_html(md: str, run_dir: Path) -> str:
    import html as _html
    import re

    # 把 markdown 图片转成 <img>
    def img_repl(m: re.Match) -> str:
        alt, src = m.group(1), m.group(2)
        # 如果是相对路径，从 run_dir 找
        p = Path(src)
        if not p.is_absolute():
            p = run_dir / "images" / "final" / src
        src_str = str(p) if p.exists() else src
        return f'<img alt="{_html.escape(alt)}" src="{_html.escape(src_str)}" style="max-width:100%;border-radius:8px;margin:16px 0">'

    md = re.sub(r"!\[(.*?)\]\((.*?)\)", img_repl, md)

    lines = md.split("\n")
    body = []
    for ln in lines:
        if ln.startswith("# "):
            body.append(f"<h1>{_html.escape(ln[2:])}</h1>")
        elif ln.startswith("## "):
            body.append(f"<h2>{_html.escape(ln[3:])}</h2>")
        elif ln.startswith("### "):
            body.append(f"<h3>{_html.escape(ln[4:])}</h3>")
        elif ln.strip():
            body.append(f"<p>{_html.escape(ln)}</p>")
    return ("<!DOCTYPE html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<style>body{max-width:680px;margin:0 auto;padding:16px;font-family:-apple-system,sans-serif;line-height:1.8;color:#222}</style>"
            f"</head><body>{''.join(body)}</body></html>")
