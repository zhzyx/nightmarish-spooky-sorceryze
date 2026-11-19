#!/bin/bash
set -euo pipefail

# 桌面启动不会继承终端 export；从图形会话或登录钥匙串恢复，不写入项目。
if [[ -z "${KIMI_API_KEY:-}" ]]; then
    if command -v launchctl >/dev/null 2>&1; then
        KIMI_API_KEY="$(launchctl getenv KIMI_API_KEY || true)"
    fi
    if [[ -z "${KIMI_API_KEY:-}" ]] && command -v security >/dev/null 2>&1; then
        KIMI_API_KEY="$(security find-generic-password -a "$(id -un)" -s "com.gonggong.ainative.KIMI_API_KEY" -w 2>/dev/null || true)"
    fi
    export KIMI_API_KEY
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCH="$(uname -m)"
ENGINE="$REPO/bin/godot.macos.editor.$ARCH"
PROJECT="$REPO/samples/gonggong-workbench"

fail() {
    status=$?
    set +e
    echo
    echo "[失败] 无法启动引擎，请查看上方错误信息。"
    read -r -p "按回车键关闭窗口..."
    exit "$status"
}
trap fail ERR

if [[ ! -x "$ENGINE" ]]; then
    echo "[错误] 找不到引擎：$ENGINE"
    echo "请先运行桌面上的“更新编译并启动引擎.command”。"
    false
fi

if [[ ! -d "$PROJECT" ]]; then
    echo "[错误] 找不到项目：$PROJECT"
    false
fi

cd "$REPO"
echo "正在启动引擎……"
trap - ERR
exec "$ENGINE" --editor --path "$PROJECT"
