#!/usr/bin/env bash
set -Eeuo pipefail

PRODUCT_NAME="Number download"
REPO_URL="https://github.com/XiaoZzya/Number-download.git"
DRY_RUN=false
RECONFIGURE=false
INSTALL_DIR_ARG=""
OUTPUT_DIR_ARG=""
COMMAND_NAME_ARG=""
ACTION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-dir) INSTALL_DIR_ARG="${2:?缺少安装目录}"; shift 2 ;;
    --output-dir) OUTPUT_DIR_ARG="${2:?缺少下载目录}"; shift 2 ;;
    --command-name) COMMAND_NAME_ARG="${2:?缺少命令名称}"; shift 2 ;;
    --reconfigure) RECONFIGURE=true; ACTION="install"; shift ;;
    --upgrade-current) ACTION="install"; shift ;;
    --uninstall) ACTION="uninstall"; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) echo "错误：未知参数 $1" >&2; exit 2 ;;
  esac
done

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "${SOURCE_DIR}/pyproject.toml" || ! -d "${SOURCE_DIR}/src/streamgrab" ]]; then
  echo "错误：请从完整的 Number download 源码目录运行 install.sh。" >&2
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then echo "错误：无法识别操作系统。" >&2; exit 1; fi
source /etc/os-release
if [[ "${ID:-}" != "debian" || "${VERSION_ID:-}" != "13" || "$(uname -m)" != "x86_64" ]]; then
  echo "错误：当前安装器仅支持 Debian 13 x86_64。当前：${PRETTY_NAME:-unknown} / $(uname -m)" >&2
  exit 1
fi

expand_path() {
  local value="$1"
  if [[ "${value}" == "~" ]]; then value="${HOME}"; fi
  if [[ "${value}" == ~/* ]]; then value="${HOME}/${value#~/}"; fi
  if [[ "${value}" != /* ]]; then echo "错误：路径必须是绝对路径或以 ~/ 开头：${value}" >&2; exit 2; fi
  printf '%s\n' "${value%/}"
}

run() {
  if $DRY_RUN; then printf 'DRY-RUN:'; printf ' %q' "$@"; printf '\n'; else "$@"; fi
}

default_install_root() {
  if [[ "${EUID}" -eq 0 ]]; then printf '/opt/ND\n'; else printf '%s/.local/share/ND\n' "${HOME}"; fi
}

default_command_dir() {
  if [[ "${EUID}" -eq 0 ]]; then printf '/usr/local/bin\n'; else printf '%s/.local/bin\n' "${HOME}"; fi
}

show_donation() {
  local installed_python="${INSTALL_ROOT:-}/venv/bin/python"
  if [[ -x "${installed_python}" ]]; then
    "${installed_python}" -m streamgrab.donate
  elif [[ -x "${SOURCE_DIR}/.venv/bin/python" ]] && "${SOURCE_DIR}/.venv/bin/python" -c 'import qrcode' >/dev/null 2>&1; then
    PYTHONPATH="${SOURCE_DIR}/src" "${SOURCE_DIR}/.venv/bin/python" -m streamgrab.donate
  elif [[ -f "${SOURCE_DIR}/donate.txt" ]]; then
    command cat "${SOURCE_DIR}/donate.txt"
  else
    echo "感谢支持 ${PRODUCT_NAME} / ND！"
    echo "微信：https://payapp.wechatpay.cn/sjt/qr/AQEQ9PnYyuHotIDyr71jOuTs"
    echo "支付宝：https://qr.alipay.com/tsx19783zphnbqnd04xkcec"
    echo "安装完成后运行 nd donate 可显示 ASCII 收款码。"
  fi
}

if [[ -z "${ACTION}" && -z "${INSTALL_DIR_ARG}" && -t 0 ]]; then
  printf '\n╔════════════════════════════════╗\n'
  printf '║       Number download / ND     ║\n'
  printf '╠════════════════════════════════╣\n'
  printf '║  1. 安装或升级                 ║\n'
  printf '║  2. 卸载                       ║\n'
  printf '║  3. 打赏支持                   ║\n'
  printf '║  0. 退出                       ║\n'
  printf '╚════════════════════════════════╝\n'
  read -r -p "请选择 [0-3]：" choice
  case "${choice:-0}" in
    1) ACTION="install" ;;
    2) ACTION="uninstall" ;;
    3) INSTALL_ROOT="$(default_install_root)"; show_donation; exit 0 ;;
    0) exit 0 ;;
    *) echo "错误：无效选项。" >&2; exit 2 ;;
  esac
fi
ACTION="${ACTION:-install}"
DEFAULT_INSTALL="$(default_install_root)"

if [[ "${ACTION}" == "uninstall" ]]; then
  if [[ -t 0 ]]; then
    read -r -p "程序安装目录 [${DEFAULT_INSTALL}]：" entered
    INSTALL_ROOT="$(expand_path "${entered:-${DEFAULT_INSTALL}}")"
  else
    INSTALL_ROOT="$(expand_path "${INSTALL_DIR_ARG:-${DEFAULT_INSTALL}}")"
  fi
  META_FILE="${INSTALL_ROOT}/etc/install.toml"
  [[ -f "${META_FILE}" ]] || { echo "错误：未找到安装记录：${META_FILE}" >&2; exit 1; }
  readarray -t metadata < <(python3 - "${META_FILE}" <<'PY'
import sys, tomllib
with open(sys.argv[1], "rb") as f: data = tomllib.load(f)
print(data["output_root"]); print(data["command_path"])
PY
  )
  OUTPUT_ROOT="${metadata[0]}"; COMMAND_PATH="${metadata[1]}"
  echo "1. 卸载程序，保留配置、历史、profile、成品和分片"
  echo "2. 彻底删除程序、配置、历史、profile、成品和分片"
  echo "0. 取消"
  read -r -p "请选择 [0-2]：" uninstall_choice
  case "${uninstall_choice:-0}" in
    1) purge_flag=() ;;
    2)
      echo "即将永久删除：${INSTALL_ROOT}"
      echo "即将永久删除：${OUTPUT_ROOT}"
      read -r -p "请输入 DELETE 确认彻底删除：" confirmation
      [[ "${confirmation}" == "DELETE" ]] || { echo "已取消。"; exit 0; }
      purge_flag=(--purge)
      ;;
    0) exit 0 ;;
    *) echo "错误：无效选项。" >&2; exit 2 ;;
  esac
  PYTHONPATH="${SOURCE_DIR}/src" python3 -m streamgrab.uninstall --install-root "${INSTALL_ROOT}" --output-root "${OUTPUT_ROOT}" --command-path "${COMMAND_PATH}" "${purge_flag[@]}"
  echo "卸载完成。"
  exit 0
fi

if [[ "${EUID}" -eq 0 ]]; then echo "警告：不推荐以 root 安装或运行 ND；Chromium 将需要 --no-sandbox。"; fi

existing_install="$(expand_path "${INSTALL_DIR_ARG:-${DEFAULT_INSTALL}}")"
META_FILE="${existing_install}/etc/install.toml"
CURRENT_OUTPUT=""
CURRENT_COMMAND="nd"
if [[ -f "${META_FILE}" ]]; then
  readarray -t metadata < <(python3 - "${META_FILE}" <<'PY'
import sys, tomllib
with open(sys.argv[1], "rb") as f: data = tomllib.load(f)
print(data.get("output_root", "")); print(data.get("command_name", "nd"))
PY
  )
  CURRENT_OUTPUT="${metadata[0]}"; CURRENT_COMMAND="${metadata[1]}"
fi

if $RECONFIGURE || [[ -z "${INSTALL_DIR_ARG}" && ! -f "${META_FILE}" ]]; then
  if [[ -t 0 ]]; then
    read -r -p "程序安装目录 [${existing_install}]：" entered
    INSTALL_ROOT="$(expand_path "${entered:-${existing_install}}")"
    default_output="${CURRENT_OUTPUT:-${HOME}/Downloads/ND}"
    read -r -p "成品下载目录 [${default_output}]：" entered
    OUTPUT_ROOT="$(expand_path "${entered:-${default_output}}")"
    read -r -p "命令名称 [${CURRENT_COMMAND}]：" entered
    COMMAND_NAME="${entered:-${CURRENT_COMMAND}}"
  else
    INSTALL_ROOT="${existing_install}"
    OUTPUT_ROOT="$(expand_path "${OUTPUT_DIR_ARG:-${CURRENT_OUTPUT:-${HOME}/Downloads/ND}}")"
    COMMAND_NAME="${COMMAND_NAME_ARG:-${CURRENT_COMMAND}}"
  fi
else
  INSTALL_ROOT="${existing_install}"
  OUTPUT_ROOT="$(expand_path "${OUTPUT_DIR_ARG:-${CURRENT_OUTPUT:-${HOME}/Downloads/ND}}")"
  COMMAND_NAME="${COMMAND_NAME_ARG:-${CURRENT_COMMAND}}"
fi

[[ "${COMMAND_NAME}" =~ ^[a-zA-Z][a-zA-Z0-9_-]{0,31}$ ]] || { echo "错误：命令名无效。" >&2; exit 2; }
if [[ "${INSTALL_ROOT}${OUTPUT_ROOT}" == *'"'* || "${INSTALL_ROOT}${OUTPUT_ROOT}" == *$'\n'* || "${INSTALL_ROOT}${OUTPUT_ROOT}" == *$'\r'* ]]; then
  echo "错误：路径不能包含引号或换行符。" >&2; exit 2
fi
for unsafe in / /opt /usr /home "${HOME}"; do
  [[ "${INSTALL_ROOT}" != "${unsafe}" && "${OUTPUT_ROOT}" != "${unsafe}" ]] || { echo "错误：拒绝使用危险目录 ${unsafe}" >&2; exit 2; }
done
[[ "${INSTALL_ROOT}" != "${OUTPUT_ROOT}" ]] || { echo "错误：安装目录和下载目录不能相同。" >&2; exit 2; }

missing_packages=()
command -v python3 >/dev/null 2>&1 || missing_packages+=(python3)
python3 -m venv --help >/dev/null 2>&1 || missing_packages+=(python3-venv)
command -v git >/dev/null 2>&1 || missing_packages+=(git)
command -v curl >/dev/null 2>&1 || missing_packages+=(curl)
command -v chromium >/dev/null 2>&1 || missing_packages+=(chromium)
command -v xvfb-run >/dev/null 2>&1 || missing_packages+=(xvfb)
command -v ffmpeg >/dev/null 2>&1 || missing_packages+=(ffmpeg)
dpkg-query -W -f='${Status}' fonts-noto-cjk 2>/dev/null | grep -q 'install ok installed' || missing_packages+=(fonts-noto-cjk)
dpkg-query -W -f='${Status}' ca-certificates 2>/dev/null | grep -q 'install ok installed' || missing_packages+=(ca-certificates)
if [[ ${#missing_packages[@]} -gt 0 ]]; then
  echo "需要安装系统依赖：${missing_packages[*]}"
  [[ -t 0 ]] || { echo "错误：非交互模式缺少系统依赖。" >&2; exit 1; }
  read -r -p "是否使用管理员权限安装？ [Y/n] " answer
  [[ "${answer,,}" != "n" && "${answer,,}" != "no" ]] || exit 1
  if [[ "${EUID}" -eq 0 ]]; then admin=(); elif command -v sudo >/dev/null 2>&1; then admin=(sudo); else
    echo "错误：当前用户没有 sudo，请管理员安装：${missing_packages[*]}" >&2; exit 1
  fi
  run "${admin[@]}" apt-get update
  run "${admin[@]}" apt-get install -y --no-install-recommends "${missing_packages[@]}"
fi

COMMAND_DIR="$(default_command_dir)"
COMMAND_PATH="${COMMAND_DIR}/${COMMAND_NAME}"
existing_command="$(command -v "${COMMAND_NAME}" 2>/dev/null || true)"
if [[ -e "${COMMAND_PATH}" ]] && ! grep -q 'ND_MANAGED_ENTRY' "${COMMAND_PATH}" 2>/dev/null; then
  echo "错误：命令路径已存在且不属于 ND：${COMMAND_PATH}" >&2; exit 1
fi
if [[ -n "${existing_command}" && "${existing_command}" != "${COMMAND_PATH}" ]] && ! grep -q 'ND_MANAGED_ENTRY' "${existing_command}" 2>/dev/null; then
  echo "错误：命令 ${COMMAND_NAME} 已被占用：${existing_command}" >&2; exit 1
fi

run install -d -m 0755 "${INSTALL_ROOT}" "${INSTALL_ROOT}/app" "${INSTALL_ROOT}/etc" "${INSTALL_ROOT}/tools" "${INSTALL_ROOT}/diagnostics" "${COMMAND_DIR}" "${OUTPUT_ROOT}" "${OUTPUT_ROOT}/.data"
run install -d -m 0700 "${INSTALL_ROOT}/profile" "${INSTALL_ROOT}/profile/chromium"
run install -m 0644 "${SOURCE_DIR}/pyproject.toml" "${INSTALL_ROOT}/app/pyproject.toml"
run install -m 0644 "${SOURCE_DIR}/README.md" "${INSTALL_ROOT}/app/README.md"
run install -m 0644 "${SOURCE_DIR}/LICENSE" "${INSTALL_ROOT}/app/LICENSE"
run install -m 0644 "${SOURCE_DIR}/donate.txt" "${INSTALL_ROOT}/app/donate.txt"
run install -m 0755 "${SOURCE_DIR}/update.sh" "${INSTALL_ROOT}/update.sh"
if ! $DRY_RUN; then cp -a "${SOURCE_DIR}/src" "${INSTALL_ROOT}/app/"; fi

if [[ ! -x "${INSTALL_ROOT}/venv/bin/python" ]]; then run python3 -m venv "${INSTALL_ROOT}/venv"; fi
run "${INSTALL_ROOT}/venv/bin/python" -m pip install --upgrade pip
run "${INSTALL_ROOT}/venv/bin/python" -m pip install "${INSTALL_ROOT}/app"

CONFIG_FILE="${INSTALL_ROOT}/etc/config.toml"
if [[ ! -e "${CONFIG_FILE}" ]] && ! $DRY_RUN; then
  cat >"${CONFIG_FILE}" <<EOF
default_output = "${OUTPUT_ROOT}"
downloader_path = "${INSTALL_ROOT}/tools/N_m3u8DL-RE"
extractor_proxy = ""
timeout_seconds = 20
last_update_check = ""
chromium_path = "/usr/bin/chromium"
browser_profile = "${INSTALL_ROOT}/profile/chromium"
diagnostics_dir = "${INSTALL_ROOT}/diagnostics"
temp_root = "${OUTPUT_ROOT}/.data"
locale = "zh-CN"
page_timeout_ms = 45000
search_wait_ms = 5000
capture_timeout_ms = 30000
m3u8_preferred_domain = "mushroomtrack.com"
allow_m3u8_fallback = false
allow_root_no_sandbox = $([[ "${EUID}" -eq 0 ]] && echo true || echo false)
download_threads = 8
EOF
  chmod 0600 "${CONFIG_FILE}"
elif $RECONFIGURE && ! $DRY_RUN; then
  ND_CONFIG_DIR="${INSTALL_ROOT}/etc" ND_DATA_DIR="${INSTALL_ROOT}" ND_NEW_OUTPUT="${OUTPUT_ROOT}" ND_NEW_ROOT="${INSTALL_ROOT}" "${INSTALL_ROOT}/venv/bin/python" - <<'PY'
import os
from dataclasses import replace
from streamgrab.config import load_config, save_config
c = load_config()
root, output = os.environ["ND_NEW_ROOT"], os.environ["ND_NEW_OUTPUT"]
save_config(replace(c, default_output=output, downloader_path=f"{root}/tools/N_m3u8DL-RE", browser_profile=f"{root}/profile/chromium", diagnostics_dir=f"{root}/diagnostics", temp_root=f"{output}/.data"))
PY
fi

if ! $DRY_RUN; then
  cat >"${INSTALL_ROOT}/etc/install.toml" <<EOF
install_root = "${INSTALL_ROOT}"
output_root = "${OUTPUT_ROOT}"
command_name = "${COMMAND_NAME}"
command_path = "${COMMAND_PATH}"
repo_url = "${REPO_URL}"
EOF
  chmod 0600 "${INSTALL_ROOT}/etc/install.toml"
fi

if [[ ! -x "${INSTALL_ROOT}/tools/N_m3u8DL-RE" ]] && ! $DRY_RUN; then
  ND_CONFIG_DIR="${INSTALL_ROOT}/etc" ND_DATA_DIR="${INSTALL_ROOT}" "${INSTALL_ROOT}/venv/bin/python" -c 'from streamgrab.tools import fetch_latest_release, install_release; print(install_release(fetch_latest_release(timeout=60), timeout=180))'
fi

if ! $DRY_RUN; then
  cat >"${COMMAND_PATH}" <<EOF
#!/usr/bin/env bash
# ND_MANAGED_ENTRY
set -Eeuo pipefail
export ND_CONFIG_DIR="${INSTALL_ROOT}/etc"
export ND_DATA_DIR="${INSTALL_ROOT}"
exec xvfb-run -a -s "-screen 0 1365x768x24" "${INSTALL_ROOT}/venv/bin/nd" "\$@"
EOF
  chmod 0755 "${COMMAND_PATH}"
fi

if [[ "${SOURCE_DIR}" != "${INSTALL_ROOT}/source" && ! -d "${INSTALL_ROOT}/source/.git" ]] && ! $DRY_RUN; then
  git clone --branch main --single-branch "${REPO_URL}" "${INSTALL_ROOT}/source"
fi

echo "安装/升级完成。命令：${COMMAND_PATH}"
if [[ ":${PATH}:" != *":${COMMAND_DIR}:"* ]]; then echo "提示：${COMMAND_DIR} 不在 PATH，请加入：export PATH=\"${COMMAND_DIR}:\$PATH\""; fi
echo "运行检查：${COMMAND_NAME} doctor"
