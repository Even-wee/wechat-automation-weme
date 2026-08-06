"""飞书多维表格适配器。

真实环境：FEISHU_APP_ID / FEISHU_APP_SECRET 提供凭证，调用飞书 API
写入/更新多维表格（选题库、内容库）。
无凭证（默认）：把数据写回本地 JSON（~/.wewrite/fusion/.feishu_stub/），
保证链路可测试，真实迁移时只需实现 _push_real。

统一结构：
- push_topics(top5): 写回选题库（新增 wewrite_score 等字段）
- push_content_log(record): 写回内容库（发布后记录）
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from common import WEWRITE_HOME, log, write_json, read_json

STUB_DIR = WEWRITE_HOME / "fusion" / ".feishu_stub"


def _push_real(table: str, rows: list) -> None:
    """真实飞书写入（TODO：凭证就绪后实现 lark-cli 调用）。"""
    raise NotImplementedError("飞书真实写入待接入 lark-cli")


def push_topics(top5: list, use_real: bool = False) -> None:
    if use_real:
        try:
            _push_real("选题库", top5)
            log("D2", "Top5 已写入飞书选题库", "ok")
            return
        except NotImplementedError:
            log("D2", "飞书真实写入未实现，落本地 stub", "warn")
    out = STUB_DIR / "topics_top5.json"
    write_json(out, top5)
    log("D2", f"Top5 写入本地 stub：{out}", "info")


def push_content_log(record: dict, use_real: bool = False) -> None:
    if use_real:
        try:
            _push_real("内容库", [record])
            log("D9", "发布记录已写飞书内容库", "ok")
            return
        except NotImplementedError:
            log("D9", "飞书真实写入未实现，落本地 stub", "warn")
    out = STUB_DIR / "content_log.json"
    logs = read_json(out)
    if not isinstance(logs, list):
        logs = []
    logs.append(record)
    write_json(out, logs)
    log("D9", f"发布记录写本地 stub：{out}", "info")
