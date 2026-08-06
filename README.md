# wechat-automation-weme

> 微信公众号全自动发布流水线 · WEME 版
> 10 步 4 阶段端到端闭环：选题 → 写作 → 核查 → 审稿 → 配图 → 排版 → 发布 → 复盘

![version](https://img.shields.io/badge/version-v1.2-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![agents](https://img.shields.io/badge/agents-Codex%20%7C%20Claude%20Code%20%7C%20OpenClaw-important)

一个 **完全自包含** 的公众号自动化 Skill：解压即用，零外部运行时依赖（不需要 wewrite、不需要预装任何内容引擎）。任何支持 SKILL.md 标准的 Agent（Codex CLI / Claude Code / Gemini CLI / Cursor / OpenClaw…）都能加载使用。

---

## ✨ 特性

- **10 步 4 阶段闭环**：选题融合 → 内容质量升级 → 视觉排版 → 发布复盘
- **赛道精准选题**：采集时按你的赛道关键词粗筛 + 5 维加权评分（双保险）
- **14 维文风 DNA**：提供范文自动提炼你的写作风格（`dna_builder.py`）
- **事实核查 + 合规护栏**：claims 账本逐条验证 + 12 类违禁词自动修复
- **智能去水印**：AI 生成图片底部水印自动检测裁剪
- **Playwright 发布**：扫码一次永久免密，自动存草稿箱
- **多用户隔离**：一台机器多个账号，`users/<id>/` 各自独立配置
- **严格校验**：未初始化直接跑会报错引导，不会用默认值硬跑

## 📦 快速开始

```bash
# 1. 安装依赖
pip install pyyaml beautifulsoup4 cssutils markdown
npm install playwright && npx playwright install chromium

# 2. 初始化你的账号（交互问答，约 5 分钟）
bash init.sh alice

# 3. （强烈推荐）用你的历史文章建模文风
python scripts/dna_builder.py --user alice --samples "/path/to/your/articles/*.md"

# 4. 扫码登录公众号
bash login.sh alice

# 5. 跑一篇
bash pipeline.sh alice --topic "你的选题"
```

## 🧩 安装到 Agent

### Codex CLI

```bash
# 方式 1：手动复制
cp -r wechat-automation-weme ~/.codex/skills/

# 方式 2：npx skills（Vercel 通用安装器）
npx skills add your-name/wechat-automation-weme -g -a codex
```

### Claude Code

```bash
cp -r wechat-automation-weme ~/.claude/skills/
```

### 其他 Agent

SKILL.md 是开放标准（Open Agent Skills Ecosystem），Codex / Claude Code / Gemini CLI / Cursor / Cline / OpenClaw 等 27+ 种 Agent 均支持。把 `wechat-automation-weme/` 目录放进对应 Agent 的 `skills/` 路径即可。

## 🏗 目录结构

```
wechat-automation-weme/
├── SKILL.md                    ← Skill 定义（标准 frontmatter）
├── init.sh                     ← 用户初始化向导
├── pipeline.sh                 ← 主流程封装（D2→D8 编排）
├── login.sh                    ← 公众号扫码登录
├── fusion/                     ← 【自包含引擎】12 模块，零外部依赖
│   ├── auto_pipeline.py        ← 主编排器
│   ├── topic_scorer.py         ← 选题评分
│   ├── brief_generator.py      ← 任务书生成
│   ├── fact_check.py           ← 事实核查
│   ├── review_engine.py        ← 编辑审稿
│   ├── layout.py               ← 排版（内置转换器优先）
│   ├── publisher.py            ← 发布适配
│   └── sample/                 ← 中性示例数据
├── templates/                  ← 5 份空白配置模板
├── scripts/
│   ├── dna_builder.py          ← 范文 → 14 维 DNA
│   └── remove_watermark.py     ← 智能去水印
└── users/_template/            ← 空白用户目录
```

## 🔄 工作流程（10 步 4 阶段）

```
Phase 1 选题融合          Phase 2 内容质量升级        Phase 3 视觉排版        Phase 4 发布闭环
① 红狐采集+粗筛          ③ 任务书+14维DNA           ⑦ AI生图+去水印         ⑨ Playwright发布
② 评分+去重+SEO  ───→    ④ 写初稿(warm-editor) ──→  ⑧ 排版18主题  ────────→  ⑩ 数据复盘+反哺
                         ⑤ 事实核查(claims账本)
                         ⑥ 编辑审稿(六项判断+合规)
```

## 🛡 合规与安全

- 写作边界由用户 identity.yaml 定义（防虚构/防夸大/防承诺）
- 事实核查 claims 账本逐条关联来源
- 微信风控：每天 1 篇 + 模拟真人输入节奏，不建议矩阵号

## 📄 License

MIT License © 2026

---

*本仓库为通用模板，不含任何个人账号信息。示例人物「张三」为虚构。*
