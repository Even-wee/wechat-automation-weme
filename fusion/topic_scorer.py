"""D2 · 选题评分：红狐采集（赛道粗筛）→ WeWrite 评分 → Top5。

评分维度（权重来自 config.topic_scoring.weights）：
  track_match 赛道匹配度 / seo_value SEO价值 / timeliness 时效性
  dedup 历史去重 / account_fit 账号匹配

双保险流程：
  1) fetch_topics 已按 track_keywords 粗筛（采集端先捞后筛）
  2) score_topic 再做 5 维加权精评（评分端）

无 LLM 环境用启发式打分（关键词命中 + 热度 + 时间词），可读 config 权重。
如需语义级评分，设 WEWRITE_LLM=1 时调用 wewrite topic score（若存在）。

输出：Top5 评分排序 → 写回飞书（stub 落本地）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common import load_config, load_history, log, stamp, write_json, load_user_config
from redfox_adapter import fetch_topics, _load_track_keywords
from feishu_adapter import push_topics

# 通用版：赛道命中词从用户 topics.yaml 动态生成（回退通用默认）
def _track_kw() -> list:
    kws = _load_track_keywords()
    return kws or ["方法", "案例", "实操", "复盘", "指南", "效率", "工具", "技巧", "经验"]

def _account_kw() -> list:
    """账号匹配词：用户 topics.yaml 的赛道名 + 通用人设词。"""
    topics = load_user_config("topics")
    names: list[str] = []
    for t in topics.get("tracks", {}).values():
        if isinstance(t, dict) and t.get("name"):
            names.append(str(t["name"]))
    return names + ["方法", "案例", "实操", "避坑", "复盘", "干货", "教程",
                    "新手", "指南", "经验", "流程", "清单"]

TRACK_KW = _track_kw()
ACCOUNT_KW = _account_kw()
# 时效词
TIME_KW = ["最新", "2026", "今年", "今日", "刚刚", "近日", "8月", "半年"]


def _hit(text: str, kws: list[str]) -> int:
    return sum(1 for k in kws if k in text)


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def score_topic(t: dict, weights: dict, history_titles: list[str]) -> dict:
    title = t.get("title", "")
    keywords = " ".join(t.get("keywords", []))
    blob = title + " " + keywords

    track = min(1.0, _hit(blob, TRACK_KW) / 2.0)
    account = min(1.0, _hit(blob, ACCOUNT_KW) / 2.0)
    seo = min(1.0, 0.4 + 0.6 * t.get("hot", 0.5))  # 以热度代理 SEO 检索量
    time = min(1.0, 0.3 + 0.7 * _hit(blob, TIME_KW) / 1.5)

    # 去重：与历史标题最大相似度，越低越新鲜
    max_sim = max([_jaccard(title, h) for h in history_titles], default=0.0)
    dedup = 1.0 - max_sim

    total = (track * weights.get("track_match", 0.30)
             + seo * weights.get("seo_value", 0.25)
             + time * weights.get("timeliness", 0.20)
             + dedup * weights.get("dedup", 0.15)
             + account * weights.get("account_fit", 0.10))

    return {
        **t,
        "wewrite_score": round(total, 4),
        "seo_value": round(seo, 4),
        "dedup_score": round(dedup, 4),
        "track_match": round(track, 4),
        "account_fit": round(account, 4),
        "timeliness": round(time, 4),
    }


def run(use_real_redfox: bool = False, out_path: Path | None = None) -> list:
    config = load_config()
    w = config.get("topic_scoring", {}).get("weights", {})
    # 双保险：粗筛（采集端）+ 精评（评分端）
    # redfox_adapter 内部已按 DEFAULT_TRACK_KEYWORDS 做粗筛
    topics = fetch_topics(use_real=use_real_redfox,
                           track_keywords=TRACK_KW,
                           coarse_filter_enabled=True)
    history = load_history()
    history_titles = [str(h.get("title", "")) for h in history.get("articles", [])]

    scored = [score_topic(t, w, history_titles) for t in topics]
    scored.sort(key=lambda x: x["wewrite_score"], reverse=True)
    top5 = scored[:5]

    log("D2", f"已评分 {len(scored)} 条，Top5：")
    for i, t in enumerate(top5, 1):
        log("D2", f"  {i}. [{t['wewrite_score']:.3f}] {t['title']}", "ok")

    push_topics(top5, use_real=False)
    if out_path:
        write_json(out_path, top5)
        log("D2", f"Top5 已落盘：{out_path}", "info")
    return top5


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "sample" / "topics_top5.json"
    run(out_path=out)
