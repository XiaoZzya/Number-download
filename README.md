# Number download

番号下载器，根据车牌/番号，搜索并下载合并

Number download（命令名 `nd`）是面向 Debian 13 x86_64 无桌面服务器的交互式下载编排工具。它使用 Xvfb 中的 Chromium 定位公开作品页面并捕获公开 HLS 地址，再调用 [`N_m3u8DL-RE`](https://github.com/nilaoda/N_m3u8DL-RE) 下载和混流。

> 仅用于你有权访问和下载的内容。ND 不自动登录、不导出 Cookie、不解决验证码，也不绕过 DRM、付费墙或访问控制。

## 推荐环境

- Debian 13 (trixie) x86_64
- 推荐普通用户安装和运行
- Chromium + Xvfb，无需桌面环境
- Python 3.11+

普通用户运行 Chromium 会保留沙箱。root 模式会显示安全警告并使用 `--no-sandbox`，不推荐日常使用。

## 一键部署

### 普通用户（推荐）

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/XiaoZzya/Number-download.git "$HOME/.local/share/ND/source"
"$HOME/.local/share/ND/source/install.sh"
```

如果当前用户不能执行第一行，请让管理员预装 `git`，然后以普通用户执行后两行。安装器发现其他系统依赖缺失时，会询问是否使用 `sudo apt-get` 安装；没有 sudo 时会显示需要管理员执行的包列表。

### root（不推荐）

```bash
apt-get update && apt-get install -y git
git clone https://github.com/XiaoZzya/Number-download.git /opt/ND/source
/opt/ND/source/install.sh
```

安装菜单：

```text
1. 安装
2. 卸载
3. 打赏支持
0. 退出
```

普通用户默认值：

```text
程序：~/.local/share/ND
成品：~/Downloads/ND
命令：~/.local/bin/nd
配置：~/.local/share/ND/etc/config.toml
profile：~/.local/share/ND/profile/chromium
```

root 默认值：

```text
程序：/opt/ND
成品：/root/Downloads/ND
命令：/usr/local/bin/nd
```

所有路径都能在安装时修改。非交互安装示例：

```bash
./install.sh --install-dir "$HOME/.local/share/ND" \
  --output-dir "$HOME/Downloads/ND" --command-name nd
```

从早期 StreamGrab 版本迁移时，可以继续选择命令名 `d`。安装器只会接管带有旧版 `STREAMGRAB_MANAGED_ENTRY` 或新版 `ND_MANAGED_ENTRY` 标记的入口，不会覆盖其他程序创建的同名命令。

安装器不会静默修改 shell 配置。如果 `~/.local/bin` 不在 PATH，会显示需要添加的命令。

## 使用

```bash
nd IPX-850
nd 121914-760
nd 河北彩花
nd https://jable.tv/videos/ipx-850/
nd IPX-850 --quality 1080p
nd IPX-850 --threads 12
nd doctor
nd history --limit 20
nd donate
nd update
nd update-tools
```

番号输入会优先打开精确作品页；页面不存在或输入普通关键字时才进入搜索并显示选择菜单。选择作品后直接解析，不再二次确认。

成品文件名直接使用网页标题，因为标题通常已经包含番号。ffprobe 验证成功后自动清理当前任务分片；下载、混流、验证失败或中断时保留现场。

## 更新

```bash
nd update
```

菜单提供：

```text
1. 根据当前配置升级
2. 重新配置后升级
0. 取消
```

更新器只接受本项目固定 GitHub 地址，使用 `git merge --ff-only`，并在源码存在未提交修改时拒绝覆盖。根据当前配置升级不会改变安装目录、下载目录、命令、历史或 profile。

正常运行 `nd` 命令时会先检查本项目是否有新版本。发现新版后提示是否更新，直接回车默认为“是”；选择拒绝或网络检查失败不会阻止原命令继续运行。非交互环境只提示并继续，不会擅自更新。

`nd update-tools` 只更新 `N_m3u8DL-RE`。

## 卸载

再次运行源码目录中的 `install.sh`，选择“卸载”：

```text
1. 卸载程序，保留配置、历史、profile、成品和分片
2. 彻底删除程序、配置、历史、profile、成品和分片
0. 取消
```

彻底删除会列出安装目录与下载目录，并要求输入大写 `DELETE`。卸载器拒绝删除 `/`、用户家目录、`/opt`、`/usr`、`/home`、`/root`、符号链接和挂载点。

## 常用参数

- `--quality best|720p|1080p`：跳过画质询问。
- `--threads N`：临时指定分片并发数；默认 8。
- `--output DIR`：临时覆盖成品目录。
- `--downloader PATH`：临时指定 `N_m3u8DL-RE`。
- `--extractor-proxy URL`：仅用于 Chromium 和播放列表检查。
- `--diagnose`：失败时显示诊断文件位置。
- `--dry-run`：只显示脱敏下载命令。
- `--no-history`：不保存本次历史。

## 验证页与隐私

程序会等待普通 JavaScript 检查。页面仍要求验证码或人工验证时会停止，不尝试解决或绕过。最近一次失败诊断只包含阶段、HTTP状态、脱敏URL和截图，不保存 Cookie、完整 HTML、m3u8 查询参数或代理认证信息。

## 开发与测试

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest
```

项目采用 MIT License。

## 打赏支持

如果这个项目对你有帮助，欢迎请作者喝杯咖啡。

<p align="center">
  <img src="assets/wechat-donate.jpg" alt="微信支付收款码" height="260">
  &nbsp;&nbsp;
  <img src="assets/alipay-donate.png" alt="支付宝收款码" height="260">
</p>
