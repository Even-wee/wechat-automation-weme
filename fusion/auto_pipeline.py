"""主编排器：串联 D2→D8，支持全自动/半自动双模式 + 步进执行。

这是用户最终调用的入口（D5 端到端 / D9 全自动 / D10 半自动 共用此文件）。

用法：
  # 全自动：从选题到发布跑通一篇
  python auto_pipeline.py --review-mode auto --draft /path/to/draft.md

  # 半自动：审稿后暂停等人工确认
  python auto_pipeline.py --review-mode manual --draft /path/to/draft.md

  # 指定选题标题
  python auto_pipeline.py --review-mode auto --topic "美食探店避坑指南..."

  # 只跑某步
  python auto_pipeline.py --only D2
  python auto_pipeline.py --from D6 --draft /path/to/article.md

步骤顺序：D2 选题 → D3 任务书+写作 → D5 事实核查 → D4 审稿 → D6 排版 → D7 发布 → D8 复盘
"""
from __future__ import annotations

import argparse
from pathlib import Path

from common import load_config, log, run_dir, write_json

import topic_scorer
import brief_generator
import writer
import fact_check
import review_engine
import layout
import publisher
import stats

STEPS = ["D2", "D3", "D5", "D4", "D6", "D7", "D8"]


def _select_topic(top5: list, topic_title: str | None) -> dict:
    if topic_title:
        for t in top5:
            if topic_title in t.get("title", "") or t.get("title", "") in topic_title:
                return t
        log("D2", f"未匹配到「{topic_title}」，回退 Top1", "warn")
    return top5[0]


def run_pipeline(review_mode: str, draft_input: str | None = None,
                 topic_title: str | None = None, only: str | None = None,
                 start: str = "D2") -> dict:
    rd = run_dir()
    log("PIPE", f"运行目录：{rd}", "info")
    result: dict = {"run_dir": str(rd), "steps": {}}

    topic = None
    # 跳步起点 >= D6 时，后续依赖 rd/article.md（封存终稿）；用传入草稿补足
    import shutil
    if start >= "D6" and draft_input and not (rd / "article.md").exists():
        draft_path = Path(draft_input)
        shutil.copy(draft_path, rd / "article.md")
        log("PIPE", f"--from {start}：以传入草稿作为已封存终稿", "info")
        # 若原草稿所在 run_dir 已有生成好的图片，一并继承
        src_images = draft_path.parent / "images" / "final"
        if src_images.exists():
            dst_images = rd / "images" / "final"
            dst_images.mkdir(parents=True, exist_ok=True)
            for f in src_images.glob("*.png"):
                shutil.copy2(f, dst_images / f.name)
            log("PIPE", f"继承配图：{len(list(dst_images.glob('*.png')))} 张", "info")

    if only == "D2" or start <= "D2":
        top5 = topic_scorer.run(out_path=rd / "topics_top5.json")
        topic = _select_topic(top5, topic_title)
        result["steps"]["D2"] = {"selected": topic.get("title")}
        if only == "D2":
            return result

    if start > "D3":
        log("PIPE", "跳过 D2/D3（--from 指定起点）", "info")
        # 需要至少一个 topic 占位
        topic = {"title": topic_title or "（已有选题）", "track": "美食探店"}

    # D3 任务书 + 写作
    if start <= "D3":
        brief = brief_generator.run(topic, rd)
        draft = writer.write_draft(brief, rd, draft_input=draft_input)
        result["steps"]["D3"] = {"brief": str(brief), "draft": str(draft)}
        if only == "D3":
            return result
    else:
        draft = Path(draft_input) if draft_input else rd / "draft.md"

    # D5 事实核查
    if start <= "D5":
        claims = fact_check.fact_check(draft, rd)
        result["steps"]["D5"] = {"claims": len(claims)}
        if only == "D5":
            return result

    # D4 审稿（双模式）
    if start <= "D4":
        report = review_engine.review(draft, rd, mode_override=review_mode)
        result["steps"]["D4"] = {"status": report["status"], "warn": report["warn_count"]}
        if report["status"] == "pending_human":
            log("PIPE", "⏸ 半自动模式暂停：请确认 approval_request.json 后继续 D6-D8",
                "warn")
            write_json(rd / "pipeline_state.json", {**result, "paused_at": "D4"})
            return result
        if only == "D4":
            return result

    # D6 排版（用封存终稿）
    if start <= "D6":
        html = layout.layout(rd / "article.md", rd)
        result["steps"]["D6"] = {"html": str(html)}
        if only == "D6":
            return result

    # D7 发布
    if start <= "D7":
        rec = publisher.publish(html if "html" in locals() else rd / "preview.html",
                                rd, topic.get("title", ""))
        result["steps"]["D7"] = {"status": rec["status"]}
        if only == "D7":
            return result

    # D8 数据复盘
    if start <= "D8":
        s = stats.backfill(rd, topic)
        result["steps"]["D8"] = {"reads": s["reads"]}
        if only == "D8":
            return result

    log("PIPE", "✅ 全流程跑通（D2→D8）", "ok")
    write_json(rd / "pipeline_state.json", {**result, "done": True})
    return result


def main():
    ap = argparse.ArgumentParser(description="WeWrite 融合流水线（多用户通用）")
    ap.add_argument("--review-mode", choices=["auto", "manual"], default=None,
                    help="审稿双模式；不传则读 config.review_mode.auto")
    ap.add_argument("--draft", help="已写好的草稿路径（模拟 wewrite 产出 / 测试用真实稿）")
    ap.add_argument("--topic", help="指定选题标题（否则取 Top1）")
    ap.add_argument("--only", choices=STEPS, help="只跑某一步")
    ap.add_argument("--from", dest="start", choices=STEPS, default="D2",
                    help="从某步开始")
    args = ap.parse_args()

    # 解析 review_mode 默认值
    if args.review_mode is None:
        cfg = load_config()
        args.review_mode = "auto" if cfg.get("review_mode", {}).get("auto", True) else "manual"

    run_pipeline(args.review_mode, draft_input=args.draft,
                 topic_title=args.topic, only=args.only, start=args.start)


if __name__ == "__main__":
    main()
