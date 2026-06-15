#!/usr/bin/env python3
"""Windfiles Cloud Drive 下载脚本 - 入口点"""
import sys
import os
import time
import urllib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.url_parser import extract_windfiles_url
from src.html_parser import DownloadLinkParser, extract_download_info
from src.downloader import download_file, _extract_filename_from_disposition, download_slow_via_post, download_with_agent_browser
from src.proxy import setup_global_proxy, show_exit_ip
from src.fetcher import fetch_page, fetch_page_with_retry
from src.cli import main

if __name__ == '__main__':
    main()
