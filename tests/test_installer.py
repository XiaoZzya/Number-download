from pathlib import Path


def test_installer_targets_debian_layout_and_safe_command_conflict():
    script = Path("install.sh").read_text(encoding="utf-8")
    assert 'APP_ROOT="/data/dd"' in script
    assert 'OUTPUT_ROOT="/data/downloads/ss"' in script
    assert "chromium xvfb ffmpeg" in script
    assert 'ENTRY="/usr/local/bin/${COMMAND_NAME}"' in script
    assert "command -v" in script
    assert "rm -rf" not in script
    assert "curl | bash" not in script


def test_installer_keeps_profile_and_config_on_reinstall():
    script = Path("install.sh").read_text(encoding="utf-8")
    assert 'if [[ ! -e "${CONFIG_FILE}" ]]' in script
    assert '"${APP_ROOT}/profile/chromium"' in script
    assert "STREAMGRAB_CONFIG_DIR" in script


def test_updater_uses_fixed_repo_and_safe_fast_forward():
    script = Path("update.sh").read_text(encoding="utf-8")
    assert 'REPO_URL="https://github.com/XiaoZzya/Number-download.git"' in script
    assert 'SOURCE_ROOT="${APP_ROOT}/source"' in script
    assert "merge --ff-only" in script
    assert "status --porcelain" in script
    assert "rm -rf" not in script
    assert "curl | bash" not in script


def test_installer_installs_updater_and_git():
    script = Path("install.sh").read_text(encoding="utf-8")
    assert "curl git chromium" in script
    assert '"${SOURCE_DIR}/update.sh" "${APP_ROOT}/update.sh"' in script
