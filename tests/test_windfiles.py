"""
Characterization tests for windfiles_download.py

These tests capture the CURRENT behavior of the original codebase
before refactoring. They serve as a safety net to verify that
refactored code produces identical results.

NOT intended as definitive "correct behavior" — they document
what the code actually does today.
"""

import io
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock, mock_open
from html.parser import HTMLParser

# Add the scripts dir to path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

# Import the original module
import windfiles_download as wd


# =============================================================================
# url_parser — extract_windfiles_url()
# =============================================================================

class TestExtractWindfilesURL(unittest.TestCase):
    """Characterizes extract_windfiles_url() behavior on various URL formats."""

    def test_direct_windfiles_url(self):
        """Direct windfiles share URL is returned as-is."""
        url = 'https://windfiles.com/share/abc123DEF'
        self.assertEqual(wd.extract_windfiles_url(url), url)

    def test_windfiles_url_with_path(self):
        """Windfiles URL with extra path segments."""
        url = 'https://windfiles.com/share/abc123DEF/some/extra/path'
        result = wd.extract_windfiles_url(url)
        self.assertEqual(result, 'https://windfiles.com/share/abc123DEF')

    def test_javlibrary_redirect(self):
        """Extracts windfiles URL from javlibrary's redirect.php with encoded URL."""
        url = 'https://www.javlibrary.com/cn/redirect.php?url=https%3A%2F%2Fwindfiles.com%2Fshare%2Fabc123DEF'
        result = wd.extract_windfiles_url(url)
        self.assertEqual(result, 'https://windfiles.com/share/abc123DEF')

    def test_javlibrary_redirect_double_encoded(self):
        """Extracts windfiles URL from javlibrary with double-encoded URL."""
        url = 'https://www.javlibrary.com/cn/redirect.php?url=https%253A%252F%252Fwindfiles.com%252Fshare%252Fabc123DEF'
        result = wd.extract_windfiles_url(url)
        self.assertEqual(result, 'https://windfiles.com/share/abc123DEF')

    def test_javlibrary_redirect_url_param_only(self):
        """Extracts windfiles URL from url param even without double-encoding."""
        url = 'https://some-site.com/redirect?url=https://windfiles.com/share/abc123DEF'
        result = wd.extract_windfiles_url(url)
        self.assertEqual(result, 'https://windfiles.com/share/abc123DEF')

    def test_no_windfiles_url_found(self):
        """If no windfiles URL is found anywhere, returns the original URL unchanged."""
        url = 'https://example.com/some/page'
        result = wd.extract_windfiles_url(url)
        self.assertEqual(result, url)

    def test_empty_url(self):
        """Empty string returns empty string."""
        url = ''
        result = wd.extract_windfiles_url(url)
        self.assertEqual(result, url)

    def test_windfiles_share_with_numbers(self):
        """Windfiles share IDs can contain numbers."""
        url = 'https://windfiles.com/share/abc123XYZ456'
        self.assertEqual(wd.extract_windfiles_url(url), url)

    def test_invalid_protocol_windfiles(self):
        """Windfiles URL with http (not https) — current code returns original URL unchanged."""
        url = 'http://www.javlibrary.com/redirect?url=http%3A%2F%2Fwindfiles.com%2Fshare%2Fabc123'
        result = wd.extract_windfiles_url(url)
        # NOTE: current code only matches 'https://windfiles.com' not 'http://windfiles.com'
        self.assertEqual(result, url)

    def test_redirect_with_multiple_params(self):
        """Redirect with url param among other params."""
        url = 'https://javlibrary.com/redirect.php?page=1&url=https%3A%2F%2Fwindfiles.com%2Fshare%2Fabc123DEF&lang=cn'
        result = wd.extract_windfiles_url(url)
        self.assertEqual(result, 'https://windfiles.com/share/abc123DEF')


# =============================================================================
# Content-Disposition — _extract_filename_from_disposition()
# =============================================================================

class TestExtractFilenameFromDisposition(unittest.TestCase):
    """Characterizes _extract_filename_from_disposition() header parsing."""

    def test_basic_filename(self):
        """Standard Content-Disposition with filename."""
        headers = {'Content-Disposition': 'attachment; filename="movie.torrent"'}
        result = wd._extract_filename_from_disposition(headers, 'default.torrent')
        self.assertEqual(result, 'movie.torrent')

    def test_filename_with_spaces(self):
        """Filename with spaces."""
        headers = {'Content-Disposition': 'attachment; filename="my movie file.torrent"'}
        result = wd._extract_filename_from_disposition(headers, 'default.torrent')
        self.assertEqual(result, 'my movie file.torrent')

    def test_filename_with_utf8_star(self):
        """RFC 5987 UTF-8 encoded filename — current code captures raw string (no URL decoding)."""
        headers = {'Content-Disposition': "attachment; filename*=UTF-8''%E6%B5%8B%E8%AF%95.torrent"}
        result = wd._extract_filename_from_disposition(headers, 'default.torrent')
        # NOTE: regex captures the raw filename*= value without URL-decoding UTF-8 chars
        # This is a known limitation of the current implementation
        self.assertEqual(result, "UTF-8''%E6%B5%8B%E8%AF%95.torrent")

    def test_no_content_disposition(self):
        """Missing Content-Disposition returns the default."""
        headers = {}
        result = wd._extract_filename_from_disposition(headers, 'fallback.torrent')
        self.assertEqual(result, 'fallback.torrent')

    def test_empty_content_disposition(self):
        """Empty Content-Disposition returns the default."""
        headers = {'Content-Disposition': ''}
        result = wd._extract_filename_from_disposition(headers, 'fallback.torrent')
        self.assertEqual(result, 'fallback.torrent')

    def test_inline_disposition(self):
        """Inline disposition also has a filename."""
        headers = {'Content-Disposition': 'inline; filename="doc.pdf"'}
        result = wd._extract_filename_from_disposition(headers, 'default.pdf')
        self.assertEqual(result, 'doc.pdf')

    def test_filename_single_quoted(self):
        """Single-quoted filename (non-standard but handled)."""
        headers = {'Content-Disposition': "attachment; filename='movie.torrent'"}
        result = wd._extract_filename_from_disposition(headers, 'default.torrent')
        self.assertEqual(result, 'movie.torrent')

    def test_filename_with_special_chars(self):
        """Filename with special characters (underscores, dashes, dots)."""
        headers = {'Content-Disposition': 'attachment; filename="AQUMA-129.torrent"'}
        result = wd._extract_filename_from_disposition(headers, 'default.torrent')
        self.assertEqual(result, 'AQUMA-129.torrent')

    def test_filename_raw_quotes(self):
        """RFC 6266 case: filename with quotes embedded in unquoted value."""
        headers = {'Content-Disposition': 'attachment; filename="file with spaces.torrent"'}
        result = wd._extract_filename_from_disposition(headers, 'default.torrent')
        self.assertEqual(result, 'file with spaces.torrent')


# =============================================================================
# HTML Parser — DownloadLinkParser + extract_download_info()
# =============================================================================

class TestDownloadLinkParserDirect(unittest.TestCase):
    """Characterizes DownloadLinkParser behavior on known HTML fragments."""

    def test_parser_initial_state(self):
        """Parser starts with all fields as None/default."""
        parser = wd.DownloadLinkParser()
        self.assertIsNone(parser.slow_download_link)
        self.assertIsNone(parser.fast_download_link)
        self.assertIsNone(parser.filename)
        self.assertIsNone(parser.filesize)
        self.assertEqual(parser.countdown_seconds, 90)

    def test_extracts_slow_download_link_from_href(self):
        """Extracts /download/slow/ link from anchor href."""
        html = '<a href="/download/slow/?dl=abc123">Slow Download</a>'
        parser = wd.DownloadLinkParser()
        parser.feed(html)
        self.assertEqual(parser.slow_download_link, '/download/slow/?dl=abc123')

    def test_extracts_fast_vip_link(self):
        """Fast download links containing 'VIP' are not extracted as fast_download_link."""
        html = '<a href="/download/fast/?dl=xyz&type=VIP">VIP Fast Download</a>'
        parser = wd.DownloadLinkParser()
        parser.feed(html)
        # VIP links are excluded from fast_download_link
        self.assertIsNone(parser.fast_download_link)

    def test_extracts_fast_non_vip_link(self):
        """Fast download link WITHOUT 'VIP' is captured."""
        html = '<a href="/download/fast/?dl=xyz">Fast Download</a>'
        parser = wd.DownloadLinkParser()
        parser.feed(html)
        self.assertEqual(parser.fast_download_link, '/download/fast/?dl=xyz')

    def test_extracts_counter_time_from_script(self):
        """Extracts countdown from const counterTime = N in page."""
        html = '<script>const counterTime = 45;</script>'
        parser = wd.DownloadLinkParser()
        parser.feed(html)
        self.assertEqual(parser.countdown_seconds, 45)

    def test_extracts_torrent_filename(self):
        """.torrent filenames are captured as filename."""
        html = '<div>AQUMA-129.torrent</div>'
        parser = wd.DownloadLinkParser()
        parser.feed(html)
        self.assertEqual(parser.filename, 'AQUMA-129.torrent')

    def test_extracts_torrent_filename_via_regex_fallback(self):
        """extract_download_info() — handle_data captures full text containing .torrent."""
        html = '<html><body><p>AQUMA-129.torrent is ready</p></body></html>'
        info = wd.extract_download_info(html)
        # NOTE: handle_data captures the ENTIRE data containing '.torrent', not just the filename
        self.assertIn('AQUMA-129.torrent', info.filename)

    def test_extracts_slow_link_via_regex_fallback(self):
        """extract_download_info() falls back to regex for slow download link."""
        html = '<html><body><a href="/download/slow/?dl=abc123">DL</a></body></html>'
        info = wd.extract_download_info(html)
        self.assertIn('abc123', info.slow_download_link)

    def test_counter_time_via_regex_fallback(self):
        """counterTime extraction via regex fallback."""
        html = '<script>counterTime = 30</script>'
        info = wd.extract_download_info(html)
        self.assertEqual(info.countdown_seconds, 30)

    def test_multiple_links_in_page(self):
        """Multiple download links — LAST slow link overwrites previous (parser overwrites)."""
        html = '''
        <a href="/download/slow/?dl=first">Download1</a>
        <a href="/download/slow/?dl=second">Download2</a>
        '''
        parser = wd.DownloadLinkParser()
        parser.feed(html)
        self.assertEqual(parser.slow_download_link, '/download/slow/?dl=second')

    def test_filename_not_torrent_ignored(self):
        """Non-.torrent text is not captured as filename (length check)."""
        html = '<div>' + 'x' * 200 + '.torrent</div>'
        parser = wd.DownloadLinkParser()
        parser.feed(html)
        # Data longer than 100 chars is skipped by the length check
        self.assertIsNone(parser.filename)

    def test_empty_html(self):
        """Empty HTML produces no results."""
        info = wd.extract_download_info('')
        self.assertIsNone(info.slow_download_link)
        self.assertIsNone(info.filename)
        self.assertEqual(info.countdown_seconds, 90)

    def test_no_counter_time_found(self):
        """HTML without counterTime keeps default 90."""
        html = '<html><body><p>No timer here</p></body></html>'
        parser = wd.DownloadLinkParser()
        parser.feed(html)
        self.assertEqual(parser.countdown_seconds, 90)


# =============================================================================
# setup_global_proxy()
# =============================================================================

class TestSetupGlobalProxy(unittest.TestCase):
    """Characterizes setup_global_proxy() behavior."""

    def setUp(self):
        # Reset any side effects from previous tests
        # The module-level proxy state needs careful isolation
        self._original_build_opener = urllib_request_build_opener if 'urllib_request_build_opener' in dir() else None
        pass

    @patch('windfiles_download.urllib.request.install_opener')
    @patch('windfiles_download.urllib.request.build_opener')
    @patch('windfiles_download.urllib.request.ProxyHandler')
    def test_proxy_url_stored_globally(self, mock_proxy_handler,
                                        mock_build_opener, mock_install_opener):
        """setup_global_proxy with a URL sets up proxy handler."""
        mock_proxy_handler.return_value = 'proxy_handler_instance'
        mock_build_opener.return_value = 'opener_instance'

        wd.setup_global_proxy('http://user:pass@proxy:8080')

        # Proxy handler created with both http and https
        mock_proxy_handler.assert_called_once_with({
            'http': 'http://user:pass@proxy:8080',
            'https': 'http://user:pass@proxy:8080'
        })
        # build_opener called with the proxy handler
        mock_build_opener.assert_called_once_with('proxy_handler_instance')
        # install_opener called with the opener
        mock_install_opener.assert_called_once_with('opener_instance')
        # NOTE: SSL context replacement is a MODULE-LEVEL side effect (on import),
        # not a function-level one, so it's not tested here

    def test_no_proxy_no_op(self):
        """setup_global_proxy with None/empty URL does nothing."""
        # Verify no crash
        wd.setup_global_proxy(None)
        wd.setup_global_proxy('')

    @patch('windfiles_download.urllib.request.install_opener')
    def test_prints_proxy_url(self, mock_install):
        """setup_global_proxy prints the proxy URL (captured for verification)."""
        with patch('builtins.print') as mock_print:
            wd.setup_global_proxy('http://test:pass@proxy:5001')
            mock_print.assert_called_with('🔌 使用代理：http://test:pass@proxy:5001')


# =============================================================================
# fetch_page / fetch_page_with_retry (via mocks)
# =============================================================================

class TestFetchPage(unittest.TestCase):
    """Characterizes fetch_page() behavior."""

    @patch('windfiles_download.urllib.request.urlopen')
    def test_fetch_page_success(self, mock_urlopen):
        """Successful page fetch returns decoded HTML."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'<html>test page</html>'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = wd.fetch_page('https://windfiles.com/share/test')
        self.assertEqual(result, '<html>test page</html>')

    @patch('windfiles_download.urllib.request.urlopen')
    def test_fetch_page_user_agent(self, mock_urlopen):
        """Request includes Chrome user-agent header."""
        wd.fetch_page('https://windfiles.com/share/test')
        request_arg = mock_urlopen.call_args[0][0]
        # urllib.request.Request stores headers case-insensitively
        ua = request_arg.get_header('User-agent')
        self.assertIn('Mozilla/5.0', ua)
        self.assertIn('Chrome/120', ua)

    @patch('windfiles_download.urllib.request.urlopen')
    def test_fetch_page_accept_header(self, mock_urlopen):
        """Request includes Accept header."""
        wd.fetch_page('https://windfiles.com/share/test')
        request_arg = mock_urlopen.call_args[0][0]
        self.assertIn('text/html', request_arg.headers['Accept'])

    @patch('windfiles_download.urllib.request.urlopen', side_effect=wd.urllib.error.URLError('Connection failed'))
    def test_fetch_page_error_returns_none(self, mock_urlopen):
        """Fetch failure returns None (does not raise)."""
        result = wd.fetch_page('https://windfiles.com/share/test')
        self.assertIsNone(result)

    @patch('windfiles_download.fetch_page')
    def test_retry_success_first_attempt(self, mock_fetch_page):
        """fetch_page_with_retry succeeds on first attempt."""
        mock_fetch_page.return_value = '<html>ok</html>'
        result = wd.fetch_page_with_retry('https://windfiles.com/share/test')
        self.assertEqual(result, '<html>ok</html>')
        mock_fetch_page.assert_called_once()

    @patch('windfiles_download.fetch_page')
    @patch('windfiles_download.time.sleep')
    def test_retry_after_failure(self, mock_sleep, mock_fetch_page):
        """fetch_page_with_retry retries 3 times with 5s delay between."""
        mock_fetch_page.side_effect = [None, None, '<html>ok</html>']
        result = wd.fetch_page_with_retry('https://windfiles.com/share/test')
        self.assertEqual(result, '<html>ok</html>')
        self.assertEqual(mock_fetch_page.call_count, 3)

    @patch('windfiles_download.fetch_page')
    @patch('windfiles_download.time.sleep')
    def test_retry_all_fail(self, mock_sleep, mock_fetch_page):
        """fetch_page_with_retry returns None if all retries fail."""
        mock_fetch_page.return_value = None
        result = wd.fetch_page_with_retry('https://windfiles.com/share/test')
        self.assertIsNone(result)
        self.assertEqual(mock_fetch_page.call_count, 3)


# =============================================================================
# download_file()
# =============================================================================

class TestDownloadFile(unittest.TestCase):
    """Characterizes download_file() behavior."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch('windfiles_download.urllib.request.urlopen')
    def test_download_uses_referer(self, mock_urlopen):
        """download_file includes Referer: https://windfiles.com/ header."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'torrent data'
        mock_resp.headers = {'Content-Disposition': 'attachment; filename="test.torrent"'}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        wd.download_file('https://dl.windfiles.com?dl=abc', self.temp_dir, 'test.torrent')

        request_arg = mock_urlopen.call_args[0][0]
        self.assertEqual(request_arg.headers['Referer'], 'https://windfiles.com/')

    @patch('windfiles_download.urllib.request.urlopen')
    def test_download_saves_file(self, mock_urlopen):
        """download_file saves file with real name from Content-Disposition."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'fake torrent content ' * 20  # >100 bytes
        mock_resp.headers = {'Content-Disposition': 'attachment; filename="AQUMA-129.torrent"'}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = wd.download_file('https://dl.windfiles.com?dl=abc', self.temp_dir, 'test.torrent')
        expected_path = os.path.join(self.temp_dir, 'AQUMA-129.torrent')
        self.assertEqual(result, expected_path)
        self.assertTrue(os.path.exists(expected_path))
        with open(expected_path) as f:
            self.assertEqual(f.read(), 'fake torrent content ' * 20)  # >100 bytes

    @patch('windfiles_download.urllib.request.urlopen')
    def test_download_small_data_returns_none(self, mock_urlopen):
        """Files smaller than 100 bytes are considered failed and return None."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'small'
        mock_resp.headers = {}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = wd.download_file('https://dl.windfiles.com?dl=abc', self.temp_dir, 'test.torrent')
        self.assertIsNone(result)

    @patch('windfiles_download.urllib.request.urlopen')
    def test_html_content_type_returns_none(self, mock_urlopen):
        """HTML content type triggers warning and returns None."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'<html>limit page</html>'
        mock_resp.headers = {'Content-Type': 'text/html'}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = wd.download_file('https://dl.windfiles.com?dl=abc', self.temp_dir, 'test.torrent')
        self.assertIsNone(result)

    @patch('windfiles_download.urllib.request.urlopen')
    def test_empty_data_returns_none(self, mock_urlopen):
        """Empty response data returns None."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b''
        mock_resp.headers = {}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = wd.download_file('https://dl.windfiles.com?dl=abc', self.temp_dir, 'test.torrent')
        self.assertIsNone(result)

    @patch('windfiles_download.urllib.request.urlopen')
    def test_http_error_returns_none(self, mock_urlopen):
        """HTTP 4xx/5xx errors return None."""
        mock_urlopen.side_effect = wd.urllib.error.HTTPError(
            'http://example.com', 403, 'Forbidden', {}, io.BytesIO(b'error body')
        )
        result = wd.download_file('https://windfiles.com/share/test', self.temp_dir, 'test.torrent')
        self.assertIsNone(result)


# =============================================================================
# download_slow_via_post()
# =============================================================================

class TestDownloadSlowViaPost(unittest.TestCase):
    """Characterizes download_slow_via_post() behavior."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch('windfiles_download.urllib.request.urlopen')
    def test_post_data_includes_btnAct(self, mock_urlopen):
        """POST body contains btnAct=Start+Download+Now."""
        tmp_dir = tempfile.mkdtemp()
        try:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'torrent data'
            mock_resp.headers = {'Content-Disposition': 'attachment; filename="out.torrent"'}
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            wd.download_slow_via_post('abc123', tmp_dir, 'test.torrent')
            request_arg = mock_urlopen.call_args[0][0]
            self.assertIn(b'btnAct=Start+Download+Now', request_arg.data)
        finally:
            shutil.rmtree(tmp_dir)

    @patch('windfiles_download.urllib.request.urlopen')
    def test_post_with_proper_content_type(self, mock_urlopen):
        """POST uses application/x-www-form-urlencoded content type."""
        tmp_dir = tempfile.mkdtemp()
        try:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'torrent data'
            mock_resp.headers = {'Content-Disposition': 'attachment; filename="out.torrent"'}
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            wd.download_slow_via_post('abc123', tmp_dir, 'test.torrent')
            request_arg = mock_urlopen.call_args[0][0]
            # urllib.request.Request stores headers case-insensitively
            ct = request_arg.get_header('Content-type')
            self.assertEqual(ct, 'application/x-www-form-urlencoded')
        finally:
            shutil.rmtree(tmp_dir)

    @patch('windfiles_download.urllib.request.urlopen')
    def test_post_http_error_returns_none(self, mock_urlopen):
        """POST HTTP error returns None."""
        mock_urlopen.side_effect = wd.urllib.error.HTTPError(
            'http://example.com', 429, 'Too Many', {}, io.BytesIO(b'try again later')
        )
        result = wd.download_slow_via_post('abc123', self.temp_dir, 'test.torrent')
        self.assertIsNone(result)

    @patch('windfiles_download.urllib.request.urlopen')
    def test_post_html_response_returns_none(self, mock_urlopen):
        """POST returning HTML (not binary) returns None (triggered limit)."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'<html>limit page</html>'
        mock_resp.headers = {'Content-Type': 'text/html; charset=utf-8'}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = wd.download_slow_via_post('abc123', self.temp_dir, 'test.torrent')
        self.assertIsNone(result)


# =============================================================================
# show_exit_ip()
# =============================================================================

class TestShowExitIp(unittest.TestCase):
    """Characterizes show_exit_ip() behavior."""

    @patch('windfiles_download.urllib.request.urlopen')
    def test_returns_ip_from_first_service(self, mock_urlopen):
        """Returns IP string from the first IP service that responds."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'1.2.3.4\n'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = wd.show_exit_ip()
        self.assertEqual(result, '1.2.3.4')

    @patch('windfiles_download.urllib.request.urlopen')
    def test_tries_multiple_ip_services(self, mock_urlopen):
        """Falls back through multiple IP detection services."""
        mock_urlopen.side_effect = [
            Exception('Service 1 down'),
            Exception('Service 2 down'),
            Exception('Service 3 down'),
        ]
        result = wd.show_exit_ip()
        self.assertIsNone(result)
        # Should have tried all 3 services
        self.assertEqual(mock_urlopen.call_count, 3)

    @patch('windfiles_download.urllib.request.urlopen')
    def test_strips_whitespace_from_ip(self, mock_urlopen):
        """Returned IP is stripped of whitespace/newlines."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'  1.2.3.4  \n'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = wd.show_exit_ip()
        self.assertEqual(result, '1.2.3.4')


# =============================================================================
# CLI argument parsing (tested through main() with sys.argv)
# =============================================================================

class TestCLIArgumentParsing(unittest.TestCase):
    """Characterizes argument parsing behavior via main()."""

    @patch('windfiles_download.download_with_agent_browser')
    @patch('windfiles_download.setup_global_proxy')
    @patch('windfiles_download.time.sleep')
    def test_minimal_args(self, mock_sleep, mock_setup, mock_browser):
        """URL is the only positional argument."""
        mock_browser.return_value = '/tmp/out/test.torrent'
        with patch.object(sys, 'argv', ['script', 'https://windfiles.com/share/test']):
            with self.assertRaises(SystemExit) as ctx:
                wd.main()
            self.assertEqual(ctx.exception.code, 0)

    @patch('windfiles_download.download_with_agent_browser')
    @patch('windfiles_download.setup_global_proxy')
    @patch('windfiles_download.time.sleep')
    def test_custom_output_dir(self, mock_sleep, mock_setup, mock_browser):
        """--output-dir overrides default."""
        mock_browser.return_value = '/tmp/out/test.torrent'
        with patch.object(sys, 'argv', ['script', 'https://windfiles.com/share/test', '--output-dir', '/tmp/custom']):
            with self.assertRaises(SystemExit):
                wd.main()

    @patch('windfiles_download.download_with_agent_browser')
    @patch('windfiles_download.setup_global_proxy')
    @patch('windfiles_download.time.sleep')
    def test_skip_wait_flag(self, mock_sleep, mock_setup, mock_browser):
        """--skip-wait flag is accepted without error."""
        mock_browser.return_value = '/tmp/out/test.torrent'
        with patch.object(sys, 'argv', ['script', 'https://windfiles.com/share/test', '--skip-wait']):
            with self.assertRaises(SystemExit):
                wd.main()

    @patch('windfiles_download.download_with_agent_browser')
    @patch('windfiles_download.setup_global_proxy')
    @patch('windfiles_download.time.sleep')
    def test_manual_browser_flag(self, mock_sleep, mock_setup, mock_browser):
        """--manual-browser flag is accepted."""
        mock_browser.return_value = '/tmp/out/test.torrent'
        with patch.object(sys, 'argv', ['script', 'https://windfiles.com/share/test', '--manual-browser']):
            with self.assertRaises(SystemExit):
                wd.main()

    @patch('windfiles_download.download_with_agent_browser')
    @patch('windfiles_download.setup_global_proxy')
    @patch('windfiles_download.time.sleep')
    def test_proxy_arg(self, mock_sleep, mock_setup, mock_browser):
        """--proxy URL is accepted."""
        mock_browser.return_value = '/tmp/out/test.torrent'
        with patch.object(sys, 'argv', ['script', 'https://windfiles.com/share/test', '--proxy', 'http://user@host:8080']):
            with self.assertRaises(SystemExit):
                wd.main()

    @patch('windfiles_download.download_with_agent_browser')
    @patch('windfiles_download.setup_global_proxy')
    @patch('windfiles_download.time.sleep')
    def test_show_ip_flag(self, mock_sleep, mock_setup, mock_browser):
        """--show-ip flag is accepted."""
        mock_browser.return_value = '/tmp/out/test.torrent'
        with patch.object(sys, 'argv', ['script', 'https://windfiles.com/share/test', '--show-ip']):
            with self.assertRaises(SystemExit):
                wd.main()

    def test_url_required(self):
        """URL is required — missing URL triggers error."""
        with patch.object(sys, 'argv', ['script']):
            with self.assertRaises(SystemExit):
                wd.main()


# =============================================================================
# Full main() flow (high-level integration)
# =============================================================================

class TestMainFlow(unittest.TestCase):
    """Characterizes main() integration behavior with mocked dependencies."""

    @patch('windfiles_download.download_slow_via_post')
    @patch('windfiles_download.fetch_page_with_retry')
    @patch('windfiles_download.extract_download_info')
    @patch('windfiles_download.time.sleep')
    @patch('windfiles_download.show_exit_ip')
    @patch('windfiles_download.setup_global_proxy')
    def test_main_mocked_manual_browser(
        self, mock_setup, mock_ip, mock_sleep, mock_extract, mock_fetch, mock_download
    ):
        """Manual browser flow: fetch page → parse → POST download."""
        mock_download.return_value = '/tmp/output/test.torrent'

        mock_info = MagicMock()
        mock_info.filename = 'test.torrent'
        mock_info.slow_download_link = '/download/slow/?dl=abc123'
        mock_info.countdown_seconds = 90
        mock_extract.return_value = mock_info
        mock_fetch.return_value = '<html>some page</html>'

        with patch.object(sys, 'argv', ['script', 'https://windfiles.com/share/test', '--manual-browser']):
            with self.assertRaises(SystemExit) as ctx:
                wd.main()
            self.assertEqual(ctx.exception.code, 0)

        mock_fetch.assert_called_once()
        mock_extract.assert_called_once_with('<html>some page</html>')
        mock_download.assert_called_once()

    @patch('windfiles_download.download_slow_via_post')
    @patch('windfiles_download.fetch_page_with_retry')
    @patch('windfiles_download.extract_download_info')
    def test_main_skip_wait_no_sleep(
        self, mock_extract, mock_fetch, mock_download
    ):
        """With --skip-wait, no time.sleep is called before download."""
        mock_download.return_value = '/tmp/out/test.torrent'
        mock_info = MagicMock()
        mock_info.filename = 'test.torrent'
        mock_info.slow_download_link = '/download/slow/?dl=abc123'
        mock_info.countdown_seconds = 90
        mock_extract.return_value = mock_info
        mock_fetch.return_value = '<html>page</html>'

        with patch.object(sys, 'argv', ['script', 'https://windfiles.com/share/test', '--manual-browser', '--skip-wait']):
            with patch('windfiles_download.time.sleep') as mock_sleep:
                with self.assertRaises(SystemExit):
                    wd.main()
                mock_sleep.assert_not_called()

    @patch('windfiles_download.setup_global_proxy')
    @patch('windfiles_download.show_exit_ip')
    @patch('windfiles_download.time.sleep')
    def test_main_with_proxy_shows_ip(self, mock_sleep, mock_ip, mock_setup):
        """With --proxy, setup_global_proxy is called and IP is shown."""
        mock_ip.return_value = '1.2.3.4'
        with patch.object(sys, 'argv', [
            'script', 'https://windfiles.com/share/test', '--manual-browser',
            '--proxy', 'http://user:pass@proxy:8080', '--skip-wait'
        ]):
            with patch('windfiles_download.fetch_page_with_retry', return_value='<html>ok</html>'):
                with patch('windfiles_download.extract_download_info') as mock_extract:
                    mock_info = MagicMock()
                    mock_info.slow_download_link = '/download/slow/?dl=abc'
                    mock_info.filename = 'test.torrent'
                    mock_info.countdown_seconds = 90
                    mock_extract.return_value = mock_info
                    with patch('windfiles_download.download_slow_via_post', return_value='/tmp/out/test.torrent'):
                        with self.assertRaises(SystemExit):
                            wd.main()

        mock_setup.assert_called_once_with('http://user:pass@proxy:8080')
        mock_ip.assert_called_once()

    @patch('windfiles_download.download_with_agent_browser')
    @patch('windfiles_download.time.sleep')
    @patch('windfiles_download.setup_global_proxy')
    def test_main_default_browser_mode(self, mock_setup, mock_sleep, mock_browser):
        """Default mode (no --manual-browser) uses agent-browser."""
        mock_browser.return_value = '/tmp/out/test.torrent'
        with patch.object(sys, 'argv', ['script', 'https://windfiles.com/share/test']):
            with self.assertRaises(SystemExit) as ctx:
                wd.main()
            self.assertEqual(ctx.exception.code, 0)
        mock_browser.assert_called_once()

    @patch('windfiles_download.download_slow_via_post')
    @patch('windfiles_download.fetch_page_with_retry', return_value=None)
    @patch('windfiles_download.download_with_agent_browser')
    @patch('windfiles_download.time.sleep')
    def test_main_fallback_to_agent_browser(
        self, mock_sleep, mock_browser, mock_fetch, mock_download
    ):
        """If manual-browser fetch fails, falls back to agent-browser."""
        mock_browser.return_value = '/tmp/out/test.torrent'
        with patch.object(sys, 'argv', ['script', 'https://windfiles.com/share/test', '--manual-browser', '--skip-wait']):
            with self.assertRaises(SystemExit) as ctx:
                wd.main()
            self.assertEqual(ctx.exception.code, 0)
        mock_browser.assert_called_once()


# The agent-browser path (download_with_agent_browser) is tightly coupled to
# subprocess calls and file-system polling (~/Downloads, mtime checks).
# Characterization requires deep mocking of subprocess.run outputs and
# os.listdir/mtime/getsize — not done here because the interface needs
# to be broken up for testability in the refactored version.


if __name__ == '__main__':
    unittest.main()
