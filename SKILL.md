---
name: windfiles-download
description: "Windfiles 云盘文件下载工具。Use when 需要从 windfiles.com 下载文件 / 用户提供了 windfiles 分享链接 / 下载 torrent 文件。VPS/无桌面环境推荐使用 --manual-browser 模式。"
---

# Windfiles Download

Windfiles 云盘自动下载工具。支持住宅代理，可完全绕过 windfiles 的 IP 级限制。

## 功能

- 解析分享页面，提取下载链接（从 JS `document.location` 提取）
- **检测冷却时间限制（10 分钟内不能重复下载，IP 级）**
- **检测每日下载限制（2 次/24h，IP 级）**
- 自动等待倒计时（60-90 秒）
- POST /download/jump + 跟随重定向到 dl.windfiles.com（最可靠的免费下载路径）
- 自动保存到指定目录，从 `Content-Disposition` 头提取真实文件名
- **详细的错误报告**
- **两种下载模式**:
  - `--manual-browser`：纯 Python urllib 请求，无外部依赖，**推荐 VPS/服务器环境**
  - agent-browser（默认）：通过 Chrome 自动化完成下载，适合有桌面环境的机器
- **支持重定向 URL 解析**（如 javlibrary redirect.php）
- **支持住宅代理下载**（完全绕过 IP 级限制，包括冷却和每日限制）

## 模式选择

| 环境 | 推荐模式 | 说明 |
|------|----------|------|
| **VPS / 无桌面环境** | `--manual-browser` | 纯 Python，无 GUI/浏览器依赖，与 `--proxy` 配合使用 |
| **本地桌面 (有 Chrome)** | 默认 (agent-browser) | Chrome 自动化，点击按钮兼容性最好 |

**VPS 标准用法**（`--manual-browser` + `--proxy`）：

```bash
python3 {baseDir}/scripts/windfiles_download.py "<链接>" --manual-browser --proxy "http://YOUR_USER:YOUR_PASS@host:port"
```

## 使用方法

### VPS/服务器：推荐用法（manual-browser + 代理）

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://www.javlibrary.com/cn/redirect.php?url=..." --manual-browser --skip-wait --proxy "http://YOUR_USER:YOUR_PASS@host:port"
```

### 桌面环境：默认用法（agent-browser）

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx"
```

### 从重定向链接下载（如 javlibrary）

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://www.javlibrary.com/cn/redirect.php?url=..." --manual-browser --proxy "http://YOUR_USER:YOUR_PASS@host:port" --skip-wait
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

### 使用代理下载（绕过所有 IP 级限制）

Windfiles 对免费用户有 **10 分钟冷却 + 2 次/24h 的 IP 级**限制。
使用住宅代理切换 IP 即可完全绕过（已验证）。

#### RapidProxy 住宅代理（自建 session ID 旋转 IP）

```bash
# 每次运行用不同 session ID → 不同出口 IP，完全绕过冷却 + 每日限制
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --manual-browser --proxy "http://YOUR_USERNAME-residential-AS-session-12345678-stime-3:YOUR_PASSWORD@us.rapidproxy.io:5001"

# 跳过倒计时，适合脚本批量
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --manual-browser --proxy "http://YOUR_USERNAME-residential-AS-session-12345678-stime-3:YOUR_PASSWORD@us.rapidproxy.io:5001" --skip-wait
```

> **原理**：session ID 决定出口 IP，每次换不同 session ID 即可轮换 IP。已验证：冷却 + 每日限制均为 IP 级，旋转 IP 即可绕过。

#### 自建代理 / Bright Data

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --manual-browser --proxy "http://user:pass@host:port"
```

### 显示当前出口 IP（用于调试）

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --manual-browser --show-ip
```

## 参数说明

| 参数 | 说明 |
|------|------|
| `url` | Windfiles 分享链接或重定向链接（必填） |
| `--output-dir, -o` | 输出目录，默认 `~/Downloads` |
| `--skip-wait` | 跳过倒计时等待 |
| `--manual-browser` | **VPS 推荐**。禁用 agent-browser，纯 Python urllib 下载 |
| `--proxy` | HTTP 代理地址，如 `http://user:pass@host:port` |
| `--show-ip` | 下载前显示当前出口 IP |

> **VPS 推荐组合**：`--manual-browser --proxy "http://YOUR_USER:YOUR_PASS@host:port" --skip-wait`

## 工作流程

1. **解析 URL** — 从重定向链接中提取 windfiles 真实地址
2. **安装代理 + SSL** — 全局 proxy handler + 非验证 SSL context（确保重定向到 dl.windfiles.com 正常工作）
3. **显示出口 IP** — 可选，确认代理生效
4. **解析分享页面** — 从 JS `document.location = "/download/slow/?dl=..."` 提取 dl 参数
5. **POST /download/jump** — 发送 `btnAct=Start+Download+Now`，得到 302 重定向
6. **跟随重定向** — 提取 `Location: https://dl.windfiles.com?dl=...`，GET 下载实际文件
7. **提取文件名** — 从 `Content-Disposition: attachment; filename="REAL_NAME.torrent"` 获取真实文件名
8. **检测限制** — 如果返回失败，检查是否冷却/每日限制触发
9. **保存文件** — 写入指定输出目录

## 错误处理

| 错误类型 | 说明 | 解决方案 |
|----------|------|----------|
| `COOLDOWN_ACTIVE` | 10 分钟冷却时间内（IP 级） | 用 `--proxy` 切换 IP |
| `DAILY_LIMIT` | 每日下载次数用尽（2次/24h，IP 级） | 用 `--proxy` 切换 IP |
| `DOWNLOAD_FAILED` | 下载失败 | 尝试 `--manual-browser` 模式 |
| `LINK_NOT_FOUND` | 找不到下载链接 | 检查链接是否有效 |
| `ERR_CERT_AUTHORITY_INVALID` | agent-browser SSL 证书错误 | VPS 环境下使用 `--manual-browser` |

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
- **VPS 环境必须加 `--manual-browser`**（无 Chrome + 无桌面环境）
- **桌面环境**可以省略 `--manual-browser`，用默认 agent-browser 模式
- 使用 `--manual-browser` 模式时，脚本自动设置全局非验证 SSL context + ProxyHandler，确保 `dl.windfiles.com` 的重定向正常工作

## VPS 批量下载脚本示例

```bash
#!/bin/bash
# windfiles 批量下载（VPS 环境）
# 每次用不同 session ID 轮换出口 IP
PROXY_URL="http://YOUR_USERNAME-residential-AS-session-$(date +%s%N)-stime-3:YOUR_PASSWORD@us.rapidproxy.io:5001"

URLS=(
  "https://windfiles.com/share/xxxxxx"
  "https://windfiles.com/share/yyyyyy"
)

for url in "${URLS[@]}"; do
  python3 {baseDir}/scripts/windfiles_download.py "$url" \
    --manual-browser --proxy "$PROXY_URL" --skip-wait
done
```

## 依赖

- Python 3.x
- `agent-browser`（默认模式需要，`--manual-browser` 不需要）
