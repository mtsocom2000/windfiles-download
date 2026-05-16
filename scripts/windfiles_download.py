#!/usr/bin/env python3
"""
Windfiles Cloud Drive 下载脚本

功能：
1. 解析分享页面，提取下载链接
2. 自动等待倒计时（可选跳过）
3. 下载文件到指定目录
4. 支持重定向 URL 解析（如 javlibrary redirect.php）

用法：
    python3 windfiles_download.py <share_url> [--output-dir <dir>] [--skip-wait] [--manual-browser]
"""

import argparse
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
import ssl
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse


def extract_windfiles_url(url):
    """从重定向 URL 中提取 windfiles 真实链接
    
    支持格式：
    - https://www.javlibrary.com/cn/redirect.php?url=https%3A%2F%2Fwindfiles.com%2Fshare%2Fxxx
    - 其他包含 url 参数的重定向链接
    """
    # 首先尝试直接从整个 URL 字符串中提取 windfiles 链接（最可靠）
    match = re.search(r'https://windfiles\.com/share/[a-zA-Z0-9]+', url)
    if match:
        result = match.group(0)
        print(f"从重定向 URL 中提取：{result}")
        return result
    
    parsed = urlparse(url)
    
    # 如果是直接的 windfiles 链接，直接返回
    if 'windfiles.com' in parsed.netloc:
        return url
    
    # 尝试从 url 参数中提取
    params = parse_qs(parsed.query)
    if 'url' in params:
        redirect_url = params['url'][0]
        # URL 解码后可能还是编码的，需要再次解码
        import urllib.parse
        try:
            redirect_url = urllib.parse.unquote(redirect_url)
        except:
            pass
        
        # 检查是否是 windfiles 链接
        if 'windfiles.com' in redirect_url:
            match = re.search(r'https://windfiles\.com/share/[a-zA-Z0-9]+', redirect_url)
            if match:
                print(f"从重定向 URL 中提取：{match.group(0)}")
                return match.group(0)
    
    # 如果没有找到，返回原 URL（让后续逻辑处理）
    return url


def fetch_page(url, timeout=30):
    """获取页面内容"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    request = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
    )
    
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
            return response.read().decode('utf-8')
    except urllib.error.URLError as e:
        print(f"错误：无法访问页面 - {e}")
        return None


class DownloadLinkParser(HTMLParser):
    """解析 Windfiles 页面，提取下载链接"""
    
    def __init__(self):
        super().__init__()
        self.slow_download_link = None
        self.fast_download_link = None
        self.filename = None
        self.filesize = None
        self.countdown_seconds = 90
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        href = attrs_dict.get('href', '')
        
        # 提取文件名
        if tag == 'th' and 'File Name' in self.last_data if hasattr(self, 'last_data') else False:
            pass
            
        # 提取下载链接
        if '/download/slow/' in href:
            self.slow_download_link = href
        elif '/download/fast/' in href and 'VIP' not in href:
            self.fast_download_link = href
            
    def handle_data(self, data):
        self.last_data = data
        
        # 提取文件名（.torrent 文件）
        if '.torrent' in data and len(data) < 100:
            self.filename = data.strip()
            
        # 提取倒计时时间
        match = re.search(r'const counterTime\s*=\s*(\d+)', data)
        if match:
            self.countdown_seconds = int(match.group(1))


def extract_download_info(html_content):
    """从 HTML 中提取下载信息"""
    parser = DownloadLinkParser()
    parser.feed(html_content)
    
    # 如果 parser 没找到，用正则直接提取
    if not parser.slow_download_link:
        match = re.search(r'/download/slow/\?dl=[^"\'>\s]+', html_content)
        if match:
            parser.slow_download_link = match.group(0)
    
    # 提取文件名
    if not parser.filename:
        match = re.search(r'([A-Z0-9-]+\.torrent)', html_content)
        if match:
            parser.filename = match.group(1)
    
    # 提取倒计时时间
    match = re.search(r'counterTime\s*=\s*(\d+)', html_content)
    if match:
        parser.countdown_seconds = int(match.group(1))
    
    return parser


def download_file(url, output_dir, filename, timeout=60):
    """下载文件"""
    import os
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, filename)
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    request = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://windfiles.com/',
        }
    )
    
    print(f"正在下载：{filename}")
    print(f"保存到：{output_path}")
    
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
            # 检查是否是重定向到其他页面
            content_type = response.headers.get('Content-Type', '')
            if 'html' in content_type:
                print("警告：服务器返回了 HTML 页面，可能需要通过浏览器下载")
                return None
                
            with open(output_path, 'wb') as f:
                f.write(response.read())
            
            print(f"下载完成：{output_path}")
            return output_path
    except Exception as e:
        print(f"下载失败：{e}")
        return None


def download_with_agent_browser(share_url, output_dir):
    """使用 agent-browser 进行下载（适用于需要交互的情况）"""
    
    import os
    import shutil
    from pathlib import Path
    
    # 检查 agent-browser 是否可用
    result = subprocess.run(['which', 'agent-browser'], capture_output=True)
    if result.returncode != 0:
        print("错误：agent-browser 未安装")
        return None
    
    print("使用 agent-browser 进行下载...")
    
    # 1. 打开分享页面
    subprocess.run(['agent-browser', 'open', share_url], check=True)
    time.sleep(2)
    
    # 2. 获取页面快照
    result = subprocess.run(['agent-browser', 'snapshot', '-i'], 
                          capture_output=True, text=True)
    snapshot_content = result.stdout
    
    # 3. 从快照提取文件名
    share_filename = 'download.torrent'
    match = re.search(r'([A-Z0-9-]+\.torrent)', snapshot_content)
    if match:
        share_filename = match.group(1)
        print(f"文件名：{share_filename}")
    
    # 4. 使用 curl 直接从分享页面提取下载链接
    html_content = fetch_page(share_url)
    
    # 5. 提取下载链接（如果 fetch_page 失败，html_content 为 None）
    match = re.search(r'/download/slow/\?dl=[^"\'>\s]+', html_content) if html_content else None
    if not match:
        print("错误：无法找到下载链接，尝试点击免费下载按钮...")
        
        match = re.search(r'link "Free Slow Download" \[ref=(e\d+)\]', snapshot_content)
        if match:
            free_btn_ref = match.group(1)
            print(f"点击免费下载按钮：{free_btn_ref}")
            subprocess.run(['agent-browser', 'click', free_btn_ref], check=True)
            time.sleep(95)
            
            result = subprocess.run(['agent-browser', 'snapshot', '-i'], 
                                  capture_output=True, text=True)
    else:
        download_link = match.group(0)
        if not download_link.startswith('http'):
            download_link = 'https://windfiles.com' + download_link
        
        print(f"下载链接：{download_link}")
        
        # 6. 访问下载页面
        subprocess.run(['agent-browser', 'open', download_link], check=True)
        time.sleep(2)
        
        # 7. 获取下载页面快照
        result = subprocess.run(['agent-browser', 'snapshot', '-i', '-C'],
                              capture_output=True, text=True)
        snapshot_text = result.stdout
        
        # 7a. 检查页面是否有冷却/错误提示
        cooldown_patterns = [
            r'wait.*10.*min', r'cool.?down', r'cooldown',
            r'please wait', r'try again later',
            r'you can only download', r'daily.*limit',
            r'already downloaded', r'10.*分钟内', r'冷却',
            r'请等待', r'请稍后', r'限制', r'已达到',
        ]
        for pat in cooldown_patterns:
            if re.search(pat, snapshot_text, re.IGNORECASE):
                print(f"❌ 检测到下载限制：页面包含冷却/限制提示")
                # 截取相关上下文
                context_pat = r'.{0,40}' + pat + r'.{0,80}'
                cmatch = re.search(context_pat, snapshot_text, re.IGNORECASE)
                if cmatch:
                    print(f"   提示内容：{cmatch.group(0).strip()}")
                print("   10 分钟冷却期内无法下载，请稍后再试或使用 --proxy 切换 IP")
                return None
        
        # 8. 查找并点击下载按钮
        match = re.search(r'button "Start Download Now" \[ref=(e\d+)\]', snapshot_text)
        if match:
            button_ref = match.group(1)
            print(f"点击下载按钮：{button_ref}")
            subprocess.run(['agent-browser', 'click', button_ref], check=True)
        else:
            # 没有按钮也没有冷却提示 — 输出部分页面内容帮助调试
            preview = snapshot_text[:300]
            print(f"❌ 未找到下载按钮，页面内容：{preview}")
            return None
    
    # --- 修复：正确找回下载的文件 ---
    downloads_dir = os.path.expanduser('~/Downloads')
    os.makedirs(output_dir, exist_ok=True)
    
    # 9. 轮询等待文件下载完成（最多 30 秒）
    downloaded_file = None
    for wait_sec in range(30):
        time.sleep(1)
        
        if not os.path.exists(downloads_dir):
            continue
        
        for f in os.listdir(downloads_dir):
            if f.endswith('.torrent'):
                fp = os.path.join(downloads_dir, f)
                try:
                    if f.endswith('.crdownload'):
                        continue
                    # 只看最近 60 秒内修改的文件（排除旧文件）
                    mtime = os.path.getmtime(fp)
                    if time.time() - mtime < 60:
                        downloaded_file = fp
                        break
                except OSError:
                    continue
        if downloaded_file:
            break
    
    # 如果按时间没找到，但文件名完全匹配分享页预期文件名，也接受
    if not downloaded_file and os.path.exists(downloads_dir):
        for f in os.listdir(downloads_dir):
            if f == share_filename:
                fp = os.path.join(downloads_dir, f)
                if os.path.isfile(fp):
                    mtime = os.path.getmtime(fp)
                    if time.time() - mtime < 300:  # 放宽到 5 分钟
                        downloaded_file = fp
                        break
    
    # 10. 复制到目标目录
    if downloaded_file:
        os.makedirs(output_dir, exist_ok=True)
        dest = os.path.join(output_dir, share_filename)
        shutil.copy2(downloaded_file, dest)
        actual_size = os.path.getsize(dest)
        print(f"文件已保存到：{dest}（{actual_size / 1024:.1f} KB）")
        return dest
    
    print("❌ 下载失败：未在 ~/Downloads 中找到新下载的 torrent 文件")
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Windfiles 云盘下载工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 基本用法（默认使用 browser 模式）
    python3 windfiles_download.py "https://windfiles.com/share/abc123"

    # 指定输出目录
    python3 windfiles_download.py "https://windfiles.com/share/abc123" --output-dir ./downloads

    # 从 javlibrary 重定向链接下载
    python3 windfiles_download.py "https://www.javlibrary.com/cn/redirect.php?url=https%3A%2F%2Fwindfiles.com%2Fshare%2Fabc123"

    # 禁用 browser 模式（使用传统下载方式）
    python3 windfiles_download.py "https://windfiles.com/share/abc123" --manual-browser
"""
    )
    
    parser.add_argument('url', help='Windfiles 分享链接')
    parser.add_argument('--output-dir', '-o', default='~/Downloads/windfiles',
                       help='输出目录 (默认：~/Downloads/windfiles)')
    parser.add_argument('--skip-wait', action='store_true',
                       help='跳过倒计时等待（直接访问下载页面）')
    parser.add_argument('--manual-browser', action='store_true',
                       help='手动禁用 browser 模式（默认启用 browser 模式）')
    
    args = parser.parse_args()
    
    # 展开输出目录路径
    import os
    output_dir = os.path.expanduser(args.output_dir)
    
    # 提取真实的 windfiles 链接（处理重定向 URL）
    windfiles_url = extract_windfiles_url(args.url)
    print(f"原始链接：{args.url}")
    print(f"Windfiles URL: {windfiles_url}")
    
    # 默认使用 browser 模式，除非显式禁用
    use_browser = not args.manual_browser
    
    if use_browser:
        result = download_with_agent_browser(windfiles_url, output_dir)
    else:
        # 获取分享页面
        print("正在获取页面信息...")
        html_content = fetch_page(windfiles_url)
        
        if not html_content:
            print("获取页面失败，尝试使用 agent-browser...")
            result = download_with_agent_browser(windfiles_url, output_dir)
            sys.exit(0 if result else 1)
        
        # 解析下载信息
        info = extract_download_info(html_content)
        
        print(f"文件名：{info.filename or '未知'}")
        print(f"倒计时：{info.countdown_seconds} 秒")
        
        if info.slow_download_link:
            download_url = 'https://windfiles.com' + info.slow_download_link
            print(f"下载链接：{download_url}")
            
            if not args.skip_wait:
                print(f"\n等待 {info.countdown_seconds} 秒（可使用 --skip-wait 跳过）...")
                time.sleep(info.countdown_seconds)
            
            result = download_file(download_url, output_dir, 
                                  info.filename or 'download.torrent')
        else:
            print("未找到免费下载链接，尝试使用 agent-browser...")
            result = download_with_agent_browser(windfiles_url, output_dir)
    
    sys.exit(0 if result else 1)


if __name__ == '__main__':
    main()
