import re
from html.parser import HTMLParser


class DownloadLinkParser(HTMLParser):

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

        if '/download/slow/' in href:
            self.slow_download_link = href
        elif '/download/fast/' in href and 'VIP' not in href:
            self.fast_download_link = href

    def handle_data(self, data):
        self.last_data = data

        if '.torrent' in data and len(data) < 100:
            self.filename = data.strip()

        match = re.search(r'const counterTime\s*=\s*(\d+)', data)
        if match:
            self.countdown_seconds = int(match.group(1))


def extract_download_info(html_content):
    parser = DownloadLinkParser()
    parser.feed(html_content)

    if not parser.slow_download_link:
        match = re.search(r'/download/slow/\?dl=[^"\'>\s]+', html_content)
        if match:
            parser.slow_download_link = match.group(0)

    if not parser.filename:
        match = re.search(r'([A-Z0-9-]+\.torrent)', html_content)
        if match:
            parser.filename = match.group(1)

    match = re.search(r'counterTime\s*=\s*(\d+)', html_content)
    if match:
        parser.countdown_seconds = int(match.group(1))

    return parser
