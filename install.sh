#!/usr/bin/env bash
set -Eeuo pipefail

# StreamGrab 2.0 local installer for Debian 13 x86_64.
# Review this file locally before running it as root.

APP_ROOT="/data/dd"
OUTPUT_ROOT="/data/downloads/ss"
COMMAND_NAME="d"
DRY_RUN=false

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "错误：install.sh 只支持 root 执行。" >&2
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  echo "错误：无法识别操作系统。" >&2
  exit 1
fi

source /etc/os-release
if [[ "${ID:-}" != "debian" || "${VERSION_ID:-}" != "13" ]]; then
  echo "错误：第一版安装器只支持 Debian 13。当前：${PRETTY_NAME:-unknown}" >&2
  exit 1
fi
if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "错误：第一版安装器只支持 x86_64。" >&2
  exit 1
fi

run() {
  if $DRY_RUN; then
    printf 'DRY-RUN:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "${SOURCE_DIR}/pyproject.toml" || ! -d "${SOURCE_DIR}/src/streamgrab" ]]; then
  echo "错误：请从完整的 StreamGrab 源码目录运行 install.sh。" >&2
  exit 1
fi

EXISTING="$(command -v "${COMMAND_NAME}" 2>/dev/null || true)"
if [[ -n "${EXISTING}" ]] && ! grep -q "STREAMGRAB_MANAGED_ENTRY" "${EXISTING}" 2>/dev/null; then
  echo "命令 ${COMMAND_NAME} 已存在：${EXISTING}"
  if [[ ! -t 0 ]]; then
    echo "错误：非交互安装无法询问新命令名。" >&2
    exit 1
  fi
  read -r -p "请输入新的短命令名称：" COMMAND_NAME
  if [[ ! "${COMMAND_NAME}" =~ ^[a-zA-Z][a-zA-Z0-9_-]{0,31}$ ]]; then
    echo "错误：命令名格式无效。" >&2
    exit 1
  fi
  if command -v "${COMMAND_NAME}" >/dev/null 2>&1; then
    echo "错误：命令 ${COMMAND_NAME} 也已存在，未覆盖。" >&2
    exit 1
  fi
fi

run apt-get update
run apt-get install -y --no-install-recommends \
  python3 python3-venv ca-certificates curl git chromium xvfb ffmpeg fonts-noto-cjk

run install -d -m 0755 "${APP_ROOT}" "${APP_ROOT}/app" "${APP_ROOT}/etc" \
  "${APP_ROOT}/tools" "${APP_ROOT}/logs" "${APP_ROOT}/diagnostics"
run install -d -m 0700 "${APP_ROOT}/profile" "${APP_ROOT}/profile/chromium"
run install -d -m 0755 "${OUTPUT_ROOT}" "${OUTPUT_ROOT}/.data"

run install -m 0644 "${SOURCE_DIR}/pyproject.toml" "${APP_ROOT}/app/pyproject.toml"
run install -m 0644 "${SOURCE_DIR}/README.md" "${APP_ROOT}/app/README.md"
run install -m 0644 "${SOURCE_DIR}/LICENSE" "${APP_ROOT}/app/LICENSE"
run install -m 0755 "${SOURCE_DIR}/update.sh" "${APP_ROOT}/update.sh"
if ! $DRY_RUN; then
  cp -a "${SOURCE_DIR}/src" "${APP_ROOT}/app/"
fi

if [[ ! -x "${APP_ROOT}/venv/bin/python" ]]; then
  run python3 -m venv "${APP_ROOT}/venv"
fi
run "${APP_ROOT}/venv/bin/python" -m pip install --upgrade pip
run "${APP_ROOT}/venv/bin/python" -m pip install "${APP_ROOT}/app"

CONFIG_FILE="${APP_ROOT}/etc/config.toml"
if [[ ! -e "${CONFIG_FILE}" ]] && ! $DRY_RUN; then
  cat >"${CONFIG_FILE}" <<'EOF'
default_output = "/data/downloads/ss"
downloader_path = "/data/dd/tools/N_m3u8DL-RE"
extractor_proxy = ""
timeout_seconds = 20
last_update_check = ""
chromium_path = "/usr/bin/chromium"
browser_profile = "/data/dd/profile/chromium"
diagnostics_dir = "/data/dd/diagnostics"
temp_root = "/data/downloads/ss/.data"
locale = "zh-CN"
page_timeout_ms = 45000
search_wait_ms = 5000
capture_timeout_ms = 30000
m3u8_preferred_domain = "mushroomtrack.com"
allow_m3u8_fallback = false
allow_root_no_sandbox = true
download_threads = 8
EOF
  chmod 0600 "${CONFIG_FILE}"
fi

if [[ ! -x "${APP_ROOT}/tools/N_m3u8DL-RE" ]] && ! $DRY_RUN; then
  STREAMGRAB_CONFIG_DIR="${APP_ROOT}/etc" STREAMGRAB_DATA_DIR="${APP_ROOT}" \
    "${APP_ROOT}/venv/bin/python" -c \
    'from streamgrab.tools import fetch_latest_release, install_release; print(install_release(fetch_latest_release(timeout=60), timeout=180))'
fi

ENTRY="/usr/local/bin/${COMMAND_NAME}"
if ! $DRY_RUN; then
  cat >"${ENTRY}" <<'EOF'
#!/usr/bin/env bash
# STREAMGRAB_MANAGED_ENTRY
set -Eeuo pipefail
export STREAMGRAB_CONFIG_DIR="/data/dd/etc"
export STREAMGRAB_DATA_DIR="/data/dd"
exec xvfb-run -a -s "-screen 0 1365x768x24" /data/dd/venv/bin/streamgrab "$@"
EOF
  chmod 0755 "${ENTRY}"
fi

echo "安装完成。短命令：${COMMAND_NAME}"
echo "运行检查：${COMMAND_NAME} doctor"
