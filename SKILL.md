---
name: windfiles-download
description: "Windfiles 云盘文件下载工具。Use when 需要从 windfiles.com 下载文件 / 用户提供了 windfiles 分享链接 / 下载 torrent 文件。自动解析分享页面、等待倒计时、下载文件。会检测并报告冷却时间等错误。"
---

# Windfiles Download

Windfiles 云盘自动下载工具。

## 功能

- 解析分享页面，提取下载链接
- **检测冷却时间限制（10分钟内不能重复下载）**
- 自动等待倒计时（60-90秒）
- 支持免费慢速下载和 VIP 快速下载
- 自动保存到指定目录
- **详细的错误报告**

## 使用方法

### 基本用法

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx"
```

### 指定输出目录

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --output-dir ./downloads
```

### 跳过倒计时等待

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --skip-wait
```

### 使用浏览器模式

当直接下载失败时，使用 agent-browser 进行交互式下载：

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --use-browser
```

### 使用代理

```bash
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --proxy "http://127.0.0.1:7890"
```

## 参数说明

| 参数 | 说明 |
|------|------|
| `url` | Windfiles 分享链接（必填） |
| `--output-dir, -o` | 输出目录，默认 `~/Downloads` |
| `--skip-wait` | 跳过倒计时等待 |
| `--use-browser` | 使用 agent-browser 进行下载 |
| `--proxy` | 使用代理服务器 |

## 工作流程

1. **解析分享页面** — 提取文件名、文件大小、下载链接
2. **检测冷却时间** — 检查是否有“10分钟内不能下载”提示
3. **获取免费下载链接** — 从页面源码提取 `/download/slow/?dl=...`
4. **等待倒计时** — 免费下载需要等待 60-90 秒
5. **访问下载页面** — 获取实际的下载按钮
6. **再次检测冷却时间** — 点击下载后检查是否有限制提示
7. **下载文件** — 保存到指定目录

## 错误处理

| 错误类型 | 说明 | 解决方案 |
|----------|------|----------|
| `COOLDOWN_ACTIVE` | 10分钟冷却时间内 | 等待冷却结束或使用代理 |
| `DAILY_LIMIT` | 每日下载次数用尽 | 等到明天或更换 IP |
| `DOWNLOAD_FAILED` | 下载失败 | 使用 `--use-browser` 模式 |
| `LINK_NOT_FOUND` | 找不到下载链接 | 检查链接是否有效 |

## 注意事项

- 免费用户每天只能下载 2 个文件
- 免费下载速度限制为 50 KB/s
- 下载需要等待 60-90 秒倒计时
- **10分钟冷却时间**：下载完成后 10 分钟内不能再次下载
- 如果遇到冷却时间限制，可以使用 `--proxy` 参数切换 IP

## 依赖

- Python 3.x
- `agent-browser`（可选，用于 `--use-browser` 模式）