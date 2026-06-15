import re
import urllib.parse
from urllib.parse import parse_qs, urlparse


def extract_windfiles_url(url):
    match = re.search(r'https://windfiles\.com/share/[a-zA-Z0-9]+', url)
    if match:
        result = match.group(0)
        print(f"从重定向 URL 中提取：{result}")
        return result

    parsed = urlparse(url)

    if 'windfiles.com' in parsed.netloc:
        return url

    params = parse_qs(parsed.query)
    if 'url' in params:
        redirect_url = params['url'][0]
        try:
            redirect_url = urllib.parse.unquote(redirect_url)
        except:
            pass

        if 'windfiles.com' in redirect_url:
            match = re.search(r'https://windfiles\.com/share/[a-zA-Z0-9]+', redirect_url)
            if match:
                print(f"从重定向 URL 中提取：{match.group(0)}")
                return match.group(0)

    return url
