"""D6-AI · 图片生成计划：为文章生成封面 + 内文配图请求。

当前实现：
  - 读取 article.md，提取标题、主题、关键章节。
  - 生成 image_requests.json（含封面 + 3 张内文配图的 prompt / 尺寸 / 输出路径）。
  - 生成 article_with_images.md：在关键章节插入图片占位符。
  - 如果 final/ 目录已存在生成好的图片，直接插入真实路径。

ImageGen 是 Agent 级工具，Python 脚本无法直接调用。因此：
  - 脚本负责产出「图片生成需求清单」和「带占位符的文章」。
  - Agent 读取 image_requests.json，调用 ImageGen 生成图片到 final/。
  - 再次运行 layout.py 时，自动检测到 final/ 图片并嵌入真实路径。

若后续接本地 Stable Diffusion / Replicate / 其他 HTTP API，可把 plan()
扩展为 generate() 直接出图。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from common import log, read_text, write_text, write_json, load_user_config

STYLE_PREFIX = (
    "Warm minimalist editorial illustration, muted earth tones "
    "(terracotta, sage green, cream), soft golden-hour lighting, "
    "clean vector-like illustration style, no text, no logos, "
    "emotional and trustworthy mood. "
)


def _style_prefix() -> str:
    """通用版：优先读用户 style.yaml 的 image_style.prompt_prefix。"""
    style = load_user_config("style")
    img = style.get("image_style", {}) if isinstance(style, dict) else {}
    prefix = img.get("prompt_prefix")
    return prefix if prefix else STYLE_PREFIX


def _image_sizes() -> tuple[str, str]:
    style = load_user_config("style")
    img = style.get("image_style", {}) if isinstance(style, dict) else {}
    return (img.get("cover_size", "1175x500"), img.get("inline_size", "1024x1024"))


def _extract_title(md: str) -> str:
    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    return m.group(1).strip() if m else "文章配图"


def _extract_sections(md: str) -> list[dict]:
    """提取二级标题作为配图锚点。"""
    sections = []
    for m in re.finditer(r"^##\s+(.+)$", md, re.MULTILINE):
        sections.append({"title": m.group(1).strip(), "pos": m.start()})
    return sections


def _slug(title: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "-", title).strip("-")[:40]


def plan(article_path: Path, run_dir: Path) -> Path:
    """生成图片生成计划，并在文章中插入占位符（幂等：多次运行不会重复插入）。"""
    md = read_text(article_path)

    # 先剥离已有图片引用，得到 bare 原文，避免重复插入
    bare = re.sub(r"\n*!\[.*?\]\(.*?\)\n*", "\n", md)
    bare = re.sub(r"\n{3,}", "\n\n", bare).strip() + "\n"
    bare_path = run_dir / "article.bare.md"
    write_text(bare_path, bare)

    title = _extract_title(bare)
    sections = _extract_sections(bare)

    # 按固定主题选择 3 个配图锚点，确保图片内容与章节对齐：
    # image-1 -> 资质证照，image-2 -> 品控/货不对板，image-3 -> 售后/服务
    theme_patterns = [
        ("资质", "证照", "许可证"),
        ("品控", "货不对板", "质量", "退货"),
        ("售后", "出事", "装死", "赔偿", "服务"),
    ]
    selected: list[dict] = []
    used_titles = set()
    for patterns in theme_patterns:
        for sec in sections:
            title = sec["title"]
            if title in used_titles:
                continue
            if any(p in title for p in patterns):
                selected.append(sec)
                used_titles.add(title)
                break
    # 若固定主题未凑齐 3 个，用剩余靠前的章节补齐
    for sec in sections:
        if len(selected) >= 3:
            break
        if sec["title"] not in used_titles:
            selected.append(sec)
            used_titles.add(sec["title"])

    final_dir = run_dir / "images" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    # 如果当前 run_dir 没有图片，尝试从原 article 所在目录的 images/final/ 继承
    src_final = article_path.parent / "images" / "final"
    if src_final.exists() and src_final != final_dir:
        for f in src_final.glob("*.png"):
            dst = final_dir / f.name
            if not dst.exists():
                import shutil
                shutil.copy2(f, dst)
                log("D6-AI", f"从原目录继承图片：{f.name}", "info")

    requests = []
    prefix = _style_prefix()
    cover_size, inline_size = _image_sizes()
    cover_w, cover_h = (int(x) for x in cover_size.split("x"))
    in_w, in_h = (int(x) for x in inline_size.split("x"))
    # 封面
    cover_path = final_dir / "cover.png"
    requests.append({
        "role": "cover",
        "filename": "cover.png",
        "size": f"{cover_w}x{cover_h}",
        "target_size": [cover_w, cover_h],
        "aspect": f"{cover_w / cover_h:.2f}:1",
        "prompt": (
            f"{prefix}Wide banner illustration for WeChat official account cover, "
            f"aspect ratio {cover_w / cover_h:.2f}:1, generous negative space for "
            f"headline overlay. Article theme: {title}."
        ),
        "output": str(cover_path),
    })

    # 内文配图（固定命名，方便 Agent 与脚本对齐）
    for i, sec in enumerate(selected, 1):
        fname = f"image-{i}.png"
        img_path = final_dir / fname
        requests.append({
            "role": "inline",
            "anchor": sec["title"],
            "filename": fname,
            "size": f"{in_w}x{in_h}",
            "prompt": (
                f"{prefix}Scene about \"{sec['title']}\" for an article titled "
                f"\"{title}\". Show authentic real-life details, warm interaction, "
                f"or honest business practice. No text, no logos."
            ),
            "output": str(img_path),
        })

    # 保存请求清单
    req_path = run_dir / "image_requests.json"
    write_json(req_path, requests)
    log("D6-AI", f"图片生成计划已写入：{req_path}（{len(requests)} 张）", "ok")

    # 生成带占位符/真实路径的文章
    use_real = all(Path(r["output"]).exists() for r in requests)
    img_article = _insert_placeholders(bare, requests, use_real=use_real)
    img_article_path = run_dir / "article_with_images.md"
    write_text(img_article_path, img_article)

    if use_real:
        article_path.write_text(img_article, encoding="utf-8")
        log("D6-AI", f"检测到已生成图片，已嵌入真实路径：{article_path}", "ok")
    else:
        log("D6-AI", f"图片尚未生成，占位文章：{img_article_path}", "warn")

    return article_path if use_real else img_article_path


def _insert_placeholders(md: str, requests: list[dict], use_real: bool = False) -> str:
    """在对应二级标题后插入图片引用，每个标题只插入一次。"""
    lines = md.splitlines()
    out: list[str] = []
    inline_map = {r["anchor"]: r for r in requests if r.get("role") == "inline"}
    for ln in lines:
        out.append(ln)
        if ln.startswith("## "):
            title = ln.lstrip("# ").strip()
            if title in inline_map:
                r = inline_map[title]
                path = r["output"] if use_real else r["filename"]
                out.append("")
                out.append(f"![{title}]({path})")
                out.append("")
    return "\n".join(out)


def generate_stub(run_dir: Path) -> list[Path]:
    """无真实 API 时的占位：复制默认占位图或返回空列表。"""
    log("D6-AI", "未接入本地图片 API，跳过自动生成。请由 Agent 按 image_requests.json 调用 ImageGen。", "warn")
    return []


if __name__ == "__main__":
    import sys
    rd = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    article = rd / "article.md"
    plan(article, rd)
