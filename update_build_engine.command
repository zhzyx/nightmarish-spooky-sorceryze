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
PYTHON="$HOME/.local/venvs/godot-build/bin/python"
ARCH="$(uname -m)"
ENGINE="$REPO/bin/godot.macos.editor.$ARCH"
PROJECT="$REPO/samples/gonggong-workbench"

fail() {
    status=$?
    set +e
    echo
    echo "[失败] 操作已停止，请查看上方错误信息。"
    read -r -p "按回车键关闭窗口..."
    exit "$status"
}
trap fail ERR

if [[ "$ARCH" != "arm64" && "$ARCH" != "x86_64" ]]; then
    echo "[错误] 不支持的 Mac 架构：$ARCH"
    false
fi

if [[ ! -d "$REPO/.git" ]]; then
    echo "[错误] 找不到仓库：$REPO"
    false
fi

if [[ ! -x "$PYTHON" ]]; then
    echo "[错误] 找不到编译环境：$PYTHON"
    false
fi

cd "$REPO"

echo "[1/3] 切换 main 并拉取最新代码……"
git switch main
git pull --ff-only origin main

echo "[2/3] 编译 macOS $ARCH 编辑器……"
"$PYTHON" -m SCons platform=macos target=editor "arch=$ARCH" use_volk=yes accesskit=no -j8
"$PYTHON" tools/package_tianshu_ui.py --output "$REPO/bin/tianshu-ui.json"

if [[ ! -x "$ENGINE" ]]; then
    echo "[错误] 编译后未找到引擎：$ENGINE"
    false
fi

echo "[3/3] 启动引擎……"
trap - ERR
exec "$ENGINE" --editor --path "$PROJECT"
