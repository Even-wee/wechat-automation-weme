# 用户配置模板说明（templates/）

安装后，`init.sh` 向导会引导你复制并填写这 5 份模板，生成你的专属配置。

## 5 份模板一览

| 模板 | 必填? | 决定什么 | 对应流水线步骤 |
|---|---|---|---|
| `identity.template.yaml` | ✅ 必填 | 作者身份画像——AI 写"我是谁/我做过/我用过"的素材库 | ③ 任务书、④ 写稿 |
| `topics.template.yaml` | ✅ 必填 | 选题赛道——采集按哪些词筛选、评分怎么算 | ① 采集、② 评分 |
| `style.template.yaml` | ✅ 必填 | 视觉与语言风格——排版主题、配图调性、语气 | ⑦ 生图、⑧ 排版 |
| `style-dna.template.yaml` | ⭐ 推荐建模 | 14 维文风 DNA——"你的文章是什么味道" | ④ 写稿 |
| `lark.template.yaml` | ⭕ 可选 | 飞书表格/通知（不填走本地 stub） | ① 推送、⑨ 记录 |

## 填写顺序建议

```
1. identity.template.yaml    ← 最先填（10 分钟，最重要）
2. topics.template.yaml      ← 第二填（5 分钟，决定选题准不准）
3. style.template.yaml       ← 第三填（5 分钟，不满意可先默认）
4. style-dna.template.yaml   ← 强烈建议用「范文建模」自动生成
5. lark.template.yaml        ← 可选，不接飞书可跳过
```

## 用法

```bash
# 复制模板创建你的配置（user_id 是你的名字，如 alice）
cp templates/identity.template.yaml users/alice/identity.yaml
cp templates/topics.template.yaml   users/alice/topics.yaml
cp templates/style.template.yaml    users/alice/style.yaml
cp templates/style-dna.template.yaml users/alice/style-dna.yaml
cp templates/lark.template.yaml     users/alice/lark.yaml

# 然后编辑 users/alice/*.yaml 填你的信息
```

## 快捷方式

`init.sh` 向导（推荐）：
```bash
bash init.sh alice
# 交互式问答：赛道关键词 → 读者 → 语气 → 字数 → 视觉风格
# 自动生成 5 份配置到 users/alice/
```

`dna_builder.py` 范文建模（推荐，自动提炼文风）：
```bash
python scripts/dna_builder.py --user alice --samples /path/to/your/articles/*.md
# 读 3-10 篇你的历史文章 → 自动生成 style-dna.yaml
```

## 重要提醒

- **identity 只填真实信息**——AI 只会写你填过的，虚构会导致文章翻车
- **style-dna 是学出来的**——填空只能填出形容词，范文建模才能学到句式指纹
- 所有配置改完，跑 `bash pipeline.sh alice` 即用新配置生效
