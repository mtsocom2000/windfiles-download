# Windfiles Download

Windfiles 云盘自动下载工具。支持住宅代理，可绕过 windfiles 的 **IP 级** 下载限制。

## 功能

- **一键下载** — 解析分享页，提取下载参数，等待倒计时，下载文件
- **自动提取文件名** — 从 `Content-Disposition` 响应头获取真实文件名
- **支持重定向 URL** — 可解析 javlibrary 等站点的 `redirect.php` 链接
- **冷却检测** — 检测 10 分钟冷却期、每日下载限制等状态
- **两种下载模式**:
  - `agent-browser`（默认）— 通过 Chrome 自动化完成下载，兼容性最好
  - `manual-browser` — 纯 Python urllib 请求，适合配合代理
- **住宅代理绕过限制** — 通过住宅代理切换 IP，绕过 windfiles 的 IP 级限制
- **RapidProxy 一键配置** — 自动生成随机 session，每次下载使用不同出口 IP

## 安装

```bash
openclaw skills install https://github.com/mtsocom2000/windfiles-download
```

或者直接 git clone：

```bash
git clone https://github.com/mtsocom2000/windfiles-download.git
cd windfiles-download
```

## 快速使用

### 模式选择

| 环境 | 推荐模式 | 命令 |
|------|----------|------|
| **VPS / 无桌面** | `--manual-browser` | 加此参数，纯 Python 下载 |
| **本地桌面 (有 Chrome)** | 默认 (agent-browser) | 不加参数，Chrome 自动化 |

### VPS 推荐用法（manual-browser + 代理）

```bash
python3 scripts/windfiles_download.py "https://www.javlibrary.com/cn/redirect.php?url=..." \
  --manual-browser --skip-wait --proxy-rapid "YOUR_USER:YOUR_PASS"
```

### 桌面环境：默认用法（agent-browser）

```bash
python3 scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx"
```

### 从重定向链接下载（如 javlibrary）

```bash
python3 scripts/windfiles_download.py "https://www.javlibrary.com/cn/redirect.php?url=..." \
  --manual-browser --proxy-rapid "YOUR_USER:YOUR_PASS" --skip-wait
```

### 跳过倒计时

```bash
python3 scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --skip-wait
```

### 指定输出目录

```bash
python3 scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --output-dir ~/Downloads
```

## 代理使用（绕过下载限制）

Windfiles 对免费用户有以下限制（均为 IP 级别，已验证）：

| 限制 | 说明 | 绕过方式 |
|------|------|----------|
| 10 分钟冷却 | 同一 IP 下载后需冷却 10 分钟 | 切换 IP |
| 2 次/24h | 同一 IP 每天限 2 次下载 | 切换 IP |

使用住宅代理旋转 IP，可完全绕过以上限制。

### 方式一：RapidProxy（推荐，自动旋转 IP）

使用 `--proxy-rapid` 参数，提供 RapidProxy 的 `用户名:密码`：

```bash
# 格式：--proxy-rapid "用户名:密码"
python3 scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" \
  --proxy-rapid "YOUR_USERNAME:YOUR_PASSWORD" \
  --manual-browser --skip-wait
```

脚本会自动将 `"用户名:密码"` 展开为带随机 session ID 的完整代理 URL：

```
http://用户名-residential-AS-session-<随机值>-stime-3:密码@us.rapidproxy.io:5001
```

每次运行 session 值不同 → 出口 IP 不同 → 不触发任何 IP 级限制。

> **RapidProxy 测试参数格式**（替换为你的实际账号）：
> ```
> --proxy-rapid "your_username:your_password"
> ```
> 注意不要误提交包含实际密码的命令到公开文档或版本控制。

### 方式二：通用 HTTP 代理

```bash
# 自建代理
python3 scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" \
  --proxy "http://user:pass@proxy_ip:port"

# Bright Data 住宅代理
python3 scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" \
  --proxy "http://brd-customer-h_xxxxx-zone-xxxx:password@brd.superproxy.io:33335"
```

### 下载前确认代理 IP

```bash
python3 scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" \
  --proxy-rapid "YOUR_USERNAME:YOUR_PASSWORD" --show-ip --skip-wait
```

输出：

```
🔌 使用代理：http://...@us.rapidproxy.io:5001
🌐 出口 IP：188.3.186.251
```

### 批量下载示例

```bash
URLS=(
  "https://windfiles.com/share/xxxxxx"
  "https://windfiles.com/share/yyyyyy"
  "https://windfiles.com/share/zzzzzz"
)

for url in "${URLS[@]}"; do
  python3 scripts/windfiles_download.py "$url" \
    --proxy-rapid "YOUR_USERNAME:YOUR_PASSWORD" \
    --manual-browser --skip-wait
done
```

> 每次循环使用不同 session ID（不同出口 IP），不会触发任何限制。

## 参数说明

| 参数 | 说明 |
|------|------|
| `url` | Windfiles 分享链接或重定向链接（必填） |
| `--output-dir, -o` | 输出目录，默认 `~/Downloads` |
| `--skip-wait` | 跳过倒计时等待 |
| `--manual-browser` | **VPS 推荐**。禁用 agent-browser，纯 Python urllib 下载 |
| `--proxy` | HTTP 代理地址，如 `http://user:pass@host:port` |
| `--proxy-rapid` | RapidProxy 快速配置，格式 `用户名:密码`，自动旋转 session |
| `--show-ip` | 下载前显示当前出口 IP |

> **VPS 推荐组合**：`--manual-browser --proxy-rapid "YOUR_USER:YOUR_PASS" --skip-wait`
>
> `--proxy` 和 `--proxy-rapid` 互斥，同时指定时 `--proxy-rapid` 优先。

## 下载流程（manual-browser 模式）

```
分享页 URL
    │
    ├── 提取 dl 参数（从 JS: document.location = "/download/slow/?dl=xxx"）
    │
    ├── POST /download/jump?dl=xxx (btnAct=Start+Download+Now)
    │   └── 302 → Location: https://dl.windfiles.com?dl=xxx
    │
    ├── GET https://dl.windfiles.com?dl=xxx
    │   └── 200 OK, Content-Disposition: attachment; filename="REAL_NAME.torrent"
    │
    └── 保存为 REAL_NAME.torrent
```

## 错误处理

| 错误 | 原因 | 解决 |
|------|------|------|
| `服务器返回 HTML` | 触发了限制（冷却/每日限制） | 使用 `--proxy-rapid` 切换 IP |
| `POST 下载失败 HTTP 302` | 免费下载限制触发 | 切换 IP 或等冷却期过 |
| `agent-browser SSL 错误` | windfiles 证书问题 | 加 `--manual-browser` 改用 urllib |

## 关于下载限制（已验证）

通过实际测试确认：

- **10 分钟冷却**：IP 级别。同一 IP 下载后 10 分钟内不能再次下载。
  **住宅代理切换 IP 即可绕过。**
- **2 次/24h 限制**：IP 级别。同一 IP 每天最多 2 次免费下载。
  **住宅代理切换 IP 即可绕过。**
- 两个限制均可在单个 session 内通过 `--proxy-rapid` 自动旋转 IP 完全绕过。

## VPS 批量下载脚本示例

```bash
#!/bin/bash
# windfiles 批量下载（VPS 环境）
RAPID_CRED="YOUR_USERNAME:YOUR_PASSWORD"

URLS=(
  "https://windfiles.com/share/xxxxxx"
  "https://windfiles.com/share/yyyyyy"
)

for url in "${URLS[@]}"; do
  python3 scripts/windfiles_download.py "$url" \
    --manual-browser --proxy-rapid "$RAPID_CRED" --skip-wait
done
```

## 依赖

- Python 3.x
- `agent-browser`（默认模式需要，`--manual-browser` 不需要）

## License

MIT
