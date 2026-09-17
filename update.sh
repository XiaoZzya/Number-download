#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="${APP_ROOT}/source"
META_FILE="${APP_ROOT}/etc/install.toml"
REPO_URL="https://github.com/XiaoZzya/Number-download.git"
BRANCH="main"

[[ -f "${META_FILE}" ]] || { echo "错误：找不到安装记录 ${META_FILE}" >&2; exit 1; }
[[ -d "${SOURCE_ROOT}/.git" ]] || { echo "错误：找不到更新源码 ${SOURCE_ROOT}" >&2; exit 1; }
CURRENT_REMOTE="$(git -C "${SOURCE_ROOT}" remote get-url origin)"
[[ "${CURRENT_REMOTE}" == "${REPO_URL}" ]] || { echo "错误：更新源不匹配：${CURRENT_REMOTE}" >&2; exit 1; }
[[ -z "$(git -C "${SOURCE_ROOT}" status --porcelain)" ]] || { echo "错误：更新源码存在未提交修改，拒绝覆盖。" >&2; exit 1; }

readarray -t metadata < <(python3 - "${META_FILE}" <<'PY'
import sys, tomllib
with open(sys.argv[1], "rb") as f: d = tomllib.load(f)
print(d["install_root"]); print(d["output_root"]); print(d["command_name"])
PY
)
INSTALL_ROOT="${metadata[0]}"; OUTPUT_ROOT="${metadata[1]}"; COMMAND_NAME="${metadata[2]}"

echo "1. 根据当前配置升级"
echo "2. 重新配置后升级"
echo "0. 取消"
read -r -p "请选择 [0-2]（默认 1）：" choice
case "${choice:-1}" in
  1) mode=(--upgrade-current --install-dir "${INSTALL_ROOT}" --output-dir "${OUTPUT_ROOT}" --command-name "${COMMAND_NAME}") ;;
  2) mode=(--reconfigure --install-dir "${INSTALL_ROOT}") ;;
  0) exit 0 ;;
  *) echo "错误：无效选项。" >&2; exit 2 ;;
esac

git -C "${SOURCE_ROOT}" fetch origin "${BRANCH}"
git -C "${SOURCE_ROOT}" merge --ff-only "origin/${BRANCH}"
chmod 0755 "${SOURCE_ROOT}/install.sh" "${SOURCE_ROOT}/update.sh"
exec "${SOURCE_ROOT}/install.sh" "${mode[@]}"
