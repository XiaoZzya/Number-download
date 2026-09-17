from pathlib import Path


def test_installer_targets_debian_layout_and_safe_command_conflict():
    script = Path("install.sh").read_text(encoding="utf-8")
    assert "'/opt/ND" in script
    assert "Downloads/ND" in script
    assert 'COMMAND_PATH="${COMMAND_DIR}/${COMMAND_NAME}"' in script
    assert "command -v" in script
    assert "rm -rf" not in script
    assert "curl | bash" not in script
    assert "1. 安装或升级" in script
    assert "2. 卸载" in script
    assert "3. 打赏支持" in script
    assert 'printf \'/opt/ND' in script
    assert '.local/share/ND' in script
    assert '.local/bin' in script


def test_installer_keeps_profile_and_config_on_reinstall():
    script = Path("install.sh").read_text(encoding="utf-8")
    assert 'if [[ ! -e "${CONFIG_FILE}" ]]' in script
    assert '"${INSTALL_ROOT}/profile/chromium"' in script
    assert "ND_CONFIG_DIR" in script


def test_updater_uses_fixed_repo_and_safe_fast_forward():
    script = Path("update.sh").read_text(encoding="utf-8")
    assert 'REPO_URL="https://github.com/XiaoZzya/Number-download.git"' in script
    assert 'SOURCE_ROOT="${APP_ROOT}/source"' in script
    assert "merge --ff-only" in script
    assert "status --porcelain" in script
    assert "rm -rf" not in script
    assert "curl | bash" not in script
    assert "1. 根据当前配置升级" in script
    assert "2. 重新配置后升级" in script


def test_installer_installs_updater_and_git():
    script = Path("install.sh").read_text(encoding="utf-8")
    assert "missing_packages+=(git)" in script
    assert '"${SOURCE_DIR}/update.sh" "${INSTALL_ROOT}/update.sh"' in script


def test_uninstall_requires_explicit_purge_confirmation():
    script = Path("install.sh").read_text(encoding="utf-8")
    assert "保留配置、历史、profile、成品和分片" in script
    assert "彻底删除程序、配置、历史、profile、成品和分片" in script
    assert '[[ "${confirmation}" == "DELETE" ]]' in script
