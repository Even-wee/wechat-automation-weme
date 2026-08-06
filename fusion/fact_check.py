"""D5 · 事实核查：claims 账本（逐条关联来源，禁止模型记忆充当事实）。

真实环境：wewrite run step --action fact-check → claims.yaml（LLM 提取主张并关联 URL）。
stub：正则提取含数字/法规提及的句子作为 claims 草稿，source 留空待人工/LLM 填。

fact_check(article_path, run_dir) → 产出 claims.json
"""
from __future__ import annotations

import re
from pathlib import Path

from common import log, read_text, write_json


def fact_check(article_path: Path, run_dir: Path, use_real: bool = False) -> list:
    text = read_text(article_path)
    claims: list[dict] = []

    if use_real:
        import subprocess
        try:
            subprocess.run(["wewrite", "run", "step", "--action", "fact-check"],
                           check=True, timeout=180, capture_output=True)
            log("D5", "wewrite fact-check 完成", "ok")
        except Exception as e:  # noqa: BLE001
            log("D5", f"wewrite fact-check 不可用，走 stub：{e}", "warn")

    # stub：提取疑似事实主张
    for line in text.split("\n"):
        s = line.strip()
        if len(s) < 10:
            continue
        if re.search(r"\d", s) and re.search(r"[\u4e00-\u9fff]", s):
            claims.append({"text": s, "source": "", "verified": False,
                           "note": "待关联来源（stub 提取）"})
        elif re.search(r"(法|规|条|处罚|通报|总局|部门)", s):
            claims.append({"text": s, "source": "", "verified": False,
                           "note": "法规/处罚提及，待关联出处"})

    unverified = [c for c in claims if not c["verified"]]
    write_json(run_dir / "claims.json", claims)
    log("D5", f"提取主张 {len(claims)} 条，未验证 {len(unverified)} 条", "ok")
    return claims
