#!/usr/bin/env python3
"""
Windfiles Cloud Drive 下载脚本 - 支持代理功能

功能：
1. 解析分享页面，提取下载链接
2. 自动等待倒计时（可选跳过）
3. 支持代理下载（住宅代理可绕过 IP 级限制）
4. 支持重定向 URL 解析（如 javlibrary redirect.php）

用法：
    python3 windfiles_download.py <share_url> [--output-dir <dir>] [--skip-wait] [--manual-browser]
    python3 windfiles_download.py <share_url> --proxy "http://user:pass@host:port"
    python3 windfiles_download.py <share_url> --proxy "http://user:pass@host:port"
"""

import argparse
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
import ssl
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse


# ──────────────────────────────────────
# 全局代理 + SSL 支持
# ──────────────────────────────────────

_global_proxy = None


def setup_global_proxy(proxy_url):
    """安装全局 urllib 代理 + 全局非验证 SSL context
    
    同时做两件事：
    1. 安装 ProxyHandler，使所有 urlopen 走代理
    2. 设置全局 SSL context（禁用证书验证），因为 dl.windfiles.com 多级重定向时
       传入 context 参数会导致 urlopen 新建 opener 丢掉 proxy handler
    """
    global _global_proxy
    if not proxy_url:
        return
    _global_proxy = proxy_url
    print(f"🔌 使用代理：{proxy_url}")
    
    # 全局 SSL：不验证证书（否则 dl.windfiles.com 可能 SSL 错误）
    default_ctx = ssl.create_default_context()
    default_ctx.check_hostname = False
    default_ctx.verify_mode = ssl.CERT_NONE
    ssl._create_default_https_context = lambda: default_ctx
    
    # 全局代理
    proxy_handler = urllib.request.ProxyHandler({
        'http': proxy_url,
        'https': proxy_url
    })
    opener = urllib.request.build_opener(proxy_handler)
    urllib.request.install_opener(opener)




# ──────────────────────────────────────
# URL 解析
# ──────────────────────────────────────

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


# ──────────────────────────────────────
# 页面获取
# ──────────────────────────────────────

def fetch_page(url, timeout=30):
    """获取页面内容（走已安装的全局 proxy）"""
    
    request = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
    )
    
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except urllib.error.URLError as e:
        print(f"错误：无法访问页面 - {e}")
        return None


def fetch_page_with_retry(url, timeout=30, retries=3, delay=5):
    """带重试的页面获取"""
    for attempt in range(1, retries + 1):
        result = fetch_page(url, timeout)
        if result is not None:
            return result
        if attempt < retries:
            print(f"重试 {attempt}/{retries}（等待 {delay}s）...")
            time.sleep(delay)
    return None


# ──────────────────────────────────────
# HTML 解析
# ──────────────────────────────────────

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


# ──────────────────────────────────────
# 下载核心
# ──────────────────────────────────────

def download_file(url, output_dir, filename_hint, timeout=120):
    """下载文件（走全局 proxy）
    
    从 Content-Disposition 头提取真实文件名，fallback 到 filename_hint。
    """
    os.makedirs(output_dir, exist_ok=True)
    
    request = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://windfiles.com/',
        }
    )
    
    print(f"正在下载...")
    
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get('Content-Type', '')
            
            # 从 Content-Disposition 提取真实文件名
            real_filename = _extract_filename_from_disposition(response.headers, filename_hint)
            output_path = os.path.join(output_dir, real_filename)
            
            print(f"真实文件名：{real_filename}")
            print(f"保存到：{output_path}")
            
            # 检查是否是重定向到其他页面
            if 'html' in content_type:
                print("⚠️ 服务器返回了 HTML 页面（可能是限制页面），尝试 POST 方式...")
                return None
                
            data = response.read()
            if not data or len(data) < 100:
                print(f"⚠️ 下载数据过小 ({len(data)} 字节)，可能被限制")
                return None
                
            with open(output_path, 'wb') as f:
                f.write(data)
            
            print(f"✅ 下载完成：{output_path}（{len(data)/1024:.1f} KB）")
            return output_path
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:200]
        print(f"❌ HTTP {e.code}: {body}")
        return None
    except Exception as e:
        print(f"❌ 下载失败：{e}")
        return None


def _extract_filename_from_disposition(headers, default):
    """从 Content-Disposition 响应头提取真实文件名"""
    cd = headers.get('Content-Disposition', '')
    if not cd:
        return default
    # 支持两种格式：filename="xxx" 或 filename*=UTF-8''xxx
    match = re.search(r'''filename[^;=\n]*=((['"])(.*?)\2|[^;\n]*)''', cd, re.IGNORECASE)
    if match:
        name = match.group(3) or match.group(0).split('=', 1)[1].strip().strip('"\'')
        if name:
            return name
    return default


def download_slow_via_post(dl_param, output_dir, filename_hint, timeout=120):
    """通过 POST /download/jump 获取 slow download 的实际文件
    
    windfiles 的免费下载流程（manual-browser 模式）：
    1. 分享页提取 /download/slow/?dl=xxx
    2. POST /download/jump?dl=xxx → 302 到 dl.windfiles.com
    3. 跟随重定向 → 从 Content-Disposition 获取真实文件名 + 下载文件
    
    走全局 proxy。
    """
    os.makedirs(output_dir, exist_ok=True)
    
    post_data = b'btnAct=Start+Download+Now'
    
    request = urllib.request.Request(
        f'https://windfiles.com/download/jump?dl={dl_param}',
        data=post_data,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'https://windfiles.com/',
        }
    )
    
    print(f"正在通过 POST 获取下载...")
    
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get('Content-Type', '')
            data = response.read()
            
            # 从 Content-Disposition 提取真实文件名
            real_filename = _extract_filename_from_disposition(response.headers, filename_hint)
            output_path = os.path.join(output_dir, real_filename)
            
            print(f"真实文件名：{real_filename}")
            print(f"保存到：{output_path}")
            
            if 'html' in content_type:
                print(f"❌ POST 失败，服务器返回 HTML（可能触发了限制）")
                print(data[:500].decode('utf-8', errors='replace'))
                return None
            
            if not data or len(data) < 100:
                print(f"⚠️ POST 返回数据过小 ({len(data)} 字节)，可能失败")
                return None
                
            with open(output_path, 'wb') as f:
                f.write(data)
            
            print(f"✅ 下载完成：{output_path}（{len(data)/1024:.1f} KB）")
            return output_path
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:300]
        print(f"❌ POST 下载失败 HTTP {e.code}: {body}")
        
        # 检查是否是每日限制
        limit_patterns = [
            r'have downloaded \d+ files', r'upgrade.*VIP', r'try again',
            r'daily.*limit', r'limit.*reached', r'24 hours',
            r'每日.*下载', r'超过.*限制', r'升级.*VIP',
        ]
        for pat in limit_patterns:
            if re.search(pat, body, re.IGNORECASE):
                print("\n🔒 检测到每日下载限制（2 次/24h）")
                print("   使用 --proxy 切换 IP 即可绕过")
                break
        return None
    except Exception as e:
        print(f"❌ POST 下载失败：{e}")
        return None


# ──────────────────────────────────────
# Agent-Browser 模式（proxy 感知）
# ──────────────────────────────────────

def download_with_agent_browser(share_url, output_dir, proxy=None):
    """使用 agent-browser 进行下载（适用于需要交互的情况）
    
    支持通过环境变量传递代理给 Chrome。
    """
    import shutil
    from pathlib import Path
    
    # 代理环境变量，agent-browser / Chrome 会自动读取
    env = os.environ.copy()
    if proxy:
        env['HTTP_PROXY'] = proxy
        env['HTTPS_PROXY'] = proxy
        env['http_proxy'] = proxy
        env['https_proxy'] = proxy
    
    # 检查 agent-browser 是否可用
    result = subprocess.run(['which', 'agent-browser'], capture_output=True)
    if result.returncode != 0:
        print("错误：agent-browser 未安装")
        return None
    
    print("使用 agent-browser 进行下载...")
    
    # 1. 打开分享页面
    subprocess.run(['agent-browser', 'open', share_url], env=env, check=True)
    time.sleep(2)
    
    # 2. 获取页面快照
    result = subprocess.run(['agent-browser', 'snapshot', '-i'],
                          capture_output=True, text=True, env=env)
    snapshot_content = result.stdout
    
    # 3. 从快照提取文件名
    share_filename = 'download.torrent'
    match = re.search(r'([A-Z0-9-]+\.torrent)', snapshot_content)
    if match:
        share_filename = match.group(1)
        print(f"文件名：{share_filename}")
    
    # 4. 获取页面内容（走已安装的全局 proxy）
    html_content = fetch_page(share_url)
    
    # 5. 提取下载链接（如果 fetch_page 失败，html_content 为 None）
    match = re.search(r'/download/slow/\?dl=[^"\'>\s]+', html_content) if html_content else None
    if not match:
        print("错误：无法找到下载链接，尝试点击免费下载按钮...")
        
        match = re.search(r'link "Free Slow Download" \[ref=(e\d+)\]', snapshot_content)
        if match:
            free_btn_ref = match.group(1)
            print(f"点击免费下载按钮：{free_btn_ref}")
            subprocess.run(['agent-browser', 'click', free_btn_ref], env=env, check=True)
            time.sleep(95)
            
            result = subprocess.run(['agent-browser', 'snapshot', '-i'],
                                  capture_output=True, text=True, env=env)
    else:
        download_link = match.group(0)
        if not download_link.startswith('http'):
            download_link = 'https://windfiles.com' + download_link
        
        print(f"下载链接：{download_link}")
        
        # 6. 访问下载页面
        subprocess.run(['agent-browser', 'open', download_link], env=env, check=True)
        time.sleep(2)
        
        # 7. 获取下载页面快照
        result = subprocess.run(['agent-browser', 'snapshot', '-i', '-C'],
                              capture_output=True, text=True, env=env)
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
            subprocess.run(['agent-browser', 'click', button_ref], env=env, check=True)
            time.sleep(2)
            
            # 8a. 点击后检查是否跳转到限制提示页
            result = subprocess.run(['agent-browser', 'snapshot', '-i', '-C'],
                                  capture_output=True, text=True, env=env)
            post_click_text = result.stdout
            limit_patterns = [
                r'You have downloaded \d+ files in the last 24 hours',
                r'Please upgrade to VIP or try again tomorrow',
                r'每日下载', r'下载次数', r'超过.*限制', r'升级.*VIP',
                r'Daily download limit', r'limit reached',
                r'you have reached.*limit', r'try again tomorrow',
            ]
            for pat in limit_patterns:
                if re.search(pat, post_click_text, re.IGNORECASE):
                    print(f"❌ 检测到每日下载限制")
                    cmatch = re.search(r'.{0,40}' + pat + r'.{0,80}', post_click_text, re.IGNORECASE)
                    if cmatch:
                        print(f"   提示内容：{cmatch.group(0).strip()}")
                    print("   未登录账号每日限制 2 次下载，请使用 --proxy 切换 IP 绕过")
                    return None
        else:
            # 没有按钮也没有冷却提示 — 输出部分页面内容帮助调试
            preview = snapshot_text[:300]
            print(f"❌ 未找到下载按钮，页面内容：{preview}")
            return None
    
    # 9. 轮询等待文件下载完成（最多 30 秒）
    downloads_dir = os.path.expanduser('~/Downloads')
    os.makedirs(output_dir, exist_ok=True)
    
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
        print(f"✅ 文件已保存到：{dest}（{actual_size / 1024:.1f} KB）")
        return dest
    
    print("❌ 下载失败：未在 ~/Downloads 中找到新下载的 torrent 文件")
    return None


# ──────────────────────────────────────
# 主流程
# ──────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Windfiles 云盘下载工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 基本用法（默认使用 browser 模式）
    python3 windfiles_download.py "https://windfiles.com/share/abc123"

    # 禁用 browser 模式（传统下载方式）
    python3 windfiles_download.py "https://windfiles.com/share/abc123" --manual-browser

    # 使用自建代理下载
    python3 windfiles_download.py "https://windfiles.com/share/abc123" --proxy "http://user:pass@1.2.3.4:8080"

    # 使用 Bright Data 住宅代理（固定 IP）
    python3 windfiles_download.py "https://windfiles.com/share/abc123" --proxy "http://brd-customer-h_xxx-zone-xxx:pass@brd.superproxy.io:33335"

    # 使用 RapidProxy 住宅代理（用户自行构造 session ID）
    python3 windfiles_download.py "https://windfiles.com/share/abc123" --proxy "http://user-residential-AS-session-12345678-stime-3:pass@us.rapidproxy.io:5001"
    # 每次用不同 session ID → 不同出口 IP → 不触发每日限制

    # 从 javlibrary 重定向链接下载
    python3 windfiles_download.py "https://www.javlibrary.com/cn/redirect.php?url=https%3A%2F%2Fwindfiles.com%2Fshare%2Fabc123"
"""
    )
    
    parser.add_argument('url', help='Windfiles 分享链接')
    parser.add_argument('--output-dir', '-o', default='~/Downloads',
                       help='输出目录 (默认：~/Downloads)')
    parser.add_argument('--skip-wait', action='store_true',
                       help='跳过倒计时等待（直接访问下载页面）')
    parser.add_argument('--manual-browser', action='store_true',
                       help='手动禁用 browser 模式（默认启用 browser 模式）')
    
    # 代理参数
    proxy_group = parser.add_argument_group('代理选项（用于绕过 IP 级限制）')
    proxy_group.add_argument('--proxy',
                       help='HTTP 代理地址，如 http://user:pass@host:port')
    proxy_group.add_argument('--show-ip', action='store_true',
                       help='下载前显示当前出口 IP（用于确认代理是否生效）')
    
    args = parser.parse_args()
    
    # 解析代理参数
    proxy_url = None
    if args.proxy:
        proxy_url = args.proxy
    
    # 安装全局代理
    setup_global_proxy(proxy_url)
    
    # 可选：显示出口 IP
    if args.show_ip or proxy_url:
        ip = show_exit_ip(proxy_url)
        if ip:
            print(f"🌐 出口 IP：{ip}")
    
    # 展开输出目录路径
    output_dir = os.path.expanduser(args.output_dir)
    
    # 提取真实的 windfiles 链接（处理重定向 URL）
    windfiles_url = extract_windfiles_url(args.url)
    print(f"原始链接：{args.url}")
    print(f"Windfiles URL: {windfiles_url}")
    
    # 默认使用 browser 模式，除非显式禁用
    use_browser = not args.manual_browser
    
    if use_browser:
        result = download_with_agent_browser(windfiles_url, output_dir, proxy=proxy_url)
    else:
        # --manual-browser 模式：纯 urllib + proxy
        print("正在获取页面信息...")
        html_content = fetch_page_with_retry(windfiles_url)
        
        if not html_content:
            print("获取页面失败，尝试使用 agent-browser...")
            result = download_with_agent_browser(windfiles_url, output_dir, proxy=proxy_url)
            sys.exit(0 if result else 1)
        
        # 解析下载信息
        info = extract_download_info(html_content)
        
        print(f"文件名：{info.filename or '未知'}")
        print(f"倒计时：{info.countdown_seconds} 秒")
        
        if info.slow_download_link:
            # 提取 dl 参数，用于 POST /download/jump
            dl_match = re.search(r'dl=([^&\s]+)', info.slow_download_link)
            if dl_match:
                dl_param = dl_match.group(1)
                print(f"dl 参数：{dl_param[:40]}...")
                
                if not args.skip_wait:
                    print(f"\n等待 {info.countdown_seconds} 秒（可使用 --skip-wait 跳过）...")
                    time.sleep(info.countdown_seconds)
                
                # 首选 POST /download/jump 方式（更可靠）
                result = download_slow_via_post(dl_param, output_dir,
                                                info.filename or 'download.torrent')
                
                # 如果 POST 失败，回退到直接 GET
                if not result:
                    print("\nPOST 方式失败，尝试直接 GET 下载...")
                    download_url = 'https://windfiles.com' + info.slow_download_link
                    result = download_file(download_url, output_dir,
                                          info.filename or 'download.torrent')
            else:
                print("错误：无法提取 dl 参数")
                result = None
        else:
            print("未找到免费下载链接，尝试使用 agent-browser...")
            result = download_with_agent_browser(windfiles_url, output_dir, proxy=proxy_url)
    
    sys.exit(0 if result else 1)


def show_exit_ip(proxy_url=None):
    """显示当前出口 IP（用于确认代理是否生效）"""
    
    services = [
        'https://api.ipify.org',
        'https://ifconfig.me/ip',
        'https://checkip.amazonaws.com',
    ]
    
    for svc in services:
        try:
            request = urllib.request.Request(
                svc,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(request, timeout=10) as resp:
                ip = resp.read().decode().strip()
                return ip
        except Exception:
            continue
    
    print("⚠️ 无法获取出口 IP（所有检测服务均失败）")
    return None


if __name__ == '__main__':
    main()
