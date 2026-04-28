# LocalTool

Personal CLI toolkit — a collection of small utilities bundled into a single installable package.

个人 CLI 工具箱 — 将多个小工具打包为单个可安装的 Python 软件包。

## Installation / 安装

```bash
uv tool install .
```

Or from source / 或从源码安装：

```bash
git clone <repo-url> && cd LocalTool
uv sync
```

Requires Python >= 3.12.

## Commands / 命令

### `gt` — Git Tree / Git 目录树

Display a tree view of all tracked files in the current git repository.

以树状图展示当前仓库中所有 Git 跟踪的文件。

```bash
gt
```

### `hash` — File / Text Hashing / 文件文本哈希

Compute cryptographic hashes for files or raw text.

计算文件或文本的加密哈希值。

```bash
hash -f README.md                  # MD5 of a file / 文件的 MD5
hash -a sha256 -f README.md        # SHA-256
hash -r "hello"                    # hash raw text / 原文哈希
hash -f a.txt -f b.txt             # multiple inputs / 多个输入
```

| Flag / 参数 | Description / 说明 |
|-------------|--------------------|
| `-a`, `--algorithm` | Hash algorithm, default: `md5` / 哈希算法 |
| `-f`, `--file` | File path (repeatable) / 文件路径（可重复） |
| `-r`, `--raw` | Raw text to hash (repeatable) / 原文文本（可重复） |
| `-o`, `--output` | Write result to file / 输出到文件 |

### `httpd` — HTTP Request Logger / HTTP 请求日志

Start a minimal HTTP server that logs every incoming request to stdout.

启动一个最小化的 HTTP 服务器，将每个请求记录到标准输出。

```bash
httpd              # listen on :8080 / 监听 8080 端口
httpd -p 3000      # listen on :3000 / 监听 3000 端口
```

### `ip` — IP & Geolocation / IP 及归属地

Show local intranet IP and public IP with geolocation details (city, region, ISP).

显示本地内网 IP 和公网 IP，以及归属地信息（城市、地区、运营商）。

```bash
ip
```

### `ll` — File Listing / 文件列表

List files with details — permissions, human-readable size, modification time — similar to `ls -lah`.

列出文件的详细信息 — 权限、可读大小、修改时间 — 类似 `ls -lah`。

```bash
ll
ll /some/directory
```

### `email` — Email Client / 邮件客户端 (GUI)

A PyQt6-based desktop email client.

基于 PyQt6 的桌面邮件客户端。

**Features / 功能：**

- **Inbox & Sent / 收件箱与已发送** — folder tabs with cached switching / 文件夹标签切换，使用缓存加速
- **Unread filter / 未读筛选** — toggle to show only unread messages / 一键只看未读邮件
- **Search / 搜索** — real-time filtering by sender, recipient, or subject / 实时按发件人、收件人、主题筛选
- **Compose & Send / 撰写与发送** — polished compose dialog with monospace editor / 精致的撰写弹窗
- **Master password / 主密码** — AES-encrypted configuration on disk / AES 加密存储配置
- **Loading states / 加载动画** — spinner animations during fetch / 数据加载时的旋转动画

```bash
email
```

Configuration is encrypted with a master password and stored locally. Supports standard IMAP/SMTP providers.

配置文件使用主密码加密存储在本地，支持标准的 IMAP/SMTP 邮件服务商。

### `localtool` — Dispatcher / 调度器

Run as a meta-command to discover available tools:

作为元命令运行，发现和管理所有可用工具：

```bash
localtool           # list all commands / 列出所有命令
localtool ip        # same as `ip` directly / 等价于直接运行 `ip`
```

## Architecture / 架构

Tools extend `BaseTool` (in `localtool/core.py`) and register automatically via `__init_subclass__`. The dispatcher (`localtool/main.py`) auto-discovers modules in the `localtool/` package at startup.

工具继承 `BaseTool`（位于 `localtool/core.py`），通过 `__init_subclass__` 自动注册。调度器（`localtool/main.py`）在启动时自动发现 `localtool/` 包下的所有模块。
