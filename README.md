# Windfiles Download Skill

Windfiles 云盘自动下载工具 - OpenClaw Skill

## 功能

- 自动解析分享页面，提取下载链接
- 检测冷却时间限制
- 使用 agent-browser 自动化下载流程
- 支持自定义输出目录

## 安装

```bash
openclaw skills install https://github.com/mtsocom2000/windfiles-download
```

## 使用

```bash
# 基本用法
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --use-browser

# 指定输出目录
python3 {baseDir}/scripts/windfiles_download.py "https://windfiles.com/share/xxxxxx" --output-dir ./downloads --use-browser
```

## 参数

| 参数 | 说明 |
|------|------|
| `url` | Windfiles 分享链接 |
| `--output-dir, -o` | 输出目录，默认 `~/Downloads/windfiles` |
| `--skip-wait` | 跳过倒计时等待 |
| `--use-browser` | 使用 agent-browser 进行下载 |

## 限制

- 免费用户每天只能下载 2 个文件
- 下载后有 10 分钟冷却时间
- 免费下载速度限制为 50 KB/s

## 依赖

- Python 3.x
- agent-browser（可选）

## License

MIT