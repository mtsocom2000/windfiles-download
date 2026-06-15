import time
import urllib.error
import urllib.request


def fetch_page(url, timeout=30):
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
    for attempt in range(1, retries + 1):
        import windfiles_download as _wd
        result = _wd.fetch_page(url, timeout)
        if result is not None:
            return result
        if attempt < retries:
            print(f"重试 {attempt}/{retries}（等待 {delay}s）...")
            time.sleep(delay)
    return None
