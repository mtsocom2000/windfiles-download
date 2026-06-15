import argparse
import os
import re
import sys


def main():
    import windfiles_download as _wd

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

    proxy_group = parser.add_argument_group('代理选项（用于绕过 IP 级限制）')
    proxy_group.add_argument('--proxy',
                       help='HTTP 代理地址，如 http://user:pass@host:port')
    proxy_group.add_argument('--show-ip', action='store_true',
                       help='下载前显示当前出口 IP（用于确认代理是否生效）')

    args = parser.parse_args()

    proxy_url = None
    if args.proxy:
        proxy_url = args.proxy

    _wd.setup_global_proxy(proxy_url)

    if args.show_ip or proxy_url:
        ip = _wd.show_exit_ip(proxy_url)
        if ip:
            print(f"🌐 出口 IP：{ip}")

    output_dir = os.path.expanduser(args.output_dir)

    windfiles_url = _wd.extract_windfiles_url(args.url)
    print(f"原始链接：{args.url}")
    print(f"Windfiles URL: {windfiles_url}")

    use_browser = not args.manual_browser

    if use_browser:
        result = _wd.download_with_agent_browser(windfiles_url, output_dir, proxy=proxy_url)
    else:
        print("正在获取页面信息...")
        html_content = _wd.fetch_page_with_retry(windfiles_url)

        if not html_content:
            print("获取页面失败，尝试使用 agent-browser...")
            result = _wd.download_with_agent_browser(windfiles_url, output_dir, proxy=proxy_url)
            sys.exit(0 if result else 1)

        info = _wd.extract_download_info(html_content)

        print(f"文件名：{info.filename or '未知'}")
        print(f"倒计时：{info.countdown_seconds} 秒")

        if info.slow_download_link:
            dl_match = re.search(r'dl=([^&\s]+)', info.slow_download_link)
            if dl_match:
                dl_param = dl_match.group(1)
                print(f"dl 参数：{dl_param[:40]}...")

                if not args.skip_wait:
                    print(f"\n等待 {info.countdown_seconds} 秒（可使用 --skip-wait 跳过）...")
                    import time as _time
                    _time.sleep(info.countdown_seconds)

                result = _wd.download_slow_via_post(dl_param, output_dir,
                                                info.filename or 'download.torrent')

                if not result:
                    print("\nPOST 方式失败，尝试直接 GET 下载...")
                    download_url = 'https://windfiles.com' + info.slow_download_link
                    result = _wd.download_file(download_url, output_dir,
                                          info.filename or 'download.torrent')
            else:
                print("错误：无法提取 dl 参数")
                result = None
        else:
            print("未找到免费下载链接，尝试使用 agent-browser...")
            result = _wd.download_with_agent_browser(windfiles_url, output_dir, proxy=proxy_url)

    sys.exit(0 if result else 1)
