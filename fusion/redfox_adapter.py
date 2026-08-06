"""红狐 API 选题采集适配器。

真实环境：REDZFox API 凭证通过环境变量 REDFOX_API_KEY / REDFOX_ENDPOINT 提供，
调用真实接口返回 Top20 候选。
无凭证（默认）：从本地 sample/topics.json 读取示例候选，保证链路可端到端测试。

两种模式对外暴露同一函数 `fetch_topics()`，返回统一结构：
[
  {"title": "...", "hot": 0.82, "keywords": [...], "track": "美食探店",
   "source": "示例", "url": "..."},
  ...
]
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from common import WEWRITE_HOME, log, read_json, load_user_config, SAMPLE_TOPICS

SAMPLE = SAMPLE_TOPICS

# 通用兜底关键词：仅在旧版回退模式（无多用户配置）且 topics.yaml 完全缺失时使用。
# 多用户模式（通用版）已由 require_user_config 严格拦截，不会走到这里。
DEFAULT_TRACK_KEYWORDS = [
    "方法", "案例", "实操", "复盘", "指南", "避坑",
    "效率", "工具", "技巧", "经验", "总结", "清单",
]


def _load_track_keywords() -> list:
    """从用户 topics.yaml 提取所有赛道关键词；无则用通用兜底。"""
    topics = load_user_config("topics")
    tracks = topics.get("tracks", {})
    kws: list[str] = []
    for t in tracks.values():
        if isinstance(t, dict):
            kws.extend(t.get("keywords", []))
    return kws or DEFAULT_TRACK_KEYWORDS


def _coarse_filter(topics: list, track_keywords: list) -> list:
    """按赛道关键词粗筛——先捞后筛的「筛」前置到这里，降低噪声。
    命中规则：title + keywords 任一关键词命中即保留（不放宽也不漏爆款）。
    """
    if not track_keywords:
        return topics

    kept, dropped = [], 0
    for t in topics:
        blob = (t.get("title", "") + " " + " ".join(t.get("keywords", []))).lower()
        if any(kw.lower() in blob for kw in track_keywords):
            kept.append(t)
        else:
            dropped += 1
    log("D2", f"赛道粗筛：保留 {len(kept)} 条，过滤 {dropped} 条噪声", "ok")
    return kept


def _fetch_real(track_keywords: list | None = None) -> list:
    """调用真实红狐 API（需 REDFOX_API_KEY / REDFOX_ENDPOINT）。
    支持把赛道关键词作为 query 参数传给红狐，让 API 端先做一次过滤。
    """
    endpoint = os.environ.get("REDFOX_ENDPOINT")
    key = os.environ.get("REDFOX_API_KEY")
    headers = {"Authorization": f"Bearer {key}"}
    if track_keywords:
        # 大多数热点 API 支持 keywords/categories query
        from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
        u = urlparse(endpoint)
        qs = parse_qs(u.query)
        qs["keywords"] = track_keywords
        endpoint = urlunparse((u.scheme, u.netloc, u.path, u.params,
                               urlencode(qs, doseq=True), u.fragment))
        log("D2", f"红狐 API 按赛道关键词过滤：{track_keywords}", "info")
    req = urllib.request.Request(endpoint, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8")).get("topics", [])


def fetch_topics(use_real: bool = False,
                 track_keywords: list | None = None,
                 coarse_filter_enabled: bool = True) -> list:
    """采集候选选题。

    Args:
        use_real: True 走真实红狐 API，否则读本地示例 stub。
        track_keywords: 赛道关键词列表，传入后会：
                       1) 作为 query 参数传给红狐 API（API 端先筛）
                       2) 返回结果再本地粗筛一遍（兜底）
        coarse_filter_enabled: 是否启用本地粗筛（关闭则全量返回）。

    Returns:
        候选选题列表（按热度倒序），每条带 track_keywords 命中标记。
    """
    kws = track_keywords or _load_track_keywords()

    if use_real and os.environ.get("REDFOX_API_KEY"):
        try:
            topics = _fetch_real(kws)
            log("D2", f"红狐 API 返回 {len(topics)} 条候选", "ok")
            return _coarse_filter(topics, kws) if coarse_filter_enabled else topics
        except Exception as e:  # noqa: BLE001
            log("D2", f"红狐 API 调用失败，回退示例数据：{e}", "warn")
    # stub：本地示例
    topics = read_json(SAMPLE)
    log("D2", f"读取本地示例候选 {len(topics)} 条（stub）", "info")
    return _coarse_filter(topics, kws) if coarse_filter_enabled else topics
