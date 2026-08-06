#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# dna_builder.py — 范文 → 14 维文风 DNA 自动提炼
# ------------------------------------------------------------
# 用法：
#   python dna_builder.py --user alice --samples "/path/to/articles/*.md"
#   python dna_builder.py --user alice --file a.md --file b.md --file c.md
#
# 作用：
#   读取 3-10 篇作者的"历史文章"（他自己写的、无 AI 参与的），
#   量化分析 → 自动生成 style-dna.yaml（14 维文风指纹）。
#
# 原理（范文量化分析）：
#   1. 词汇层：统计高频词 → 提炼个人词库
#   2. 句法层：正则匹配句式模板 → 提炼句式指纹
#   3. 修辞层：开场方式 / 金句独立成段检测
#   4. 节奏层：段落长度 / 句长分布 / 分隔符
#   5. 结构层：章节标题规律
#   6. 语气层：人称代词使用
#   7. 示例层：举例密度
#   8. 结尾层：结尾方式
#   9-14. 高级维度：数字/引用/网络语/修辞/术语/立场
#
# 输出：users/{user}/style-dna.yaml（覆盖模板中的占位内容）
# ============================================================

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from collections import Counter
from pathlib import Path

# ===== 高频功能词（统计个人词库时要过滤掉）=====
STOPWORDS = set("""的了是在我和有就都而及与或一个上也很到说要去你会能可以这那呢吧啊吗
我们你们他们它们自己这个那个什么怎么为什么因为所以但是然后如果就是不是没有
还是就是更最非常特别一些有点真的觉得知道应该可以可能已经正在开始结束时间
东西事情时候现在今天昨天明天这样那样让它帮你你不需要你只需要的时候
不是因为大部分人说真的说难听点太多配图提示" """.split())


def read_articles(sample_patterns: list[str]) -> list[str]:
    """读取所有范文的纯文本。支持 glob 和 --file 两种方式。"""
    texts: list[str] = []
    seen = set()
    for pat in sample_patterns:
        for p in sorted(glob.glob(pat)):
            path = Path(p)
            if path.suffix.lower() in (".md", ".txt", ".markdown") and str(path) not in seen:
                seen.add(str(path))
                texts.append(path.read_text(encoding="utf-8"))
    if not texts:
        print(f"[dna] ✗ 没有读到任何文章，检查路径: {sample_patterns}")
        sys.exit(1)
    return texts


def strip_markdown(text: str) -> str:
    """去掉 markdown 语法，只留正文文字。"""
    text = re.sub(r"^---.*?---", "", text, flags=re.S)          # frontmatter
    text = re.sub(r"!\[.*?\]\(.*?\)", " ", text)                 # 图片
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)         # 链接保留文字
    text = re.sub(r"[#>*`~|]", " ", text)                        # 标记符号
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    """按中文标点切句。"""
    parts = re.split(r"[。！？!?；;\n]", text)
    return [p.strip() for p in parts if len(p.strip()) > 4]


# ================= 1. 词汇层 =================
def analyze_lexicon(texts: list[str], n: int = 15) -> list[str]:
    """统计 2-3 字高频词（避免粘连短语），过滤停用词。"""
    words = Counter()
    for t in texts:
        for w in re.findall(r"[\u4e00-\u9fff]{2,3}", t):
            if w not in STOPWORDS and not w.isdigit():
                words[w] += 1
    return [w for w, _ in words.most_common(n)]


# ================= 2. 句法层 =================
SYNTAX_PATTERNS = [
    (r"不是[^，。]{2,10}，是[^，。]{2,10}", "X，不是 A，是 B"),
    (r"唯有[^，。]{2,12}，才能[^，。]{2,12}", "唯有 A，才能 B"),
    (r"只靠[^，。]{2,12}，[^，。]{2,15}", "只靠 A，B"),
    (r"一旦[^，。]{2,12}，就[^，。]{2,12}", "一旦 A，就 B"),
    (r"先[^，。]{2,10}，再[^，。]{2,10}", "先 A，再 B"),
    (r"只要[^，。]{2,10}，就[^，。]{2,10}", "只要 A，就 B"),
    (r"与其[^，。]{2,10}，不如[^，。]{2,10}", "与其 A，不如 B"),
    (r"越[^，。]{2,8}，越[^，。]{2,8}", "越 A，越 B"),
]


def analyze_syntax(texts: list[str]) -> list[dict]:
    found: list[dict] = []
    counts: Counter = Counter()
    for t in texts:
        for pattern, form in SYNTAX_PATTERNS:
            matches = re.findall(pattern, t)
            if matches:
                counts[form] += len(matches)
                found.append({"form": form, "example": t[:60] + "…"})
    # 只保留出现 >=2 次的句式（真正的指纹）
    return [f for f in found if counts[f["form"]] >= 2][:6] or [{"form": "X，不是 A，是 B", "example": "待补充"}]


# ================= 3. 修辞层 =================
def analyze_openings(texts: list[str]) -> list[str]:
    """开场方式：取每篇前 3 句的开头特征。"""
    styles = Counter()
    for t in texts:
        sents = split_sentences(t)
        if not sents:
            continue
        first = sents[0]
        if re.match(r"^(最近|昨天|今天|前天|上周|上个月)", first):
            styles["从时间场景切入"] += 1
        elif re.match(r"^(我|我们)", first):
            styles["第一人称直接切入"] += 1
        elif "?" in first or "？" in first:
            styles["抛问题开场"] += 1
        elif re.match(r"^(很多人|大家都|大部分|不少人)", first):
            styles["从普遍现象切入"] += 1
        else:
            styles["从具体场景/故事切入"] += 1
    return [s for s, _ in styles.most_common(3)] or ["从具体场景切入"]


# ================= 4. 节奏层 =================
def analyze_rhythm(texts: list[str]) -> dict:
    all_para_lens, all_sent_lens = [], []
    for t in texts:
        paras = [p.strip() for p in t.split("\n") if p.strip() and not p.strip().startswith("#")]
        all_para_lens.extend(len(p) for p in paras)
        all_sent_lens.extend(len(s) for s in split_sentences(t))

    avg_para = sum(all_para_lens) / len(all_para_lens) if all_para_lens else 60
    avg_sent = sum(all_sent_lens) / len(all_sent_lens) if all_sent_lens else 30

    para_style = "短（2-4行一段）" if avg_para < 80 else ("中（4-8行）" if avg_para < 150 else "长")
    sent_style = "短句为主" if avg_sent < 25 else ("长短句交替" if avg_sent < 40 else "长句为主")
    return {"paragraph_length": para_style, "sentence_variation": sent_style,
            "avg_para_chars": round(avg_para), "avg_sent_chars": round(avg_sent)}


# ================= 5. 结构层 =================
def analyze_structure(texts: list[str]) -> list[str]:
    headers = []
    for t in texts:
        for m in re.finditer(r"^#{1,3}\s+(.+)$", t, re.MULTILINE):
            headers.append(m.group(1).strip())
    return headers[:6] or ["01 章节标题"]


# ================= 6. 语气层 =================
def analyze_tone(texts: list[str]) -> dict:
    total_1p = sum(t.count("我") + t.count("我们") for t in texts)
    total_2p = sum(t.count("你") + t.count("你们") for t in texts)
    total = total_1p + total_2p
    if total == 0:
        return {"person": "混合", "warmth": "待补充", "authority": "待补充"}
    person = "第一人称" if total_1p / total > 0.6 else ("第二人称" if total_2p / total > 0.6 else "混合")
    return {"person": person, "warmth": "待补充", "authority": "待补充"}


# ================= 7. 举例层 =================
def analyze_examples(texts: list[str]) -> dict:
    total = len(texts)
    with_example = sum(1 for t in texts if re.search(r"(比如|例如|我见过|有个|一位|一个学员|案例)", t))
    density = round(with_example / total, 2) if total else 0
    return {"source": "真实经历优先", "density": f"约 {int(density*100)}% 文章含举例"}


# ================= 8. 结尾层 =================
def analyze_ending(texts: list[str]) -> str:
    endings = Counter()
    for t in texts:
        sents = split_sentences(t)
        if not sents:
            continue
        last = sents[-1]
        if re.search(r"(希望|期待|一起|来吧)", last):
            endings["行动号召"] += 1
        elif "?" in last or "？" in last:
            endings["抛开放式问题"] += 1
        elif re.search(r"(记住|切记|记住这句话|永远)", last):
            endings["金句收尾"] += 1
        else:
            endings["自然收尾"] += 1
    return endings.most_common(1)[0][0] if endings else "自然收尾"


# ================= 9-14. 高级维度 =================
def analyze_advanced(texts: list[str]) -> dict:
    total = sum(len(t) for t in texts)
    n_digits = sum(len(re.findall(r"\d+", t)) for t in texts)
    n_quotes = sum(t.count("“") + t.count("\"") for t in texts)
    n_slang = sum(t.count("yyds") + t.count("绝绝子") + t.count("栓Q") + t.count("家人们") for t in texts)
    n_terms = sum(len(re.findall(r"[\u4e00-\u9fff]{4,6}", t)) for t in texts)

    return {
        "numbers": "关键数据必给" if n_digits > max(5, total / 500) else "少用具体数字",
        "quotes": "少用，只用真实说过的话" if n_quotes < 5 else "适度引用",
        "slang": "基本不用" if n_slang == 0 else "偶尔用网络语",
        "rhetoric_devices": "适度用对比",
        "jargon": "适度，必须白话解释",
        "stance": "结论清楚，但不绝对",
    }


# ================= 主流程 =================
def build_dna(user: str, sample_patterns: list[str], out_dir: str | None = None) -> Path:
    texts = read_articles(sample_patterns)
    print(f"[dna] 读取 {len(texts)} 篇范文，开始分析…")

    # 全量拼接（用于句式/结构分析保留标题）
    full = "\n".join(texts)
    # 去语法纯文本（用于词频/节奏）
    plain = [strip_markdown(t) for t in texts]

    lexicon = analyze_lexicon(plain)
    syntax = analyze_syntax(full)
    openings = analyze_openings(plain)
    rhythm = analyze_rhythm(texts)
    structure = analyze_structure(full)
    tone = analyze_tone(plain)
    examples = analyze_examples(plain)
    ending = analyze_ending(plain)
    advanced = analyze_advanced(plain)

    dna = f"""# ============================================================
# {user} · 文风 DNA 画像（机器可读版 · 14 维）
# 生成方式: dna_builder.py 范文建模（{len(texts)} 篇样本自动分析）
# 用途: 所有"{user}口吻"写作任务的风格基准
# ============================================================

# ===== 一句话指纹 =====
fingerprint: >-
  {tone.get('person', '')}表达，{rhythm.get('sentence_variation', '')}，
  段落{rhythm.get('paragraph_length', '')}，开场{tone.get('authority', '待补充')}。
  如果一个句子读起来不像这个作者，就要重写。

# ───────────────── 一、表层特征（4 维） ─────────────────

# 1. 词汇层：个人词库（高频词）
lexicon:
  top_words:
{chr(10).join(f"    - \"{w}\"" for w in lexicon)}
  stopwords_removed: true

# 2. 句法层：句式指纹（出现>=2次的句式）
syntax_patterns:
  patterns:
{chr(10).join(f"    - {{form: \"{s['form']}\", example: \"{s['example']}\"}}" for s in syntax)}
  forbidden:
    - "不用'如果……就……'长条件句"

# 3. 修辞层：开场三法 + 金句
rhetoric:
  openings:
{chr(10).join(f"    - \"{o}\"" for o in openings)}
  golden_lines:
    style: "金句独立成段"
    frequency: "每篇 2-3 句"

# 4. 节奏层：段落与句长
rhythm:
  paragraph_length: "{rhythm.get('paragraph_length')}"
  sentence_variation: "{rhythm.get('sentence_variation')}"
  avg_para_chars: {rhythm.get('avg_para_chars')}
  avg_sent_chars: {rhythm.get('avg_sent_chars')}

# ───────────────── 二、结构特征（2 维） ─────────────────

# 5. 结构层：文章骨架
structure:
  default_framework: "观点输出"
  sample_sections:
{chr(10).join(f"    - \"{s}\"" for s in structure)}

# 6. 语气层：人称与温度
tone:
  person: "{tone.get('person')}"
  warmth: "待补充（可从范文补充）"
  authority: "待补充"

# ───────────────── 三、内容特征（2 维） ─────────────────

# 7. 举例层
examples:
  source: "{examples.get('source')}"
  density: "{examples.get('density')}"

# 8. 结尾层
ending:
  style: "{ending}"
  cta: "留一个'我也能做'的信心"

# ───────────────── 四、高级维度（6 维） ─────────────────
advanced:
  numbers: "{advanced.get('numbers')}"
  quotes: "{advanced.get('quotes')}"
  slang: "{advanced.get('slang')}"
  rhetoric_devices: "{advanced.get('rhetoric_devices')}"
  jargon: "{advanced.get('jargon')}"
  stance: "{advanced.get('stance')}"
"""

    base = Path(out_dir) if out_dir else Path(f"users/{user}")
    base.mkdir(parents=True, exist_ok=True)
    out = base / "style-dna.yaml"
    out.write_text(dna, encoding="utf-8")
    print(f"[dna] ✓ 已生成 14 维文风 DNA：{out}")
    print(f"[dna]   高频词: {', '.join(lexicon[:8])}")
    print(f"[dna]   句式指纹: {', '.join(s['form'] for s in syntax)}")
    print(f"[dna]   开场风格: {', '.join(openings)}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="范文 → 14 维文风 DNA 自动提炼")
    ap.add_argument("--user", required=True, help="用户 id（输出到 users/<id>/）")
    ap.add_argument("--samples", help="范文路径 glob，如 '/path/to/articles/*.md'")
    ap.add_argument("--file", action="append", help="单篇范文（可多次传）")
    ap.add_argument("--out-dir", help="输出目录（默认 users/<id>/）")
    args = ap.parse_args()

    patterns = args.file or []
    if args.samples:
        patterns.append(args.samples)
    if not patterns:
        ap.error("至少提供 --samples 或 --file")

    build_dna(args.user, patterns, args.out_dir)
