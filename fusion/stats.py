"""D8 · 数据复盘 + 选题反哺闭环。

真实环境：wewrite stats --range 7d 拉取阅读数据。
stub：基于 run 信息生成模拟数据（阅读/点赞/分享），保证闭环可跑。

动作：
  1. 回填 history.yaml（追加已发文章表现）
  2. 反哺下一轮选题评分（把本次赛道表现写入 config 或 history 的 performance 字段）
"""
from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

from common import (HISTORY_PATH, load_config, load_history, log,
                    write_json, write_text)


def _sim_stats() -> dict:
    return {
        "reads": random.randint(2000, 12000),
        "likes": random.randint(80, 600),
        "shares": random.randint(20, 200),
        "comments": random.randint(10, 90),
    }


def backfill(run_dir: Path, topic: dict, use_real: bool = False) -> dict:
    config = load_config()
    stats = _sim_stats() if not use_real else {"reads": 0, "likes": 0, "shares": 0}

    # 1. 回填 history.yaml
    history = load_history()
    articles = history.get("articles", []) if isinstance(history.get("articles"), list) else []
    rec = {
        "title": topic.get("title", ""),
        "published_at": datetime.now().isoformat(),
        "track": topic.get("track", ""),
        "wewrite_score": topic.get("wewrite_score"),
        **stats,
    }
    articles.append(rec)
    history["articles"] = articles
    write_text(HISTORY_PATH, _yaml_dump(history))
    log("D8", f"已回填 history.yaml（共 {len(articles)} 篇）", "ok")

    # 2. 反哺选题评分（赛道表现写入 config 供下轮参考）
    if config.get("analytics", {}).get("feeds_topic_scoring", True):
        perf = config.setdefault("_track_performance", {})
        tr = topic.get("track", "未知")
        perf[tr] = perf.get(tr, 0) + stats["reads"]
        log("D8", f"赛道「{tr}」累计阅读 {perf[tr]}，已反哺下轮选题权重", "info")

    write_json(run_dir / "stats_backfill.json", {"stats": stats, "history_count": len(articles)})
    return stats


def _yaml_dump(d: dict) -> str:
    import yaml
    return yaml.safe_dump(d, allow_unicode=True, sort_keys=False)
