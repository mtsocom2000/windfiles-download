import ssl
import urllib.request


_global_proxy = None


def setup_global_proxy(proxy_url):
    global _global_proxy
    if not proxy_url:
        return
    _global_proxy = proxy_url
    print(f"🔌 使用代理：{proxy_url}")

    default_ctx = ssl.create_default_context()
    default_ctx.check_hostname = False
    default_ctx.verify_mode = ssl.CERT_NONE
    ssl._create_default_https_context = lambda: default_ctx

    proxy_handler = urllib.request.ProxyHandler({
        'http': proxy_url,
        'https': proxy_url
    })
    opener = urllib.request.build_opener(proxy_handler)
    urllib.request.install_opener(opener)


def show_exit_ip(proxy_url=None):
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
