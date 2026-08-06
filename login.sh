#!/usr/bin/env bash
# ============================================================
# login.sh — 公众号扫码登录（通用版 Skill）
# 用法：
#   bash login.sh                 # 用激活用户登录
#   bash login.sh alice           # 指定用户登录
#
# 作用：
#   弹出微信登录二维码 → 扫码确认 → 会话保存到 users/<id>/session.json
#   之后发布自动复用该会话（免二次扫码）
# ============================================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# ===== 决定 USER_ID =====
USER_ID="${1:-}"
if [ -z "$USER_ID" ]; then
    if [ -f ".active_user" ]; then
        USER_ID=$(cat .active_user)
    else
        echo -e "${RED}✗ 没指定 user_id，且无激活用户${NC}"
        exit 1
    fi
fi

if [ ! -d "users/$USER_ID" ]; then
    echo -e "${RED}✗ users/$USER_ID 不存在，先 bash init.sh $USER_ID${NC}"
    exit 1
fi
echo "$USER_ID" > ".active_user"

echo -e "${CYAN}== 登录用户: $USER_ID ==${NC}"
echo ""

# ===== 检查发布脚本 =====
PUBLISH_JS="${PUBLISH_JS:-$HOME/.workbuddy/skills/wechat-publisher/publish.js}"
if [ ! -f "$PUBLISH_JS" ]; then
    # 尝试几个常见位置
    for cand in \
        "$SCRIPT_DIR/publish.js" \
        "$HOME/WorkBuddy/2026-08-04-01-09-55/publish-weme.js" \
        "$HOME/WorkBuddy/2026-07-29-19-33-27/wechat-publish/publish.js"; do
        if [ -f "$cand" ]; then PUBLISH_JS="$cand"; break; fi
    done
fi

if [ ! -f "$PUBLISH_JS" ]; then
    echo -e "${RED}✗ 找不到发布脚本 publish.js${NC}"
    echo "  设 PUBLISH_JS=/path/to/publish.js 或先部署发布脚本"
    exit 1
fi
echo -e "  发布脚本: $PUBLISH_JS"

# ===== 检查 Node =====
NODE_BIN="${NODE_BIN:-node}"
if ! command -v "$NODE_BIN" >/dev/null 2>&1; then
    echo -e "${RED}✗ 找不到 node${NC}"
    exit 1
fi

# ===== 设置会话路径 =====
export WECHAT_USER="$USER_ID"
export WECHAT_SESSION="$(pwd)/users/$USER_ID/session.json"
mkdir -p "users/$USER_ID"

echo -e "${YELLOW}== 启动登录（弹出二维码，用绑定公众号的微信扫码）==${NC}"
echo "  会话保存到: $WECHAT_SESSION"
echo ""

# ===== 执行发布脚本的登录模式 =====
if [ -f "$PUBLISH_JS" ]; then
    # publish.js 支持 --login-only 时走它，否则 --no-headless 全流程
    if grep -q "login-only\|--login" "$PUBLISH_JS" 2>/dev/null; then
        node "$PUBLISH_JS" --login-only --no-headless --user "$USER_ID" || \
        node "$PUBLISH_JS" --login --no-headless --user "$USER_ID"
    else
        echo -e "${YELLOW}! publish.js 不支持 --login-only，尝试直接跑（第一次会弹二维码）${NC}"
        node "$PUBLISH_JS" --no-headless --user "$USER_ID"
    fi
fi

echo ""
echo -e "${GREEN}== 登录完成 ==${NC}"
echo "  下一步：bash pipeline.sh $USER_ID --topic '你的选题'"
