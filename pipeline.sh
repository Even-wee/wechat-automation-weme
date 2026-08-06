#!/usr/bin/env bash
# ============================================================
# pipeline.sh — 主流程封装（通用版 Skill）
# 用法：
#   bash pipeline.sh                              # 用激活用户跑完整流程（采集→写作→发布）
#   bash pipeline.sh alice                        # 指定用户跑
#   bash pipeline.sh alice --topic "选题标题"      # 指定选题
#   bash pipeline.sh alice --from D6 --draft a.md  # 从某步开始
#   bash pipeline.sh alice --only D2               # 只跑某步
#   bash pipeline.sh --help                        # 看用法
#
# 底层：调用 fusion/auto_pipeline.py（D2→D8 主编排器）
# ============================================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

PYTHON="${PYTHON:-python3}"
# 引擎默认用包内自包含的 fusion/（无需外部 ~/.wewrite 环境）
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
FUSION_DIR="${FUSION_DIR:-$SCRIPT_DIR/fusion}"

# ===== 参数 =====
USER_ID=""
TOPIC=""
ONLY=""
FROM=""
DRAFT=""
REVIEW_MODE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            echo "用法："
            echo "  bash pipeline.sh                              用激活用户跑完整流程"
            echo "  bash pipeline.sh {user_id}                    指定用户跑"
            echo "  bash pipeline.sh {user_id} --topic '选题'      指定选题"
            echo "  bash pipeline.sh {user_id} --only D2          只跑某步"
            echo "  bash pipeline.sh {user_id} --from D6 --draft a.md  从某步开始"
            echo "  bash pipeline.sh {user_id} --review-mode manual  半自动（人工确认）"
            exit 0
            ;;
        --topic) TOPIC="$2"; shift 2 ;;
        --only) ONLY="$2"; shift 2 ;;
        --from) FROM="$2"; shift 2 ;;
        --draft) DRAFT="$2"; shift 2 ;;
        --review-mode) REVIEW_MODE="$2"; shift 2 ;;
        --*) echo -e "${RED}未知参数: $1${NC}"; exit 1 ;;
        *)
            if [ -z "$USER_ID" ]; then USER_ID="$1"; shift
            else echo -e "${RED}多余参数: $1${NC}"; exit 1; fi
            ;;
    esac
done

# ===== 决定 USER_ID =====
if [ -z "$USER_ID" ]; then
    if [ -f ".active_user" ]; then
        USER_ID=$(cat .active_user)
    else
        echo -e "${RED}✗ 没指定 user_id，且无激活用户${NC}"
        echo "  bash init.sh {user_id} 创建并激活"
        exit 1
    fi
fi

if [ ! -d "users/$USER_ID" ]; then
    echo -e "${RED}✗ users/$USER_ID 不存在${NC}"
    echo "  bash init.sh $USER_ID 初始化"
    exit 1
fi
echo "$USER_ID" > ".active_user"

echo -e "${CYAN}== 用户: $USER_ID ==${NC}"
echo ""

# ===== 校验配置 =====
echo -e "${YELLOW}[0] 校验配置${NC}"
MISSING=""
for f in identity topics style style-dna; do
    if [ ! -f "users/$USER_ID/$f.yaml" ]; then
        MISSING="$MISSING $f.yaml"
    fi
done
if [ -n "$MISSING" ]; then
    echo -e "${RED}  ✗ 缺配置:$MISSING${NC}"
    echo "  bash init.sh $USER_ID 重新初始化"
    exit 1
fi
echo -e "${GREEN}  ✓ 配置齐全${NC}"
echo ""

# ===== 检查 fusion 引擎 =====
if [ ! -f "$FUSION_DIR/auto_pipeline.py" ]; then
    echo -e "${YELLOW}! fusion 引擎不在 $FUSION_DIR${NC}"
    echo "  设 FUSION_DIR 指向真实引擎目录，或先部署引擎"
fi

# ===== 拼 auto_pipeline 参数 =====
ARGS=()
if [ -n "$TOPIC" ]; then ARGS+=(--topic "$TOPIC"); fi
if [ -n "$ONLY" ]; then ARGS+=(--only "$ONLY"); fi
if [ -n "$FROM" ]; then ARGS+=(--from "$FROM"); fi
if [ -n "$DRAFT" ]; then ARGS+=(--draft "$DRAFT"); fi
REVIEW_MODE="${REVIEW_MODE:-manual}"   # 通用版默认半自动（安全）
ARGS+=(--review-mode "$REVIEW_MODE")

# 注入用户配置环境变量（fusion 引擎读取）
export WECHAT_USER="$USER_ID"
export WECHAT_USER_DIR="$(pwd)/users/$USER_ID"

echo -e "${YELLOW}== 启动流水线 ==${NC}"
echo "  用户: $USER_ID | 模式: $REVIEW_MODE"
[ -n "$TOPIC" ] && echo "  选题: $TOPIC"
[ -n "$ONLY" ] && echo "  单步: $ONLY"
[ -n "$FROM" ] && echo "  起点: $FROM"
echo ""

# ===== 跑 fusion 引擎 =====
if [ -f "$FUSION_DIR/auto_pipeline.py" ]; then
    PYTHONPATH="$FUSION_DIR" $PYTHON "$FUSION_DIR/auto_pipeline.py" "${ARGS[@]}"
else
    echo -e "${RED}✗ auto_pipeline.py 不存在：$FUSION_DIR/auto_pipeline.py${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}== 流程完成 ==${NC}"
