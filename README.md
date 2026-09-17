# StreamGrab 2.0

StreamGrab 是面向无桌面 Debian 13 服务器的交互式下载编排工具。输入番号、搜索关键字或作品页地址后，它通过 Xvfb 中的真实 Chromium 定位公开作品页、监听并验证 HLS 地址，再调用 [`N_m3u8DL-RE`](https://github.com/nilaoda/N_m3u8DL-RE) 下载和混流。

> 仅用于你有权访问和下载的内容。StreamGrab 不自动登录、不导出 Cookie、不处理验证码，也不绕过 DRM、付费墙或访问控制。

## 目标环境

- Debian 13 (trixie) x86_64
- root 运行
- Chromium + Xvfb，无需桌面环境
- 默认成品目录 `/data/downloads/ss`
- 默认短命令 `d`

用户已明确选择以 root + Chromium `--no-sandbox` 运行。该模式降低浏览器进程隔离能力，每次启动都会显示警告；不要访问不受信任的其他网站。

## 一键部署

Debian 13 x86_64 使用 root 执行。源码会保存在本机，可先审查脚本；不使用 `curl | bash`：

```bash
apt-get update && apt-get install -y git
git clone https://github.com/XiaoZzya/Number-download.git /data/dd/source
/data/dd/source/install.sh
```

以后更新程序只需：

```bash
d update
```

更新器只接受本项目的固定 GitHub 地址并使用快进合并；源码目录存在未提交修改时会拒绝覆盖。配置、历史、成品和 Chromium profile 都会保留。

## 本地源码安装

先把完整源码复制或克隆到服务器，检查 [`install.sh`](install.sh)，然后从源码目录运行：

```bash
chmod +x install.sh
./install.sh --dry-run
./install.sh
```

安装器只支持 Debian 13 x86_64，并执行以下工作：

- 通过 apt 安装 Chromium、Xvfb、ffmpeg、Python venv、CA 证书和中文字体。
- 程序安装到 `/data/dd/app`，Python环境放在 `/data/dd/venv`。
- 配置写入 `/data/dd/etc/config.toml`，重装时不会覆盖已有配置。
- Chromium持久 profile 保存到 `/data/dd/profile/chromium`。
- 从官方 GitHub Release 安装当前平台的 `N_m3u8DL-RE`。
- 创建 `/usr/local/bin/d`；若 `d` 已被占用，会显示现有路径并询问其他名称，不覆盖旧命令。

安装后检查：

```bash
d doctor
```

## 使用

```bash
d IPX-850
d ipx850
d https://jable.tv/videos/ipx-850/
d IPX-850 --quality 1080p
d IPX-850 --threads 12
d 河北彩花
d doctor
d history --limit 20
d update
d update-tools
```

标准流程：

1. 番号优先打开精确作品页；关键字或直达失败时进入搜索。
2. 搜索时展示匹配作品，选择后直接进入作品页。
3. 监听 request/response，优先捕获配置的主视频 CDN。
4. 展示清晰度，音频自动选择最佳轨道。
5. 使用 `N_m3u8DL-RE` 输出 MP4，全部字幕保存为独立 SRT。
6. ffprobe 验证视频流、时长、分辨率和大小。
7. 验证成功后自动清理本次分片；失败或中断时保留。

### 常用参数

- `--quality best|720p|1080p`：跳过画质询问。
- `--threads N`：临时指定分片下载并发数；默认 8。
- ffprobe 验证成功后自动清理本次任务目录；任何失败都会保留分片。
- `--output DIR`：临时覆盖成品目录。
- `--downloader PATH`：临时指定 `N_m3u8DL-RE`。
- `--extractor-proxy URL`：仅用于 Chromium 和播放列表检查；不允许在 URL 中嵌入账号密码。
- `--diagnose`：失败时额外显示诊断文件位置。
- `--dry-run`：完成解析和选择，只显示脱敏下载命令。
- `--no-history`：不保存本次简要历史。

## 目录与安全清理

```text
/data/dd/app                         程序
/data/dd/venv                        Python环境
/data/dd/etc/config.toml             配置
/data/dd/profile/chromium            持久浏览器profile
/data/dd/tools                       N_m3u8DL-RE
/data/dd/history.sqlite3             简要历史
/data/dd/diagnostics/latest.txt      最近一次失败诊断
/data/dd/diagnostics/latest.png      最近一次失败截图
/data/downloads/ss                   MP4与SRT成品
/data/downloads/ss/.data/<番号>      当前任务分片
```

清理仅在 ffprobe 验证成功后发生，并且目标必须是 `.data` 下名称等于当前规范化番号的直接子目录。程序拒绝清理：

- `.data` 基础目录本身；
- 其他番号目录；
- 符号链接、挂载点或路径穿越目标；
- 任何下载、混流、验证失败或被中断的任务。

清理失败只显示警告，不会删除已完成的 MP4/SRT。无交互终端时，验证成功后默认清理；验证失败始终保留现场。

## 验证页与诊断

程序会等待普通 JavaScript 检查。如果页面仍要求验证码或人工验证，程序停止，不尝试解决或绕过。最近一次失败会覆盖：

- `/data/dd/diagnostics/latest.txt`
- `/data/dd/diagnostics/latest.png`

诊断包含阶段、HTTP状态、脱敏URL和截图，不包含 Cookie、完整 HTML 或完整临时 m3u8。

## 配置

配置文件为 `/data/dd/etc/config.toml`，完整字段参考 [`config.example.toml`](config.example.toml)。常用字段包括 Chromium、profile、首选 CDN、输出与临时目录、页面超时、捕获超时和 `download_threads = 8`。成品文件名直接使用网页标题（标题通常已包含番号），不会再次拼接番号；重名时自动生成带序号的新名称。

`allow_m3u8_fallback = false` 表示只接受首选 CDN。确认站点更换主 CDN 后再修改 `m3u8_preferred_domain`，不要盲目开启备用流。

## 开发与测试

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest
```

测试使用本地 fixture、模拟浏览器事件和公开授权 HLS，不访问或下载第三方受限内容。
