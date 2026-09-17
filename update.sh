#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="/data/dd"
SOURCE_ROOT="${APP_ROOT}/source"
REPO_URL="https://github.com/XiaoZzya/Number-download.git"
BRANCH="main"

if [[ "${EUID}" -ne 0 ]]; then
  echo "错误：更新仅支持 root 执行。" >&2
  exit 1
fi

if [[ ! -d "${SOURCE_ROOT}/.git" ]]; then
  if [[ -e "${SOURCE_ROOT}" ]]; then
    echo "错误：${SOURCE_ROOT} 已存在但不是 Git 仓库，请人工检查。" >&2
    exit 1
  fi
  git clone --branch "${BRANCH}" --single-branch "${REPO_URL}" "${SOURCE_ROOT}"
else
  CURRENT_REMOTE="$(git -C "${SOURCE_ROOT}" remote get-url origin)"
  if [[ "${CURRENT_REMOTE}" != "${REPO_URL}" ]]; then
    echo "错误：更新源不匹配，拒绝更新：${CURRENT_REMOTE}" >&2
    exit 1
  fi
  if [[ -n "$(git -C "${SOURCE_ROOT}" status --porcelain)" ]]; then
    echo "错误：更新源码目录存在未提交修改，拒绝覆盖。" >&2
    exit 1
  fi
  git -C "${SOURCE_ROOT}" fetch origin "${BRANCH}"
  git -C "${SOURCE_ROOT}" merge --ff-only "origin/${BRANCH}"
fi

chmod 0755 "${SOURCE_ROOT}/install.sh" "${SOURCE_ROOT}/update.sh"
exec "${SOURCE_ROOT}/install.sh"
