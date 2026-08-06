"""D3/D4 · 写作引擎封装：调用 WeWrite 写初稿，无源素材时走 stub。

真实环境：
  wewrite run start --topic "标题" --brief brief.yaml
  wewrite run step  --action write
  → 产出 draft.md（含 warm-editor 人格 + DNA few-shot + 安全增强）

默认（无 wewrite 源素材 / CLI 不可达）：stub 复制传入的草稿，或生成 4+1 骨架占位。

writer.write_draft(brief_path, run_dir, draft_input=None, try_wewrite=True)
  draft_input: 已写好的草稿路径（模拟 wewrite 产出），直接采用
  返回: draft.md 路径
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from common import load_config, log

WEWRITE_BIN = "wewrite"


def _wewrite_available() -> bool:
    try:
        subprocess.run([WEWRITE_BIN, "--version"], capture_output=True, timeout=10)
        return True
    except Exception:  # noqa: BLE001
        return False


def _stub_skeleton(brief_path: Path, run_dir: Path) -> Path:
    """无源素材时生成 4+1 骨架占位，标明由 wewrite 填充。"""
    import yaml
    brief = yaml.safe_load(brief_path.read_text(encoding="utf-8")) or {}
    title = brief.get("topic_title", "未命名选题")
    skeleton = f"""# {title}

> [本稿由 writer 骨架占位生成；真实环境由 wewrite write 填充正文]

## 标题钩子
[数字 / 反差 / 问题，三选一]

## 白话解释
[1-2 句让小白也懂]

## 金句段
[排比 / 对比 / 反直觉]

## 实操动作
1. [具体可执行步骤]
2. [具体可执行步骤]

## 情感升华 / CTA
[建议点赞收藏]
"""
    out = run_dir / "draft.md"
    out.write_text(skeleton, encoding="utf-8")
    return out


def write_draft(brief_path: Path, run_dir: Path, draft_input: str | None = None,
                try_wewrite: bool = True) -> Path:
    out = run_dir / "draft.md"

    # 1) 直接采用已写好的草稿（模拟 wewrite 产出 / 测试用真实稿）
    if draft_input and Path(draft_input).exists():
        shutil.copy(Path(draft_input), out)
        log("D3", f"采用已写草稿：{draft_input}", "ok")
        return out

    # 2) 真实调用 wewrite CLI
    if try_wewrite and _wewrite_available():
        try:
            topic = _topic_from_brief(brief_path)
            subprocess.run([WEWRITE_BIN, "run", "start", "--topic", topic,
                            "--brief", str(brief_path)], check=True, timeout=120)
            subprocess.run([WEWRITE_BIN, "run", "step", "--action", "write"],
                           check=True, timeout=300)
            # 尝试定位 wewrite 产出的 draft
            cand = _locate_wewrite_draft()
            if cand:
                shutil.copy(cand, out)
                log("D3", f"wewrite 写稿完成：{out}", "ok")
                return out
        except Exception as e:  # noqa: BLE001
            log("D3", f"wewrite 调用失败，回退骨架占位：{e}", "warn")

    # 3) stub 骨架
    sk = _stub_skeleton(brief_path, run_dir)
    log("D3", f"生成骨架占位草稿（stub）：{sk}", "info")
    return sk


def _topic_from_brief(brief_path: Path) -> str:
    import yaml
    b = yaml.safe_load(brief_path.read_text(encoding="utf-8")) or {}
    return b.get("topic_title", "未命名选题")


def _locate_wewrite_draft() -> Path | None:
    base = Path.home() / ".wewrite" / "runs"
    if not base.exists():
        return None
    drafts = sorted(base.rglob("article.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return drafts[0] if drafts else None
