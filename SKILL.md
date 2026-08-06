---
name: wechat-automation-weme
description: >-
  微信公众号全自动发布流水线（WEME 版）。当用户要求「写一篇公众号文章」「自动发布到公众号」「选题→写作→配图→发布全流程」
  「创建公众号账号配置」「用范文提炼写作风格」时使用。从选题采集、内容生成（14维文风DNA写作+事实核查+合规审稿）、
  AI配图去水印、排版到Playwright发布草稿箱的10步4阶段闭环。不含个人账号信息，安装后需先 init.sh 初始化用户配置。
  注意：不适用于抖音/小红书/知乎等其他平台发布。
---

# 公众号自动化 · 通用版（WEME · wechat-automation-weme）

> 版本：v1.1 通用版 ｜ 日期：2026-08-07
> **本 Skill 为通用模板，不含任何预置个人账号信息**，安装后通过向导输入你自己的赛道、风格、身份即可使用。
> 完全自包含：引擎随包分发，零外部运行时依赖。

---

## 一、这是什么

一套**10 步 4 阶段**的公众号全自动流水线，封装为可复用 Skill：

```
Phase 1 选题融合 → Phase 2 内容质量升级 → Phase 3 视觉与排版 → Phase 4 发布与闭环
  ①采集 ②评分     ③任务书 ④初稿 ⑤核查 ⑥审稿   ⑦生图 ⑧排版      ⑨发布 ⑩复盘
```

- 输入：全网热点
- 输出：草稿箱里一篇排版好的文章（含封面 + 配图）
- 特点：赛道精准选题、14 维文风 DNA 仿写、事实核查 + 合规护栏、智能去水印

---

## 二、目录结构

```
wechat-automation-weme/
├── SKILL.md                    ← 本文件
├── init.sh                     ← 用户初始化向导（交互问答生成配置）
├── pipeline.sh                 ← 主流程封装（调用包内 fusion 引擎，读用户配置）
├── login.sh                    ← 公众号扫码登录（会话存用户目录）
├── fusion/                     ← 【自包含引擎】D2→D8 全流程（本包自带，零外部依赖）
│   ├── auto_pipeline.py        ← 主编排器
│   ├── topic_scorer.py         ← 选题评分
│   ├── brief_generator.py      ← 任务书生成
│   ├── fact_check.py           ← 事实核查
│   ├── review_engine.py        ← 编辑审稿
│   ├── layout.py               ← 排版（内置转换器优先，wewrite 可选增强）
│   ├── publisher.py            ← 发布适配
│   ├── ...（共 12 个模块）
│   └── sample/                 ← 中性示例数据
├── templates/                  ← 5 份空白配置模板
│   ├── identity.template.yaml  ← 作者身份画像
│   ├── topics.template.yaml    ← 选题赛道
│   ├── style.template.yaml     ← 视觉与语言风格
│   ├── style-dna.template.yaml ← 14 维文风 DNA
│   ├── lark.template.yaml      ← 飞书配置（可选）
│   └── README.md               ← 模板说明
├── scripts/
│   ├── dna_builder.py          ← 范文 → 14 维 DNA 自动提炼
│   └── remove_watermark.py     ← 智能去水印
└── users/
    └── _template/              ← 空白用户目录（init.sh 复制用）
```

**✅ 完全自包含**：引擎就在包内 `fusion/`，不需要外部 wewrite 环境、不需要 `~/.wewrite`。
pipeline.sh 默认用 `$SCRIPT_DIR/fusion`，可通过 `FUSION_DIR` 环境变量覆盖。
排版引擎三级降级：内置转换器（零依赖）→ wewrite 包（可选增强）→ 极简 HTML（兜底）。
用户配置通过 `WECHAT_USER_DIR` 环境变量注入引擎，引擎自动读该用户的配置。

---

## 三、安装与初始化

### 第 1 步：安装依赖

```bash
# Python 依赖
pip install pyyaml beautifulsoup4 cssutils markdown
# 浏览器自动化
npm install playwright && npx playwright install chromium
```

### 第 2 步：初始化你的账号（核心）

```bash
bash init.sh alice
```

交互式问答 5 组问题：
1. **基础信息**：姓名 / 公众号名 / 公开级别
2. **选题赛道**：3 个赛道名称 + 关键词（逗号分隔）
3. **写作风格**：语气（温柔但骨架硬 / 犀利干货 / 平实科普 / 亲切陪伴 / 专业权威）+ 目标字数
4. **排版主题**：18 套可选（warm-editorial / professional-clean / elegant-rose…）
5. **飞书配置**（可选）：跳过走本地 stub

向导自动生成 `users/alice/` 下 5 份配置。

> ⚠️ **严格校验**：未执行 init.sh（或配置仍为模板占位）就运行 pipeline，
> 流程会直接报错中止并提示「请先运行 bash init.sh」，不会用默认值硬跑出错误内容。
> 所以**必须**先把 5 份配置填好（至少 identity + topics + style 三份必填）。

### 第 3 步（强烈推荐）：范文建模提炼文风

```bash
python scripts/dna_builder.py --user alice --samples "/path/to/your/articles/*.md"
```

读 3-10 篇你自己写的文章 → 自动提炼 14 维文风 DNA（词库/句式/节奏/开场/结尾…）
**比填空准得多**——DNA 是"学出来的"，不是"填出来的"。

### 第 4 步：扫码登录

```bash
bash scripts/login.sh alice
```

### 第 5 步：跑一篇试试

```bash
bash pipeline.sh alice --topic manual --title "测试" --body-file test.md
```

---

## 四、5 份配置模板说明

| 模板 | 必填 | 决定什么 | 对应步骤 |
|---|---|---|---|
| `identity.template.yaml` | ✅ | 作者身份画像——AI 写"我是谁/我做过"的素材库 | ③任务书 ④写稿 |
| `topics.template.yaml` | ✅ | 选题赛道——采集关键词 + 评分权重 | ①采集 ②评分 |
| `style.template.yaml` | ✅ | 视觉语言——排版主题 + 配图风格 + 语气 | ⑦生图 ⑧排版 |
| `style-dna.template.yaml` | ⭐推荐建模 | 14 维文风指纹 | ④写稿 |
| `lark.template.yaml` | ⭕可选 | 飞书表格/通知（不填走本地 stub） | ①推送 ⑨记录 |

### 填写原则（防翻车）

- **identity 只填真实信息**——AI 只会写你填过的，虚构会导致文章翻车
- **dna 用范文建模**——填空只能填出形容词，范文建模才能学到句式指纹
- **写作边界认真填**——不虚构案例/不夸大结果/不承诺变现，这是你的合规护栏

---

## 五、核心流程（10 步 4 阶段）

### Phase 1 · 选题融合

**① 红狐采集 + 飞书推送 Top20**
- 调红狐 API 拉 24h/72h 热点 → 按你的赛道关键词粗筛 → 评分 → Top20 推飞书
- 粗筛关键词来自 `topics.yaml` 的 tracks（双保险第一步）

**② 评分 + 历史去重 + SEO**
- 5 维加权：赛道匹配 0.30 / SEO 0.25 / 时效 0.20 / 去重 0.15 / 账号匹配 0.10
- 与历史文章去重（避免重复选题）→ Top3-5 进 Phase 2

### Phase 2 · 内容质量升级

**③ 任务书 + 14 维 DNA**：读你的 identity + style-dna → 生成 brief（读者/核心判断/结构骨架/字数）
**④ 写初稿**：wewrite-write 按 brief 起草（保留你的 DNA 指纹）+ 语病检测
**⑤ 事实核查**：提取所有"事实声明"→ 联网查证 → 标记 🟢有源/🟡推断/🔴无据
**⑥ 编辑审稿**：六项判断（准确/观点/有用/合声/好读/合规）+ 合规自动修复 + 双模式

### Phase 3 · 视觉与排版

**⑦ AI 生图 + 智能去水印**：封面 1175×500 + 配图 1024×1024（风格来自 style.yaml）→ 底部水印检测裁剪
**⑧ 排版**：双引擎（内置 converter 优先 → wewrite CLI → 极简 HTML），18 主题可选

### Phase 4 · 发布与闭环

**⑨ Playwright 发布**：登录复用 → 填标题/正文/封面 → 存草稿 → 飞书记录
**⑩ 数据复盘**：7 天后拉阅读数据 → 反哺选题（bottom 进避免池 / top 提权重）

---

## 六、双模式说明

| 模式 | 配置 | 行为 |
|---|---|---|
| 全自动 | `review_mode.auto: true` | 审稿+合规修复通过后直接进 Phase 3 |
| 半自动 | `review_mode.auto: false` | 审稿通过后暂停，等人工确认再继续 |
| 自动修复 | `review_mode.auto_fix: true` | 合规命中自动改完出终稿 |

**人工介入点仅 3 处**：选题确认 / 审稿确认（半自动）/ 正式发布

---

## 七、架构说明：代码与身份分离

本 Skill 遵循**代码层与身份资产层分离**设计：

| | 代码层（随包分发） | 身份资产层（用户自建） |
|---|---|---|
| 内容 | fusion 引擎 + 脚本 + 模板 | identity / topics / style / style-dna / lark |
| 来源 | 本包自带 | init.sh 向导生成 |
| DNA | 引擎能力（通用） | 用户范文建模（dna_builder） |
| 变更 | 升级 Skill 包即可 | 改 users/<id>/ 下配置 |

- 引擎完全通用，不含任何特定作者信息
- 用户身份全部由向导生成，可随时更换
- 换人用 = 新建一个 user，不动引擎

---

## 八、常见问题

**Q: 我没有历史文章，怎么建 DNA？**
A: 用 init.sh 填空模式先跑，跑几篇后把满意的文章喂给 dna_builder 重新建模。

**Q: 微信个人号能发布吗？**
A: 能。个人订阅号无官方 API，本 Skill 用 Playwright 模拟浏览器操作，扫码登录一次后免密。

**Q: 会被微信风控吗？**
A: 每天 1 篇 + 模拟真人输入节奏，不会触发。不建议用此工具做矩阵号。

**Q: 需要服务器吗？**
A: 不需要。本机运行，数据全在本地 + 你自己的飞书表格。
