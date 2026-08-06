#!/usr/bin/env bash
# ============================================================
# init.sh — 新用户初始化向导（通用版 Skill）
# 用法：bash init.sh {user_id}
#   例：bash init.sh alice
#
# 作用：
#   1. 校验 user_id 合法性
#   2. 复制 templates/ 5 份模板到 users/{user_id}/
#   3. 交互式问答：赛道 / 读者 / 语气 / 字数 / 视觉风格
#   4. 生成 5 份配置（identity / topics / style / style-dna / lark）
#   5. 提示下一步（可选：范文建模 / 扫码登录）
# ============================================================

set -e

# ===== 颜色 =====
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

PYTHON="${PYTHON:-python3}"

# ===== 校验参数 =====
if [ $# -lt 1 ]; then
    echo -e "${RED}用法：bash init.sh {user_id}${NC}"
    echo "示例：bash init.sh alice"
    exit 1
fi
USER_ID="$1"

if [[ ! "$USER_ID" =~ ^[a-z0-9_-]+$ ]]; then
    echo -e "${RED}✗ user_id 只能包含小写字母 / 数字 / 下划线 / 横线${NC}"
    exit 1
fi

if [ -d "users/$USER_ID" ]; then
    echo -e "${RED}✗ users/$USER_ID 已存在${NC}"
    echo "  列出所有用户：bash use.sh --list"
    exit 1
fi

echo -e "${CYAN}== 初始化用户: $USER_ID ==${NC}"
echo ""

# ===== [1/6] 复制模板 =====
echo -e "${YELLOW}[1/6] 复制模板${NC}"
mkdir -p "users/$USER_ID"
for f in identity topics style style-dna lark; do
    cp "templates/$f.template.yaml" "users/$USER_ID/$f.yaml"
done
echo -e "${GREEN}  ✓ 已复制 5 份模板到 users/$USER_ID/${NC}"
echo ""

# ===== [2/6] 基础信息 =====
echo -e "${YELLOW}[2/6] 基础信息${NC}"
echo "（直接回车用默认值，事后可手动改文件）"
echo ""

read -p "你的名字 / 笔名 (例: 张三): " REAL_NAME
REAL_NAME="${REAL_NAME:-你的名字}"

read -p "公众号名 (例: 张三的美食日记): " ACCOUNT_NAME
ACCOUNT_NAME="${ACCOUNT_NAME:-你的公众号}"

echo "公开级别:"
select LEVEL in "全公开" "半公开" "匿名"; do
    LEVEL_VALUE="$LEVEL"
    break
done

echo ""

# ===== [3/6] 赛道配置 =====
echo -e "${YELLOW}[3/6] 选题赛道${NC}"
echo "你的账号写什么内容？输入 3 个赛道，每个给关键词（逗号分隔）"
echo ""

read -p "主赛道 A 名称 (例: 美食探店): " TRACK_A
TRACK_A="${TRACK_A:-主赛道}"
read -p "主赛道 A 关键词（逗号分隔, 例: 美食,探店,餐厅）: " KW_A
IFS=',' read -ra KWA <<< "$KW_A"

read -p "赛道 B 名称 (例: 行业观察): " TRACK_B
TRACK_B="${TRACK_B:-}"
read -p "赛道 B 关键词（逗号分隔）: " KW_B
IFS=',' read -ra KWB <<< "$KW_B"

read -p "赛道 C 名称 (可回车跳过): " TRACK_C
TRACK_C="${TRACK_C:-}"
read -p "赛道 C 关键词（逗号分隔）: " KW_C
IFS=',' read -ra KWC <<< "$KW_C"

echo ""

# ===== [4/6] 写作风格 =====
echo -e "${YELLOW}[4/6] 写作风格${NC}"
echo ""

echo "你的语气（选一个最接近的）:"
select TONE in "温柔但骨架硬" "犀利干货型" "平实科普型" "亲切陪伴型" "专业权威型"; do
    TONE_VALUE="$TONE"
    break
done

read -p "目标字数（默认 1800）: " TARGET_CHARS
TARGET_CHARS="${TARGET_CHARS:-1800}"

echo ""

# ===== [5/6] 视觉风格 =====
echo -e "${YELLOW}[5/6] 排版主题${NC}"
echo "选一套排版主题（18 套可选，默认 warm-editorial）:"
select THEME in "warm-editorial" "professional-clean" "elegant-rose" "moyu-green" "bold-green" "bold-navy" "bauhaus" "github" "ink" "midnight" "minimal" "newspaper" "sspai" "tech-modern"; do
    THEME_VALUE="$THEME"
    break
done
echo ""

# ===== 生成配置（Python 批量替换）=====
echo -e "${YELLOW}[6/6] 生成配置${NC}"

$PYTHON - "$USER_ID" "$REAL_NAME" "$ACCOUNT_NAME" "$LEVEL_VALUE" "$TRACK_A" "$KW_A" "$TRACK_B" "$KW_B" "$TRACK_C" "$KW_C" "$TONE_VALUE" "$TARGET_CHARS" "$THEME_VALUE" <<'PYEOF'
import sys, os, re

user_id, real_name, account_name, level = sys.argv[1:5]
track_a, kw_a, track_b, kw_b, track_c, kw_c = sys.argv[5:11]
tone, target_chars, theme = sys.argv[11:14]

def yaml_list(items, indent="      "):
    """把逗号分隔字符串转成 YAML 列表（过滤空项）。"""
    out = []
    for it in items:
        it = it.strip()
        if it:
            out.append(f"{indent}- \"{it}\"")
    return "\n".join(out) if out else f"{indent}- \"关键词1\""

base = f"users/{user_id}"

def patch(path, replacements):
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    for old, new in replacements:
        if new is not None:
            text = text.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

# --- identity.yaml ---
patch(f"{base}/identity.yaml", [
    ('name: "你的姓名或笔名"', f'name: "{real_name}"'),
    ('account_name: "你的公众号名称"', f'account_name: "{account_name}"'),
    ('public_level: "全公开"', f'public_level: "{level}"'),
])

# --- topics.yaml ---
patch(f"{base}/topics.yaml", [
    ('name: "赛道 A 名称"', f'name: "{track_a}"'),
    ('- "关键词 1"            # 例：美食探店', yaml_list(kw_a.split(','))),
])

if track_b:
    patch(f"{base}/topics.yaml", [
        ('name: "赛道 B 名称"', f'name: "{track_b}"'),
    ])
    # 替换 B 赛道的第一个关键词
    b_text = open(f"{base}/topics.yaml", encoding='utf-8').read()
    b_kw = yaml_list(kw_b.split(','))
    # 简单处理：把 B 段第一个关键词替换
    b_text = re.sub(r'(name: ".*?"\n    weight: 8\n    keywords:\n      - "关键词 1")',
                    lambda m: m.group(1).replace('- "关键词 1"', b_kw.split(chr(10))[0]), b_text, count=1)
    open(f"{base}/topics.yaml", 'w', encoding='utf-8').write(b_text)

if track_c:
    patch(f"{base}/topics.yaml", [
        ('name: "赛道 C 名称"', f'name: "{track_c}"'),
    ])

# --- style.yaml ---
patch(f"{base}/style.yaml", [
    ('theme: "warm-editorial"   # 18 套可选', f'theme: "{theme}"   # 18 套可选'),
    ('tone: "一句话描述你的语气"', f'tone: "{tone}"'),
    ('target_chars: 1800', f'target_chars: {target_chars}'),
])

# --- style-dna.yaml ---
patch(f"{base}/style-dna.yaml", [
    ('fingerprint: "用一句话描述你的文风指纹"',
     f'fingerprint: "{tone}，像一位见多识广的同行的分享经验"'),
])

print(f"  ✓ identity.yaml / topics.yaml / style.yaml / style-dna.yaml 已生成")
PYEOF

echo -e "${GREEN}  ✓ 配置生成完成${NC}"
echo ""

# ===== 设为激活用户 =====
echo "$USER_ID" > ".active_user"
echo -e "${GREEN}✓ 当前激活用户: $USER_ID${NC}"
echo ""

# ===== 完成提示 =====
echo -e "${CYAN}== 初始化完成 ==${NC}"
echo ""
echo "下一步建议："
echo "  1. 手动补全 users/$USER_ID/identity.yaml（痛点池/案例库/写作边界）"
echo "  2. （强烈推荐）范文建模提炼文风："
echo "     python scripts/dna_builder.py --user $USER_ID --samples '/path/to/articles/*.md'"
echo "  3. 扫码登录：bash scripts/login.sh $USER_ID"
echo "  4. 跑一篇试试：bash pipeline.sh $USER_ID --topic manual --title '测试'"
echo ""
