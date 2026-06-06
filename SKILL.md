---
name: windfiles-download
description: "Windfiles 云盘文件下载工具。Use when 需要从 windfiles.com 下载文件 / 用户提供了 windfiles 分享链接 / 下载 torrent 文件。自动解析分享页面、等待倒计时、下载文件。支持住宅代理绕过 IP 级限制（冷却 + 每日限制）。"
---

# Windfiles Download

Windfiles 云盘自动下载工具。支持住宅代理，可完全绕过 windfiles 的 IP 级限制。

## 功能

- 解析分享页面，提取下载链接（从 JS `document.location` 提取）
- **检测冷却时间限制（10 分钟内不能重复下载，IP 级）**
- **检测每日下载限制（2 次/24h，IP 级）**
- 自动等待倒计时（60-90 秒）
- POST /download/jump + 跟随重定向到 dl.windfiles.com（最可靠的免费下载路径）
- 自动保存到指定目录
- **详细的错误报告**
- **默认使用 agent-browser 模式（提高下载成功率）**
- **支持重定向 URL 解析（如 javlibrary redirect.php）**
- **支持住宅代理下载（完全绕过 IP 级限制，包括冷却和每日限制）**
- **支持 RapidProxy 自动旋转 IP**

## 使用方法

### 基本用法

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx"
```

### 从重定向链接下载（如 javlibrary）

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://www.javlibrary.com/cn/redirect.php?url=https%3A%2F%2Fwindfiles.com%2Fshare%2Fxxxxxx"
```

脚本会自动从 `url` 参数中提取 windfiles 真实链接。

### 指定输出目录

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --output-dir ./downloads
```

### 跳过倒计时等待

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --skip-wait
```

### 禁用浏览器模式

默认启用 agent-browser 模式。如需使用传统下载方式（推荐配合代理使用）：

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --manual-browser
```

### 使用代理下载（绕过所有 IP 级限制）

Windfiles 对免费用户有 **10 分钟冷却 + 2 次/24h 的 IP 级**限制。
使用住宅代理切换 IP 即可完全绕过（已验证）。

#### RapidProxy 住宅代理（推荐，自动旋转 IP）

```bash
# 格式：--proxy-rapid "用户名:密码"
# 每次运行使用不同 IP，完全绕过冷却 + 每日限制
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --proxy-rapid "YOUR_USERNAME:YOUR_PASSWORD"

# 跳过倒计时，适合脚本批量
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --proxy-rapid "YOUR_USERNAME:YOUR_PASSWORD" --skip-wait
```

> **原理**：`--proxy-rapid` 将格式展开为 `http://用户名-residential-AS-session-<随机数值>-stime-3:密码@us.rapidproxy.io:5001`，每个 session ID 对应不同出口 IP。已验证：冷却 + 每日限制均为 IP 级，旋转 IP 即可绕过。

#### 自建代理 / Bright Data

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --proxy "http://user:pass@host:port"
```

### 显示当前出口 IP（用于调试）

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --show-ip
```

## 参数说明

| 参数 | 说明 |
|------|------|
| `url` | Windfiles 分享链接或重定向链接（必填） |
| `--output-dir, -o` | 输出目录，默认 `~/Downloads` |
| `--skip-wait` | 跳过倒计时等待 |
| `--manual-browser` | 禁用 browser 模式（默认启用） |
| `--proxy` | HTTP 代理地址，如 `http://user:pass@host:port` |
| `--proxy-rapid` | RapidProxy 快速配置，格式 `user:pass`，自动旋转 session |
| `--show-ip` | 下载前显示当前出口 IP |

## 工作流程

1. **解析 URL** — 从重定向链接中提取 windfiles 真实地址
2. **安装代理 + SSL** — 全局 proxy handler + 非验证 SSL context（确保重定向到 dl.windfiles.com 正常工作）
3. **显示出口 IP** — 可选，确认代理生效
4. **解析分享页面** — 从 JS `document.location = "/download/slow/?dl=..."` 提取 dl 参数
5. **POST /download/jump** — 发送 `btnAct=Start+Download+Now`，得到 302 重定向
6. **跟随重定向** — 提取 `Location: https://dl.windfiles.com?dl=...`，GET 下载实际文件
7. **检测限制** — 如果返回失败，检查是否冷却/每日限制触发
8. **保存文件** — 写入指定输出目录

## 错误处理

| 错误类型 | 说明 | 解决方案 |
|----------|------|----------|
| `COOLDOWN_ACTIVE` | 10 分钟冷却时间内（IP 级） | 用 `--proxy-rapid` 或 `--proxy` 切换 IP |
| `DAILY_LIMIT` | 每日下载次数用尽（2次/24h，IP 级） | 用 `--proxy-rapid` 或 `--proxy` 切换 IP |
| `DOWNLOAD_FAILED` | 下载失败 | 使用 browser 模式（默认已启用） |
| `LINK_NOT_FOUND` | 找不到下载链接 | 检查链接是否有效 |

## 已知限制与绕过能力

### IP 级限制（住宅代理可完全绕过 ✅）

| 限制 | 说明 | 绕过方式 | 验证状态 |
|------|------|----------|----------|
| 10 分钟冷却 | 同一 IP 下载后 10 分钟冷却 | 切换 IP | ✅ 已验证 |
| 2 次/24h | 同一 IP 每天限 2 次 | 切换 IP | ✅ 可绕（原理同冷却） |

### 非 IP 级限制（不可绕过 ❌）

无。已验证所有限制均为 IP 级。

## 注意事项

- 免费下载速度限制为 50 KB/s
- 下载默认需要等待 60-90 秒倒计时（可用 `--skip-wait` 跳过）
- **默认使用 agent-browser 模式**，提高下载成功率
- `--proxy` 和 `--proxy-rapid` 互斥，同时指定时 `--proxy-rapid` 优先
- 使用 `--manual-browser` 代理模式时，脚本自动设置全局非验证 SSL context，确保 `dl.windfiles.com` 的重定向正常工作

## 依赖

- Python 3.x
- `agent-browser`（默认使用）
