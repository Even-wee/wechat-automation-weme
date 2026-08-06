"""D3 · 写前定义：从选题生成文章任务书 brief.yaml。

任务书解决"拿到选题直接写"的问题——先想清楚：
  给谁看 / 说什么核心判断 / 反方是什么 / 边界在哪 / 多少字 / 什么框架。

无 LLM 时用规则模板生成（基于选题标题 + DNA persona + config.writing.mode_default）。
设 WEWRITE_LLM=1 时可由 LLM 生成更细的判断句。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import load_config, load_dna, log, write_text, load_user_config

# 框架推断
FRAMEWORK_MAP = [
    ("监管", "热点解读"),
    ("新规", "热点解读"),
    ("处罚", "案例复盘"),
    ("避坑", "实操指南"),
    ("方法", "方法论"),
    ("案例", "案例复盘"),
    ("复盘", "案例复盘"),
    ("指南", "实操指南"),
]

# 通用版：读者/边界从用户 identity.yaml 读，回退通用默认
def _reader() -> str:
    ident = load_user_config("identity")
    aud = ident.get("primary_audience", [])
    if aud:
        return "、".join(aud[:3]) if isinstance(aud, list) else str(aud)
    return "你的目标读者（identity.yaml 中填写）"


def _boundary() -> str:
    ident = load_user_config("identity")
    fb = ident.get("forbidden", [])
    if fb:
        return "；".join(str(x) for x in fb[:3]) if isinstance(fb, list) else str(fb)
    return "不编造案例，不夸大效果，数据须有出处"


def _account_positioning() -> str:
    ident = load_user_config("identity")
    pos = ident.get("account_positioning", "")
    return pos if pos else "你的账号定位"


def infer_framework(title: str) -> str:
    for kw, fw in FRAMEWORK_MAP:
        if kw in title:
            return fw
    return "观点输出"


def infer_core_question(title: str) -> str:
    # 去掉标点，构造一个问题（读者关系前缀从 identity 读）
    t = re.sub(r"[：:，,。.!！?？]+", " ", title).strip()
    return f"「{t}」到底跟{_account_positioning()}有什么关系？"


def generate_brief(topic: dict, mode: str = "professor") -> dict:
    title = topic.get("title", "")
    framework = infer_framework(title)
    brief = {
        "reader": _reader(),
        "core_question": infer_core_question(title),
        "core_judgment": "做好基本功，是建立长期信任的杠杆",
        "counter_argument": "门槛这么高，普通人怎么开始？",
        "boundary": _boundary(),
        "word_count": "1500-2500",
        "framework": framework,
        "persona": "warm-editor",
        "mode": mode,
        "topic_title": title,
    }
    return brief


def run(topic: dict, run_dir: Path, mode: str | None = None) -> Path:
    config = load_config()
    mode = mode or config.get("writing", {}).get("mode_default", "professor")
    dna = load_dna()
    brief = generate_brief(topic, mode)
    # 把 DNA 关键句式注入 brief，供写作引擎参考
    brief["sentence_patterns"] = [p.get("form") for p in dna.get("syntax_patterns", []) if isinstance(p, dict)]
    out = run_dir / "brief.yaml"

    # 写成可读 yaml
    import yaml
    write_text(out, yaml.safe_dump(brief, allow_unicode=True, sort_keys=False))
    log("D3", f"任务书生成：{out}（框架={brief['framework']}，模式={mode}）", "ok")
    return out


if __name__ == "__main__":
    from topic_scorer import run as score_run
    top5 = score_run(out_path=Path(__file__).resolve().parent / "sample" / "topics_top5.json")
    b = generate_brief(top5[0])
    import yaml
    print(yaml.safe_dump(b, allow_unicode=True, sort_keys=False))
