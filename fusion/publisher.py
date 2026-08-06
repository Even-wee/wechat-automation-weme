"""D7 · 发布适配器：Playwright 发布到公众号 + 飞书内容库记录。

真实环境：PLAYWRIGHT 可用 + 公众号登录态 → 自动填标题/正文/封面并发布/存草稿。
无 session（默认）：stub 写发布日志 + 飞书内容库记录，保证闭环可跑。

publisher.publish(html_path, run_dir, config, use_real=False)
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from common import load_config, log
from feishu_adapter import push_content_log


def _publish_real(html_path: Path, title: str) -> str:
    """真实 Playwright 发布（TODO：凭证/session 就绪后实现）。"""
    raise NotImplementedError("Playwright 真实发布待接入公众号登录态")


def publish(html_path: Path, run_dir: Path, title: str, use_real: bool = False) -> dict:
    config = load_config()
    record = {
        "title": title,
        "html": str(html_path),
        "published_at": datetime.now().isoformat(),
        "engine": "wewrite_preview + playwright",
        "status": "published" if use_real else "stub_logged",
    }

    if use_real:
        try:
            url = _publish_real(html_path, title)
            record["url"] = url
            log("D7", f"已发布：{url}", "ok")
        except NotImplementedError:
            log("D7", "Playwright 真实发布未实现，落 stub 日志", "warn")
    else:
        log("D7", f"发布记录（stub）：{title}", "info")

    # 飞书内容库记录
    if config.get("publish", {}).get("feishu_log", True):
        push_content_log(record, use_real=False)

    # 本地发布日志
    from common import write_json
    write_json(run_dir / "publish_record.json", record)
    return record
