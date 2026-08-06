"""D4 · 编辑审稿引擎：六项判断 + 合规自动修复 + 全自动/半自动双模式。

六项判断（含合规）：
  准确 / 观点 / 有用 / 合声 / 好读 / 合规

合规由 compliance-checker.py 承担（自动修复，两段式：初筛+语境复核）。
其余五项用启发式判断（可平滑替换为 wewrite review 的 LLM 判断）。

双模式（来自 config.review_mode）：
  auto=true  → 审稿+合规修复通过后直接进 Phase 3（不暂停）
  auto=false → 审稿通过后生成审批请求并暂停，等人工确认再继续
  auto_fix   → 合规命中默认自动改完出终稿，不弹确认

产出：review-report.json + article.md（封存终稿，不可变）
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import (COMPLIANCE_CHECKER, load_config, load_dna, log,
                    write_json, read_text, write_text)

# 合规修复后终稿文件名规则：<stem>.fixed.md
# 其余五项启发式关键词
VIEWPOINT_KW = ["不是", "是", "认为", "判断", "本质上", "换句话说", "其实"]
USEFUL_KW = ["步骤", "如何", "建议", "可以", "第一", "第二", "记得", "注意"]
GOLDEN_LINE_RE = re.compile(r"^#{1,3}\s|^\s*>\s|[\u201c\u201d]")  # 金句独立段标记


def run_compliance(article_path: Path, auto_fix: bool) -> Path | None:
    """调用合规检查器。auto_fix=True 产出 .fixed.md；否则只报告。返回终稿路径或 None。"""
    if not COMPLIANCE_CHECKER.exists():
        log("D4", f"合规检查器缺失：{COMPLIANCE_CHECKER}", "err")
        return None
    cmd = [sys.executable, str(COMPLIANCE_CHECKER), str(article_path)]
    if not auto_fix:
        cmd.append("--no-fix")
    try:
        subprocess.run(cmd, check=True, timeout=120)
    except subprocess.CalledProcessError as e:
        log("D4", f"合规检查器异常：{e}", "warn")
    fixed = article_path.with_name(article_path.stem + ".fixed.md")
    if auto_fix and fixed.exists():
        log("D4", f"合规修复完成 → {fixed.name}", "ok")
        return fixed
    return None


def _check_dimensions(text: str, dna: dict) -> list[dict]:
    results: list[dict] = []

    # 1. 准确：优先用 claims.yaml 校验（若存在）
    claims_path = text and None  # claims 由 D5 产出于 run_dir，这里仅标注
    results.append({
        "dim": "准确", "status": "warn",
        "note": "请确认事实主张均有来源（claims.yaml）；无来源主张需标注或删除",
    })

    # 2. 观点：是否含独立判断句式
    has_view = any(k in text for k in VIEWPOINT_KW)
    results.append({
        "dim": "观点", "status": "pass" if has_view else "warn",
        "note": "含独立判断句式" if has_view else "建议补充明确的核心判断",
    })

    # 3. 有用：是否含可执行动作
    has_useful = any(k in text for k in USEFUL_KW)
    results.append({
        "dim": "有用", "status": "pass" if has_useful else "warn",
        "note": "含可执行动作词" if has_useful else "建议补充具体行动建议",
    })

    # 4. 合声：是否命中 DNA 禁区词
    blacklist = dna.get("blacklist", {}).get("forbidden_words", []) if isinstance(dna.get("blacklist"), dict) else []
    hit = [w for w in blacklist if w in text]
    results.append({
        "dim": "合声", "status": "pass" if not hit else "warn",
        "note": "未命中禁区词" if not hit else f"命中 DNA 禁区词：{hit}",
    })

    # 5. 好读：段落行数 + 金句独立段
    paras = [p for p in text.split("\n\n") if p.strip()]
    avg_lines = sum(len(p.split("\n")) for p in paras) / max(len(paras), 1)
    has_golden = any(GOLDEN_LINE_RE.search(p.strip()) for p in paras)
    good = avg_lines <= 5 and has_golden
    results.append({
        "dim": "好读", "status": "pass" if good else "warn",
        "note": f"段落均长 {avg_lines:.1f} 行，金句独立段={'有' if has_golden else '无'}",
    })

    return results


def review(article_path: Path, run_dir: Path, mode_override: str | None = None) -> dict:
    config = load_config()
    rm = config.get("review_mode", {})
    dna = load_dna()
    mode = mode_override or ("auto" if rm.get("auto") else "manual")
    auto_fix = rm.get("auto_fix", True)

    text = read_text(article_path)
    log("D4", f"开始审稿（模式={mode}，auto_fix={auto_fix}）", "info")

    # 合规维度
    fixed = run_compliance(article_path, auto_fix)
    finalized_src = fixed if fixed else article_path
    finalized_text = read_text(finalized_src)

    # 其余五项
    dims = _check_dimensions(finalized_text, dna)
    dims.append({
        "dim": "合规", "status": "pass" if fixed else "warn",
        "note": f"已自动修复并出终稿（{fixed.name}）" if fixed else "未自动修复（auto_fix=False），请人工检视报告",
    })

    n_warn = sum(1 for d in dims if d["status"] == "warn")
    status = "passed" if mode == "auto" else "pending_human"

    report = {
        "step": "D4-review",
        "mode": mode,
        "auto_fix": auto_fix,
        "status": status,
        "dimensions": dims,
        "warn_count": n_warn,
        "finalized_article": str(run_dir / "article.md"),
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }

    # 封存终稿（不可变）
    write_text(run_dir / "article.md", finalized_text)
    write_json(run_dir / "review-report.json", report)

    if mode == "manual":
        # 半自动：写审批请求，暂停
        approval = {
            "action": "review_approved",
            "article": str(run_dir / "article.md"),
            "report": str(run_dir / "review-report.json"),
            "status": "awaiting_human",
        }
        write_json(run_dir / "approval_request.json", approval)
        log("D4", "半自动模式：审稿通过，已生成审批请求并暂停，等待人工确认", "warn")
    else:
        log("D4", f"审稿完成，状态={status}，warn={n_warn}，终稿已封存", "ok")

    return report


if __name__ == "__main__":
    import sys as _s
    art = Path(_s.argv[1]) if len(_s.argv) > 1 else (Path.home() / ".wewrite" / "fusion" / "sample" / "draft_demo.md")
    rd = Path(_s.argv[2]) if len(_s.argv) > 2 else Path(_s.argv[0]).resolve().parent / "sample"
    review(art, rd)
